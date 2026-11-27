---
id: ros2-app-arch
title: "Архитектура бортового приложения на ROS 2: узлы, lifecycle, watchdog"
level: L3
readingTime: 65 мин
firmware: ROS 2 Jazzy · PX4 1.18 · ArduPilot 4.7
status: published
added: 2026-11-08
tags:
  - ROS 2
  - архитектура
  - lifecycle
  - watchdog
  - deployment
  - QoS
  - executor
related:
  - ros2-basics
  - ros2-px4
  - eng-systems
  - comp-raspberry
next:
  - ros2-nav
---

## summary
Один узел, который делает всё, работает ровно до первой ошибки в самой ненадёжной части — обычно в восприятии. Бортовое приложение должно переживать падение камеры, зависание нейросети и перезапуск процесса, не теряя управляемости аппарата. Модуль даёт архитектуру, которая это обеспечивает: разделение на мост, восприятие, решение и защиты; управляемые узлы (lifecycle) с явными состояниями; watchdog свежести данных с уровнями OK/DEGRADED/FAILSAFE и гистерезисом; параметры и конфигурация; контейнеры и автозапуск; отладка по bag и профилирование. Лабораторная: скелет из четырёх узлов, в котором убийство узла восприятия переводит систему в DEGRADED, а потеря позиции — в FAILSAFE, и это проверяется тестами. Без ROS проверяются QoS-матрица графа по правилу RxO и модель executor: она показывает, почему MultiThreadedExecutor без своих групп колбэков не спасает уставки от зависшего инференса.

## theory
### Четыре роли
| Роль | Что делает | Чего не делает | Критичность |
|---|---|---|---|
| **Мост** (uXRCE-DDS агент / AP_DDS / MAVROS) | переводит протокол автопилота в топики | не принимает решений | критичная |
| **Восприятие** | камера/лидар → цели, препятствия, поза | не командует аппаратом | некритичная (деградация) |
| **Решение** (миссия, автомат состояний) | выбирает уставки по целям и состоянию | не читает датчики напрямую | критичная |
| **Защиты** (watchdog, геозона приложения, батарея) | следят за свежестью и пределами, имеют право вето | не планируют | критичная |

{{diagram:ros2-graph|Четыре роли в графе узлов: мост, восприятие, решение, защиты.}}

Правило направленности: решение подписано на восприятие и на защиты; защиты могут остановить решение; восприятие не знает о решении. Ни один некритичный узел не должен быть на пути «статус автопилота → уставки».

### Управляемые узлы (lifecycle)
Обычный узел начинает работать сразу при запуске. Lifecycle-узел (`rclpy.lifecycle` / `rclcpp_lifecycle`) проходит явные состояния: **unconfigured → inactive → active → finalized**, с переходами `configure`, `activate`, `deactivate`, `cleanup`, `shutdown`, каждый — со своим колбэком, который может вернуть ошибку. Что это даёт на борту:
- конфигурация (открыть камеру, загрузить модель) отделена от работы — ошибку видно до взлёта;
- узел можно «поставить на паузу» (deactivate) без убийства процесса — например, выключить восприятие при посадке;
- менеджер (`nav2_lifecycle_manager` или свой) поднимает систему в правильном порядке и знает, кто не поднялся.

{{diagram:ros2-lifecycle|Состояния lifecycle-узла: конфигурация отделена от работы, пауза — без убийства процесса.}}

Механика, которую надо знать точно (дизайн-документ managed nodes и реализация `rcl_lifecycle`, ветка jazzy):
- Кроме четырёх основных есть **переходные** состояния: Configuring, Activating, Deactivating, CleaningUp, ShuttingDown и ErrorProcessing. Пока выполняется колбэк перехода, узел находится в переходном состоянии.
- Колбэк возвращает `TransitionCallbackReturn.SUCCESS`, `FAILURE` или `ERROR`. FAILURE в `on_configure` возвращает узел в Unconfigured, FAILURE в `on_activate` — в Inactive (`default_state_machine.c`, переход `ON_ACTIVATE_FAILURE`). ERROR и необработанное исключение ведут в ErrorProcessing. Оттуда успешный `on_error` возвращает узел в Unconfigured, неуспешный переводит в Finalized. Практическое правило: «нет файла модели» — это FAILURE (можно исправить и повторить), «драйвер камеры упал» — ERROR.
- В неактивном состоянии **молчат только lifecycle-издатели** (`create_lifecycle_publisher`; `publish()` обёрнут проверкой «включён ли»). Таймеры, подписки и обычные издатели продолжают работать. Поэтому таймер создаётся в `on_activate` и удаляется в `on_deactivate`, иначе «пауза» восприятия продолжает грузить CPU.
- Управлять узлом можно снаружи: сервисы `/<узел>/change_state`, `get_state`, `get_available_transitions`, топик `/<узел>/transition_event`; в CLI — `ros2 lifecycle set /perception configure`, `ros2 lifecycle get /perception`. В launch-файле это делают `launch_ros.actions.LifecycleNode` и `LifecycleTransition`. У Nav2 есть готовый менеджер (`nav2_lifecycle_manager`): параметры `node_names`, `autostart` (по умолчанию `false`), `bond_timeout` (4.0 с). Узел должен держать bond — так делает `nav2_util::LifecycleNode`. У обычного LifecycleNode из rclpy или rclcpp bond нет, поэтому для своих узлов ставят `bond_timeout: 0.0`, иначе менеджер не поднимет систему («unable to be reached … by bond»). Если bond рвётся, менеджер делает жёсткий сброс всей группы (deactivate → cleanup).

Скелет узла восприятия на rclpy (Jazzy). API сверено с исходниками rclpy ветки jazzy; в песочнице курса ROS 2 нет, поэтому код не запускался:

```python
import os
import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PointStamped

class Perception(LifecycleNode):
    def __init__(self):
        super().__init__("perception")
        self.declare_parameter("model_path", "/opt/models/det.onnx")
        self.pub = None
        self.timer = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        path = self.get_parameter("model_path").value
        if not os.path.exists(path):
            self.get_logger().error(f"model not found: {path}")
            return TransitionCallbackReturn.FAILURE          # back to Unconfigured, visible before take-off
        self.pub = self.create_lifecycle_publisher(PointStamped, "targets", qos_profile_sensor_data)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.timer = self.create_timer(1 / 15, self.step)    # work starts only here
        return super().on_activate(state)                    # enables lifecycle publishers

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.destroy_timer(self.timer)                       # timers do NOT pause by themselves
        self.timer = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.destroy_lifecycle_publisher(self.pub)
        self.pub = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        if self.timer:                                       # shutdown may come straight from Active
            self.destroy_timer(self.timer)
            self.timer = None
        return TransitionCallbackReturn.SUCCESS

    def step(self):
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        self.pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(Perception())

if __name__ == "__main__":
    main()
```

### Watchdog свежести
Каждое входное сообщение имеет максимальный допустимый возраст. Watchdog (`examples/ros2-docker/.../watchdog.py`, без ROS внутри) хранит время последнего сообщения по каждому входу и выдаёт один уровень системы:
- **OK** — всё свежее;
- **DEGRADED** — устарел некритичный вход (цели от камеры): миссия продолжается, функция (сопровождение) приостановлена;
- **FAILSAFE** — устарел критичный вход (статус автопилота, поза): решение перестаёт командовать и запрашивает удержание/посадку.

**Гистерезис:** вход считается восстановленным, только если он свеж непрерывно `recover_s` (например, 1 с) — иначе «мигающая» камера будет включать и выключать сопровождение несколько раз в секунду. Watchdog — отдельный узел с собственным таймером; он сам не командует автопилотом, а публикует уровень, на который подписано решение. Последний рубеж — сам автопилот. PX4 через `COM_OF_LOSS_T` выходит из Offboard в режим из `COM_OBL_RC_ACT`. ArduPilot остаётся в GUIDED и через `GUID_TIMEOUT` останавливается и висит: в логе это видно по обнулению целевой скорости, а не по событию failsafe. Если упадёт всё приложение, аппарат не продолжит лететь по последней уставке.

### Параметры и конфигурация
Всё, что отличается между аппаратами (смещения камеры, пороги, частоты, имена топиков), — в YAML-параметрах, передаваемых через launch. Колбэк `add_on_set_parameters_callback` проверяет новые значения (диапазон, тип) и может отклонить их — так оператор не выставит в поле порог 10 м вместо 1 м. Секреты (ключи VPN, токены облака) — не в параметрах ROS, а в файлах с правами доступа или в переменных окружения сервиса.

Порядок проверки в rclpy (Jazzy, `node.py`) такой. `add_pre_set_parameters_callback` может поправить или дополнить список до проверки. `add_on_set_parameters_callback` отвечает `SetParametersResult(successful=False, reason=...)`, и тогда изменение отклоняется целиком. `add_post_set_parameters_callback` вызывается после применения: там пересоздают то, что зависит от параметра. Диапазон и «только чтение» объявляются ещё при `declare_parameter` через `ParameterDescriptor` (`floating_point_range`, `read_only=True`), так что для простых границ свой колбэк не нужен. YAML для launch — `<имя_узла>: ros__parameters: {...}`, по файлу на аппарат: `quad_07.yaml` лежит в git рядом с конфигом автопилота (`eng-ci-configs`).

### Процессы, узлы и компоненты
Граница процесса — это граница отказа. Узел, упавший с исключением или убитый OOM-killer, забирает с собой всё, что работает в его процессе. Отсюда правило размещения: **восприятие — в своём процессе**, отдельно от решения и защит. Тогда `kill -9` детектора из лабораторной даёт DEGRADED, а не тишину на всём борту.

Обратная сторона — копирование. Кадр 1280×720 RGB занимает 2.76 МБ, и при 30 кадр/с межпроцессная передача через DDS гоняет около 83 МБ/с. Для тяжёлых потоков в C++ есть **композиция**. Узлы оформляются компонентами (`rclcpp_components`, макрос `RCLCPP_COMPONENTS_REGISTER_NODE`) и грузятся в один контейнер: `component_container` (один поток), `component_container_mt` (MultiThreadedExecutor), `component_container_isolated` (свой executor на каждый компонент). В launch это делают `ComposableNodeContainer` и `ComposableNode` с `extra_arguments=[{"use_intra_process_comms": True}]`. Внутри процесса сообщение передаётся указателем, без сериализации. В rclpy механизма компонентов нет (вывод из документации: композиция описана только для rclcpp), поэтому Python-узлы — отдельные процессы. Типичная раскладка: драйвер камеры и детектор — один контейнер C++ (общий отказ допустим, оба про восприятие); решение, watchdog и мост — свои процессы.

### Executors и группы колбэков
Executor решает, какой готовый колбэк и в каком потоке выполнять. Варианты:
- `SingleThreadedExecutor` (по умолчанию в `rclpy.spin`) — один поток: колбэки идут строго по очереди;
- `MultiThreadedExecutor(num_threads)` — пул потоков. В rclpy по умолчанию потоков столько, сколько ядер доступно процессу (`os.sched_getaffinity`; `executors.py`, ветка jazzy);
- событийные: `rclcpp::experimental::executors::EventsExecutor`, в rclpy `rclpy.experimental.EventsExecutor` (экспериментальный; появился в Kilted и бэкпортирован в Jazzy с rclpy 7.1.4, апрель 2025; в Humble нет); в Lyrical для rclcpp добавлен `rclcpp::executors::EventsCBGExecutor` — многопоточный, по заметкам выпуска на 10–15 % меньше CPU, чем Single/MultiThreaded.

Параллельно или нет, решают **группы колбэков**. `MutuallyExclusiveCallbackGroup` выполняет свои колбэки по одному, `ReentrantCallbackGroup` позволяет запускать их одновременно, в том числе один и тот же колбэк. Главная ловушка: у узла есть группа по умолчанию, и она **MutuallyExclusive** (`node.py`: `_default_callback_group = MutuallyExclusiveCallbackGroup()`). Если просто заменить executor на MultiThreaded и не разнести колбэки по группам, ничего не изменится: инференс и таймер уставок останутся в одной взаимоисключающей группе. Модель из лабораторной (шаг 3) показывает это числами. Однопоточный executor и MultiThreaded с группой по умолчанию дают одинаковый максимальный разрыв уставок — 402 мс, и пропущено 19 % тиков таймера. Отдельная группа для инференса возвращает ровные 50 мс.

{{diagram:ros2-executor-gaps|В одной группе с инференсом таймер уставок 20 Гц ждёт: зависание на 400 мс рвёт поток уставок на 400 мс; инференс в своей группе на втором потоке оставляет ровный шаг 50 мс.}}

Две оговорки для Python. Первая: потоки rclpy — обычные потоки Python. Чистый Python-код держит GIL, поэтому параллельности нет; numpy и onnxruntime отпускают GIL на время вычислений, тогда потоки помогают. Вторая: для тяжёлого восприятия надёжнее отдельный процесс. Разрыв в 402 мс не превышает `COM_OF_LOSS_T` (PX4 1.17, по умолчанию 1.0 с) и `GUID_TIMEOUT` (3 с), но зависание на загрузке модели или сборке мусора больше секунды уже выводит PX4 из Offboard (`ros2-px4`), а ArduPilot через 3 с останавливает аппарат в GUIDED.

### QoS по классам топиков
Совместимость считается по модели «запрошено против предложенного» (RxO). Связь есть, только если по **каждой** политике подписчик запрашивает не больше, чем предлагает издатель: reliability (BEST_EFFORT < RELIABLE), durability (VOLATILE < TRANSIENT_LOCAL), deadline (запрошенный не короче предложенного), liveliness (AUTOMATIC < MANUAL_BY_TOPIC) и lease duration. При несовместимости исключения нет: в лог пишется предупреждение «incompatible QoS», подписчик молчит, а у обеих сторон срабатывают события `requested/offered incompatible QoS`. Основы и диагностика `topic info -v` разобраны в `ros2-basics`; здесь — выбор профиля по роли топика.

{{lesson:ros2-basics|QoS с нуля: почему подписка RELIABLE на BEST_EFFORT-издателя PX4 молчит и как это увидеть в `ros2 topic info -v`.}}

| Класс топика | Reliability | Durability | History / depth | Deadline | Пример и источник |
|---|---|---|---|---|---|
| Поток датчика (камера, IMU, цели детектора) | BEST_EFFORT | VOLATILE | KEEP_LAST 1–5 | период × 2 (ориентир курса) | `qos_profile_sensor_data`: BEST_EFFORT, VOLATILE, depth 5 (`rmw/qos_profiles.h`) |
| Телеметрия автопилота | как предлагает мост | как предлагает мост | KEEP_LAST 1–5 | — | PX4 `/fmu/out/*`: BEST_EFFORT + TRANSIENT_LOCAL (`uxrce_dds_client/utilities.hpp:79-80`); AP `/ap/pose/filtered`: BEST_EFFORT, VOLATILE, depth 5 |
| Уставки и команды автопилоту | BEST_EFFORT (принимающая сторона) | VOLATILE | KEEP_LAST 1 | — | читатель PX4 `/fmu/in/*`: BEST_EFFORT, VOLATILE (`utilities.hpp:136-137`); AP `/ap/cmd_vel`: BEST_EFFORT, depth 5 |
| Состояние «по запросу опоздавших» (уровень watchdog, режим миссии) | RELIABLE | TRANSIENT_LOCAL | KEEP_LAST 1 | — | AP `/ap/status`: RELIABLE + TRANSIENT_LOCAL, depth 1 (`AP_DDS_Topic_Table.h:324-331`) |
| Параметры, сервисы | RELIABLE | VOLATILE | 1000 / 10 | — | `qos_profile_parameters` depth 1000, сервисы — VOLATILE, чтобы перезапущенный сервер не получил старые запросы |

Почему так. Старая уставка или кадр бесполезны: повторная доставка RELIABLE только добавит задержку при потерях на Wi-Fi. Уровень системы, наоборот, нужен даже опоздавшему подписчику: узел решения, перезапущенный systemd через 2 с, должен сразу узнать, что сейчас FAILSAFE, а не ждать следующего изменения. Для этого служит TRANSIENT_LOCAL, и он работает, только если его выставили **обе** стороны. Deadline — встроенный в DDS детектор свежести: подписка с `deadline = 0.2 с` получает событие «requested deadline missed», если цели не приходят 0.2 с. Это хороший вход для watchdog, но не замена ему: гистерезиса у deadline нет. Из правила RxO следует ловушка: издатель с deadline 0.2 с и подписчик, запросивший 0.15 с, не соединятся вовсе.

### Дистрибутивы ROS 2 на ноябрь 2026

| Дистрибутив | Выпуск | Конец поддержки | Платформа Tier 1 | Для борта сейчас |
|---|---|---|---|---|
| Humble Hawksbill (LTS) | май 2022 | май 2027 | Ubuntu 22.04 | только поддержка старых проектов |
| Jazzy Jalisco (LTS) | май 2024 | май 2029 | Ubuntu 24.04 | основной выбор; на нём `examples/ros2-docker` курса |
| Kilted Kaiju | май 2025 | ноябрь–декабрь 2026 | Ubuntu 24.04 | не начинать: поддержка кончается |
| Lyrical Luth (LTS) | 22 мая 2026 | май 2031 | Ubuntu 26.04 | новые проекты, если образ companion уже на 26.04 |

Сроки — по странице Distributions документации ROS 2 и REP 2000; Lyrical в REP 2000 пока нет, его платформа — по странице Supported Platforms. Для Kilted они расходятся: страница называет декабрь 2026, REP 2000 — ноябрь 2026. Узлы разных дистрибутивов между собой связываться не обязаны, поэтому companion, наземная станция с ROS и bag-плеер должны стоять на одном дистрибутиве.

### Развёртывание
- **Контейнер**: образ с ROS 2, зависимостями и вашим пакетом; версия образа = версия бортового ПО. `docker compose` с `restart: unless-stopped` и `network_mode: host` (DDS discovery внутри контейнеров с bridge-сетью сложнее).
- **Автозапуск**: systemd-сервис, запускающий `ros2 launch` (или compose) после сети и после появления последовательного порта (`After=`, `BindsTo=dev-ttyAMA0.device`).
- **Логи**: `ros2 bag record` ключевых топиков с разбиением на файлы (`-d/--max-bag-duration` в секундах, `-b/--max-bag-size` в байтах; кольцевое удаление старых файлов `--max-bag-files` появилось в rosbag2 Lyrical и требует одного из двух предыдущих флагов, в Humble, Jazzy и Kilted его нет — место на диске там чистит свой скрипт или таймер systemd) + journald; после инцидента — выгрузка bag вместе с логом автопилота.
- **Время**: chrony/NTP на companion, синхронизация с автопилотом (TIMESYNC/uXRCE) — иначе bag и лог автопилота не совмещаются.

### Отладка и профилирование
- Воспроизведение bag в узлы решения и защит (модуль ros2-basics) — основной инструмент.
- `ros2 topic hz/bw/delay` — частота, пропускная способность и задержка относительно `header.stamp`.
- Профилирование: `top`/`htop` по процессам, `py-spy record` для Python-узлов, `ros2_tracing` (LTTng) для задержек колбэков; на Jetson — `tegrastats` (CPU/GPU/температура).
- Executor: тяжёлые колбэки (нейросеть) — в отдельной группе колбэков (`MutuallyExclusiveCallbackGroup`) с `MultiThreadedExecutor`, иначе таймер уставок 20 Гц будет ждать окончания инференса.

### Справочная таблица API (Jazzy; отличия других дистрибутивов отмечены)

| Что | rclpy | rclcpp / CLI | Замечание |
|---|---|---|---|
| Lifecycle-узел | `rclpy.lifecycle.LifecycleNode` (алиас `Node`) | `rclcpp_lifecycle::LifecycleNode` | колбэки `on_configure/activate/deactivate/cleanup/shutdown/error` |
| Результат перехода | `TransitionCallbackReturn.SUCCESS / FAILURE / ERROR` | `CallbackReturn::SUCCESS / FAILURE / ERROR` | FAILURE в activate → Inactive, ERROR → ErrorProcessing |
| Издатель, молчащий в Inactive | `create_lifecycle_publisher` | `create_publisher` у lifecycle-узла | таймеры и подписки не ставятся на паузу сами |
| Управление переходами | сервис `/<узел>/change_state` | `ros2 lifecycle set/get/list/nodes` | launch: `LifecycleNode`, `LifecycleTransition` |
| Менеджер | — | `nav2_lifecycle_manager` | `autostart` = false, `bond_timeout` = 4.0 с (0.0 для узлов без bond) |
| Executors | `SingleThreadedExecutor`, `MultiThreadedExecutor(num_threads)` | `rclcpp::executors::*` | rclpy: потоков = число доступных ядер |
| Событийный executor | `rclpy.experimental.EventsExecutor` (Kilted; Jazzy с rclpy 7.1.4) | `rclcpp::experimental::executors::EventsExecutor` (экспериментальный); `rclcpp::executors::EventsCBGExecutor` (Lyrical) | в Humble для rclpy нет |
| Группы колбэков | `MutuallyExclusiveCallbackGroup`, `ReentrantCallbackGroup` | те же в `rclcpp::CallbackGroupType` | группа узла по умолчанию — MutuallyExclusive |
| Композиция | нет | `rclcpp_components`, `component_container(_mt/_isolated)` | `use_intra_process_comms: True` |
| QoS-профили | `qos_profile_sensor_data`, `QoSProfile(depth=10)` | `rclcpp::SensorDataQoS()`, `rclcpp::QoS(10)` | по умолчанию RELIABLE, VOLATILE, KEEP_LAST 10 |
| Проверка параметров | `add_pre_set_/add_on_set_/add_post_set_parameters_callback` | те же в rclcpp | `ParameterDescriptor(read_only, floating_point_range)` |
| Запись bag | — | `ros2 bag record -d 60 -b 500000000` | `--max-bag-files` только с Lyrical |

### Место в системе

- **Получает:** статус и позу автопилота через мост (`ros2-px4`, `ros2-ardupilot`); цели от узла восприятия (`per-cv`); время, синхронизированное с автопилотом.
- **Отдаёт:** уставки от узла решения — мосту и дальше автопилоту; уровень OK/DEGRADED/FAILSAFE — решению; bag ключевых топиков — разбору вместе с логом автопилота (`ros2-basics`). Последний рубеж остаётся за автопилотом: таймауты Offboard и GUIDED.
- **Если ошибиться здесь:** инференс в одном executor с таймером уставок → поток 20 Гц рвётся → PX4 выходит из Offboard (`ros2-px4`). Нет синхронизации времени companion с автопилотом → bag и лог автопилота не совмещаются, разбор инцидента невозможен (`ap-logs`).

## practice
Шаги 1–3 — чистый Python, они запущены в песочнице курса, вывод вставлен без правок. Шагам 4–6 нужны ROS 2 Jazzy и SITL (`examples/ros2-docker`): в песочнице, где писался модуль, ROS 2 не установлен, поэтому их результат описан как ожидаемый, а критерии даны для проверки у себя.

### Шаг 1. Тесты watchdog
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_watchdog.py
```
Результат в песочнице (Python 3.13): `5 passed in 0.01s`. Разбери `test_hysteresis_on_flapping_input`. Вход `targets` пропал на 1 с, вернулся на 0.5 с — уровень всё ещё DEGRADED; ещё 0.6 с — OK. Объясни, почему.

### Шаг 2. QoS-матрица своего графа без ROS
Прежде чем запускать узлы, проверь, соединятся ли они. Скрипт ниже реализует правила RxO из документации ROS 2 (reliability, durability, deadline, liveliness, lease duration). Профили мостов взяты из исходников: PX4 1.17 `uxrce_dds_client/utilities.hpp`, ArduPilot 4.7.2 `AP_DDS_Topic_Table.h`. Добавь в `cases` все топики своего приложения с профилями, которые ты собираешься задать.

```python
"""Request-vs-offered QoS check (rules: ROS 2 docs, 'QoS compatibilities'). No ROS needed."""
INF = float("inf")                      # "default" duration = unspecified = infinite
REL = {"best_effort": 0, "reliable": 1}
DUR = {"volatile": 0, "transient_local": 1}
LIV = {"automatic": 0, "manual_by_topic": 1}

def compatible(pub, sub):
    """pub offers, sub requests; returns list of reasons why there is NO connection."""
    why = []
    if REL[pub["rel"]] < REL[sub["rel"]]:
        why.append("reliability: BEST_EFFORT offered, RELIABLE requested")
    if DUR[pub["dur"]] < DUR[sub["dur"]]:
        why.append("durability: VOLATILE offered, TRANSIENT_LOCAL requested")
    if pub.get("deadline", INF) > sub.get("deadline", INF):
        why.append(f"deadline: offered {pub.get('deadline', INF)} s > requested {sub.get('deadline', INF)} s")
    if LIV[pub.get("liv", "automatic")] < LIV[sub.get("liv", "automatic")]:
        why.append("liveliness: AUTOMATIC offered, MANUAL_BY_TOPIC requested")
    if pub.get("lease", INF) > sub.get("lease", INF):
        why.append("lease duration: offered longer than requested")
    return why

DEFAULT = dict(rel="reliable", dur="volatile")            # rmw_qos_profile_default, depth 10
SENSOR = dict(rel="best_effort", dur="volatile")          # rmw_qos_profile_sensor_data, depth 5
cases = [
    # topic, publisher (offered), subscriber (requested)
    ("/fmu/out/vehicle_odometry  PX4 -> default sub", dict(rel="best_effort", dur="transient_local"), DEFAULT),
    ("/fmu/out/vehicle_odometry  PX4 -> sensor_data", dict(rel="best_effort", dur="transient_local"), SENSOR),
    ("/fmu/in/trajectory_setpoint default pub -> PX4", DEFAULT, dict(rel="best_effort", dur="volatile")),
    ("/ap/pose/filtered          AP  -> default sub", dict(rel="best_effort", dur="volatile"), DEFAULT),
    ("/ap/status                 AP  -> latched sub", dict(rel="reliable", dur="transient_local"),
     dict(rel="reliable", dur="transient_local")),
    ("/app/level  watchdog default -> latched sub", DEFAULT, dict(rel="reliable", dur="transient_local")),
    ("/app/targets 10 Hz, deadline 0.2 -> sub deadline 0.15", dict(SENSOR, deadline=0.2), dict(SENSOR, deadline=0.15)),
    ("/app/targets 10 Hz, deadline 0.2 -> sub deadline 0.5", dict(SENSOR, deadline=0.2), dict(SENSOR, deadline=0.5)),
]
for name, p, s in cases:
    why = compatible(p, s)
    print(f"{'OK ' if not why else 'NO '} {name}" + ("" if not why else "\n      " + "; ".join(why)))
```

```text
NO  /fmu/out/vehicle_odometry  PX4 -> default sub
      reliability: BEST_EFFORT offered, RELIABLE requested
OK  /fmu/out/vehicle_odometry  PX4 -> sensor_data
OK  /fmu/in/trajectory_setpoint default pub -> PX4
NO  /ap/pose/filtered          AP  -> default sub
      reliability: BEST_EFFORT offered, RELIABLE requested
OK  /ap/status                 AP  -> latched sub
NO  /app/level  watchdog default -> latched sub
      durability: VOLATILE offered, TRANSIENT_LOCAL requested
NO  /app/targets 10 Hz, deadline 0.2 -> sub deadline 0.15
      deadline: offered 0.2 s > requested 0.15 s
OK  /app/targets 10 Hz, deadline 0.2 -> sub deadline 0.5
```

Две строки NO знакомы по `ros2-basics`: подписчик по умолчанию (RELIABLE) на BEST_EFFORT-телеметрию. Третья — архитектурная ошибка этого модуля: watchdog публикует уровень профилем по умолчанию (VOLATILE), а узел решения запросил TRANSIENT_LOCAL, чтобы после перезапуска сразу узнать текущий уровень. Связи нет вовсе. Исправление — TRANSIENT_LOCAL у издателя. Четвёртая — deadline: подписчик хочет сообщения чаще, чем издатель обещает. Уставки в PX4 с издателем по умолчанию (RELIABLE) соединяются: RELIABLE предлагает больше, чем запрашивает BEST_EFFORT.

### Шаг 3. Модель executor: кто кого ждёт
Модель — не rclpy, а его правила в 46 строках: N потоков; как в rclpy (`_wait_for_ready_callbacks`), готовые таймеры берутся раньше готовых подписок, среди равных — самый старый; взаимоисключающая группа выполняет по одному колбэку, просроченный таймер срабатывает один раз (пропущенные периоды не догоняются), у камеры KEEP_LAST 1. Нагрузка: таймер уставок 20 Гц (1 мс), watchdog 10 Гц, инференс 15 кадр/с по 60 мс, раз в 3 с — зависание на 400 мс (сборка мусора, догрузка модели). 30 с модельного времени.

```python
"""Executor model (not rclpy): N worker threads; like rclpy, ready timers are taken before ready
subscriptions, then the oldest first; a MutuallyExclusive
group runs one callback at a time; a node's default group is MutuallyExclusive; an overdue timer fires
once (missed periods are skipped), the camera subscription is KEEP_LAST 1."""
SOURCES = [("setpoint", 0.050, 0.001),        # 20 Hz timer, 1 ms
           ("watchdog", 0.100, 0.0005),       # 10 Hz timer
           ("inference", 1 / 15, 0.060)]      # camera 15 Hz, 60 ms per frame

def simulate(threads, group_of, T=30.0):
    jobs = []
    for name, per, cost in SOURCES:
        for k in range(round(T / per)):
            stall = name == "inference" and k > 0 and k % 45 == 0      # 400 ms stall every 3 s
            jobs.append((k * per, name, 0.400 if stall else cost))
    jobs.sort()
    free, busy, late, starts, skipped = [0.0] * threads, {}, [], [], {"setpoint": 0, "inference": 0}
    while jobs:
        w = min(range(threads), key=free.__getitem__)
        now = free[w]
        for src in ("setpoint", "watchdog", "inference"):
            due = [j for j in jobs if j[1] == src and j[0] <= now]
            for old in due[:-1]:                  # only the newest tick / frame survives
                jobs.remove(old)
                if src in skipped:
                    skipped[src] += 1
        ready = [j for j in jobs if j[0] <= now and busy.get(group_of[j[1]], 0) <= now]
        if not ready:                             # sleep until something can run
            free[w] = min(max(j[0], busy.get(group_of[j[1]], 0)) for j in jobs)
            continue
        ready.sort(key=lambda j: (j[1] == "inference", j[0]))    # timers first, then subscriptions
        t, name, cost = ready[0]
        jobs.remove(ready[0])
        free[w] = busy[group_of[name]] = now + cost
        if name == "setpoint":
            starts.append(now); late.append(now - t)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    late.sort()
    return max(gaps), late[int(0.99 * len(late))], skipped["setpoint"], skipped["inference"]

for label, n, groups in [
        ("SingleThreadedExecutor, one default group", 1, dict(setpoint="A", watchdog="A", inference="A")),
        ("MultiThreaded(2), one default group", 2, dict(setpoint="A", watchdog="A", inference="A")),
        ("MultiThreaded(2), inference in own ME group", 2, dict(setpoint="A", watchdog="A", inference="B"))]:
    gap, p99, sp, fr = simulate(n, groups)
    print(f"{label:<45s} max gap {gap*1000:3.0f} ms  p99 late {p99*1000:3.0f} ms  "
          f"setpoints skipped {sp:3d}  frames dropped {fr}")
```

```text
SingleThreadedExecutor, one default group     max gap 402 ms  p99 late  43 ms  setpoints skipped 115  frames dropped 45
MultiThreaded(2), one default group           max gap 402 ms  p99 late  43 ms  setpoints skipped 115  frames dropped 45
MultiThreaded(2), inference in own ME group   max gap  50 ms  p99 late   0 ms  setpoints skipped   0  frames dropped 45
```

Первые две строки совпадают: второй поток простаивает, потому что все колбэки лежат в группе по умолчанию, а она MutuallyExclusive. Максимальный разрыв уставок 402 мс — зависание 400 мс плюс остаток шага: сразу после зависания таймер идёт раньше следующего кадра. 115 из 600 тиков таймера пропущены. Даже без зависаний (замени `k % 45 == 0` на `False`) колбэк 60 мс в одной группе с таймером 50 мс съедает 63 тика из 600: разрыв доходит до 67 мс, опоздание p99 — 43 мс. Отдельная группа для инференса возвращает ровный шаг 50 мс без пропусков. 45 потерянных кадров одинаковы во всех вариантах: за 30 с девять зависаний, каждое пропускает пять кадров, и KEEP_LAST 1 их выбрасывает — после зависания детектор берёт свежий кадр, а не догоняет очередь. Поэкспериментируй сам. При `threads=1` и разных группах разрыв снова 402 мс: без второго потока группы не помогают. При инференсе 80 мс (медленнее камеры: 66.7 мс на кадр) теряется уже 102 кадра, а уставки с отдельной группой идут с шагом 50 мс.

### Шаг 4. Скелет из четырёх узлов
Соберите пакет `uav_app` с узлами `bridge_monitor` (подписка на статус/позу автопилота), `perception_stub` (публикует цели 10 Гц, падает по команде), `watchdog_node` (обёртка `watchdog.py`, публикует уровень и причины), `decision_node` (автомат из ros2-px4, подписан на уровень). Launch-файл с параметрами из YAML. Профили QoS — из таблицы теории и проверенные шагом 2: уровень watchdog RELIABLE + TRANSIENT_LOCAL, цели — `qos_profile_sensor_data`; `perception_stub` — lifecycle-узел по скелету из теории, инференс-колбэк — в своей группе.

### Шаг 5. Отказ восприятия и позиции
В SITL: запустите миссию сопровождения (`perception_stub` даёт цель), затем `kill -9` процесса восприятия → уровень DEGRADED, аппарат удерживает позицию, миссия не прерывается аварийно; поднимите узел обратно → через `recover_s` OK. Затем остановите мост (агента) → FAILSAFE, решение прекращает уставки; убедитесь по логу автопилота, что сработал его собственный таймаут (PX4 — выход из Offboard; ArduPilot — остановка в GUIDED, целевая скорость обнуляется). Дополнительно: `ros2 lifecycle set /perception_stub deactivate` — цели перестают публиковаться без убийства процесса, уровень DEGRADED; `activate` — снова OK через `recover_s`.

### Шаг 6. Автозапуск
Оформите systemd-юнит (или compose с restart) для companion: старт после сети, перезапуск при падении, кольцевая запись bag. Перезагрузите машину/контейнер и убедитесь, что система поднялась сама: без единой ручной команды `ros2 node list` показывает все четыре узла.

### Переход на реальное железо
На companion с подключённым автопилотом, **пропеллеры сняты**, питание от АКБ через штатный BEC. (1) Запусти систему через systemd, `ros2 topic hz` на уставках: 20 ± 1 Гц (ориентир курса). (2) Нагрузи CPU (`stress-ng --cpu 0 --timeout 60s` или реальный инференс на полном разрешении), смотри `ros2 topic hz` и `tegrastats`/`htop`: частота уставок не должна падать ниже 18 Гц (ориентир курса: 10 % от номинала). Если падает, значит, тяжёлый колбэк не вынесен в свою группу или свой процесс. (3) `kill -9` узла восприятия: уровень DEGRADED за время `max_age` входа целей, OK — через `recover_s` после перезапуска. (4) Отключи кабель моста (UART/Ethernet): FAILSAFE на companion, а в логе автопилота — его собственный таймаут: PX4 через `COM_OF_LOSS_T` (1.0 с) выходит из Offboard, ArduPilot через `GUID_TIMEOUT` (3 с) останавливается, оставаясь в GUIDED. Прекращай и разбирайся при любом из признаков: уставки идут после FAILSAFE, автопилот не заметил потери потока, после перезагрузки поднялись не все четыре узла. Только после прохождения всех четырёх пунктов — привязной или низкий полёт в Offboard/GUIDED с готовым переключателем режима на пульте.

Самопроверка: лабораторная выполнена, когда проходят тесты watchdog и ваше объяснение `test_hysteresis_on_flapping_input` совпадает с эталоном ниже, скелет из четырёх узлов отрабатывает оба отказа в SITL (логи сохранены): после `kill -9` восприятия уровень DEGRADED, аппарат удерживает позицию, а после возврата узла уровень снова OK через `recover_s`; после остановки моста — FAILSAFE, решение прекращает уставки и в логе автопилота виден его собственный таймаут; после перезагрузки система поднимается без ручных команд; скрипт шага 2 на своём графе не даёт ни одной строки NO, а на примере выдаёт ровно четыре NO с причинами reliability, reliability, durability, deadline; модель шага 3 даёт 402 / 402 / 50 мс максимального разрыва, 115 / 115 / 0 пропущенных тиков и 45 потерянных кадров, а при `threads=1` и разных группах — снова 402 мс; на железе частота уставок под нагрузкой CPU не ниже 18 Гц.

**Эталон для самопроверки.** После 0.5 с восстановления уровень ещё DEGRADED, потому что вход считается восстановленным, только если он свеж непрерывно `recover_s` (например, 1 с), а 0.5 с меньше. Типичные неверные: (1) сопровождение включается и выключается несколько раз в секунду — гистерезиса нет или `recover_s` слишком мал; (2) после перезагрузки приложение не стартует — сервис запускается раньше, чем появились сеть или последовательный порт (`After=`, `BindsTo=`); (3) при падении восприятия миссия прервалась аварийно — некритичный узел оказался на пути «статус автопилота → уставки». (4) MultiThreadedExecutor поставлен, а уставки всё равно рвутся на время инференса — колбэки остались в группе узла по умолчанию (MutuallyExclusive). (5) Узел решения после перезапуска «не видит» FAILSAFE, пока уровень не изменится, — издатель уровня VOLATILE, нужен TRANSIENT_LOCAL с обеих сторон.

## diagnostics
- **Симптом:** при зависании нейросети аппарат «подвисает» с уставками
  - Возможная причина: инференс и таймер уставок в одном потоке executor-а.
  - Что сделать: отдельные группы колбэков, MultiThreadedExecutor, или восприятие — отдельный процесс.
- **Симптом:** сопровождение включается и выключается несколько раз в секунду
  - Возможная причина: нет гистерезиса восстановления входа.
  - Что сделать: recover_s ≥ 0.5–1 с.
- **Симптом:** после перезагрузки companion приложение не стартует
  - Возможная причина: сервис стартует раньше, чем появился последовательный порт/сеть.
  - Что сделать: зависимости systemd (After/BindsTo), ретраи подключения в мосте.
- **Симптом:** bag и лог автопилота не совмещаются по времени
  - Возможная причина: часы companion не синхронизированы.
  - Что сделать: chrony, использовать метки времени автопилота в сообщениях.
- **Симптом:** поставил `MultiThreadedExecutor`, а уставки всё равно рвутся на время инференса
  - Возможная причина: все колбэки в группе узла по умолчанию, а она MutuallyExclusive.
  - Что сделать: инференс — в свою `MutuallyExclusiveCallbackGroup` (параметр `callback_group=` у подписки/таймера), проверить моделью шага 3; для чистого Python — отдельный процесс (GIL).
- **Симптом:** перезапущенный узел решения не знает текущий уровень, пока тот не изменится
  - Возможная причина: уровень публикуется VOLATILE; или TRANSIENT_LOCAL выставлен только с одной стороны (у подписчика — связи нет вовсе).
  - Что сделать: RELIABLE + TRANSIENT_LOCAL, depth 1 у издателя и подписчика; проверить `ros2 topic info -v`.
- **Симптом:** восприятие в состоянии Inactive, а CPU по-прежнему загружен
  - Возможная причина: таймер или подписка созданы в конструкторе/`on_configure` — в Inactive молчат только lifecycle-издатели.
  - Что сделать: создавать таймер в `on_activate`, удалять в `on_deactivate`.
- **Симптом:** узел не переходит в Active, `ros2 lifecycle get` показывает unconfigured
  - Возможная причина: `on_configure` вернул FAILURE (нет файла модели, камера не открылась) — так и задумано.
  - Что сделать: читать лог узла до взлёта; менеджер с `autostart` должен остановить подъём системы, а не взлетать без восприятия.
- **Симптом:** подписка с deadline молчит, в логе «incompatible QoS ... DEADLINE»
  - Возможная причина: подписчик запросил deadline короче, чем предлагает издатель.
  - Что сделать: deadline подписчика ≥ deadline издателя; проверить парой в скрипте шага 2.

## references
- ROS 2 — Managed nodes (lifecycle) design | https://design.ros2.org/articles/node_lifecycle.html | primary | A
- ROS 2 Jazzy — Executors and callback groups | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Executors.html | primary | A
- ROS 2 Jazzy — Quality of Service settings (RxO compatibility, QoS events) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html | primary | A
- ROS 2 — Distributions (release and EOL dates) | https://docs.ros.org/en/rolling/Releases.html | primary | A
- REP 2000 — ROS 2 releases and target platforms | https://github.com/ros-infrastructure/rep/blob/master/rep-2000.rst | primary | A
- rclpy (jazzy) — executors.py, callback_groups.py, node.py, lifecycle/ | https://github.com/ros2/rclpy/tree/jazzy/rclpy/rclpy | primary | A
- rcl_lifecycle — default_state_machine.c (переходы FAILURE/ERROR) | https://github.com/ros2/rcl/blob/jazzy/rcl_lifecycle/src/default_state_machine.c | primary | A
- rmw — qos_profiles.h (профили sensor_data, default, parameters) | https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/qos_profiles.h | primary | A
- rosbag2 — ros2bag record verb (флаги -d, -b, --max-bag-files) | https://github.com/ros2/rosbag2/blob/rolling/ros2bag/ros2bag/verb/record.py | primary | A
- PX4 v1.17 — uxrce_dds_client utilities.hpp (QoS писателей и читателей) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/utilities.hpp | primary | A
- ArduPilot 4.7.2 — AP_DDS_Topic_Table.h (QoS топиков /ap/*) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_Topic_Table.h | primary | A
- ros2_tracing | https://github.com/ros2/ros2_tracing | primary | A
- Nav2 — lifecycle manager | https://api.nav2.org/nav2-jazzy/html/md_nav2_lifecycle_manager_README.html | primary | A

## checklist
- Разделяю приложение на мост, восприятие, решение и защиты с правильными зависимостями
- Использую lifecycle-узлы и понимаю их состояния
- Строю watchdog свежести с уровнями и гистерезисом
- Выношу конфигурацию в параметры с проверкой значений
- Развёртываю в контейнере с автозапуском и кольцевой записью bag
- Отлаживаю по bag и профилирую узлы, разношу тяжёлые колбэки по группам
- Выбираю QoS по классу топика и проверяю пары по правилу RxO до запуска
- Понимаю, что даёт и чего не даёт MultiThreadedExecutor без своих групп колбэков
- Выбираю дистрибутив по сроку поддержки (Jazzy до 2029, Lyrical до 2031)
