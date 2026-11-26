---
id: ros2-app-arch
title: "Архітектура бортового застосунку на ROS 2: вузли, lifecycle, watchdog"
level: L3
readingTime: 45 хв
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 2
  - архітектура
  - lifecycle
  - watchdog
  - deployment
related:
  - ros2-px4
  - eng-systems
  - comp-raspberry
next:
  - ros2-nav
source: content/ros2/ros2-app-arch.md
source_hash: 086713db5f3e
---

## summary
Один вузол, який робить усе, працює рівно до першої помилки в найменш надійній частині — зазвичай у сприйнятті. Бортовий застосунок має переживати падіння камери, зависання нейромережі й перезапуск процесу, не втрачаючи керованості апарата. Модуль дає архітектуру, яка це забезпечує: поділ на міст, сприйняття, рішення й захисти; керовані вузли (lifecycle) з явними станами; watchdog свіжості даних із рівнями OK/DEGRADED/FAILSAFE і гістерезисом; параметри й конфігурацію; контейнери та автозапуск; налагодження за bag і профілювання. Лабораторна: скелет із чотирьох вузлів, у якому вбивство вузла сприйняття переводить систему в DEGRADED, а втрата позиції — у FAILSAFE, і це перевіряється тестами.

## theory
### Чотири ролі
| Роль | Що робить | Чого не робить | Критичність |
|---|---|---|---|
| **Міст** (uXRCE-DDS агент / AP_DDS / MAVROS) | перекладає протокол автопілота в топіки | не ухвалює рішень | критична |
| **Сприйняття** | камера/лідар → цілі, перешкоди, поза | не командує апаратом | некритична (деградація) |
| **Рішення** (місія, автомат станів) | вибирає уставки за цілями та станом | не читає датчики напряму | критична |
| **Захисти** (watchdog, геозона застосунку, батарея) | стежать за свіжістю та межами, мають право вето | не планують | критична |

{{diagram:ros2-graph|Чотири ролі в графі вузлів: міст, сприйняття, рішення, захисти.}}

Правило спрямованості: рішення підписане на сприйняття й на захисти; захисти можуть зупинити рішення; сприйняття не знає про рішення. Жоден некритичний вузол не має бути на шляху «статус автопілота → уставки».

### Керовані вузли (lifecycle)
Звичайний вузол починає працювати одразу після запуску. Lifecycle-вузол (`rclpy.lifecycle` / `rclcpp_lifecycle`) проходить явні стани: **unconfigured → inactive → active → finalized**, з переходами `configure`, `activate`, `deactivate`, `cleanup`, `shutdown`, кожен — зі своїм колбеком, який може повернути помилку. Що це дає на борту:
- конфігурацію (відкрити камеру, завантажити модель) відокремлено від роботи — помилку видно до зльоту;
- вузол можна «поставити на паузу» (deactivate) без убивства процесу — наприклад, вимкнути сприйняття під час посадки;
- менеджер (`nav2_lifecycle_manager` або власний) піднімає систему в правильному порядку і знає, хто не піднявся.

{{diagram:ros2-lifecycle|Стани lifecycle-вузла: конфігурацію відокремлено від роботи, пауза — без убивства процесу.}}

{{diagram:ros2-executor-gaps|В одной группе с инференсом таймер уставок 20 Гц ждёт: зависание на 400 мс рвёт поток уставок на 400 мс; инференс в своей группе на втором потоке оставляет ровный шаг 50 мс.}}

### Watchdog свіжості
Кожне вхідне повідомлення має максимальний допустимий вік. Watchdog (`examples/ros2-docker/.../watchdog.py`, без ROS усередині) зберігає час останнього повідомлення для кожного входу і видає один рівень системи:
- **OK** — усе свіже;
- **DEGRADED** — застарів некритичний вхід (цілі від камери): місія триває, функцію (супровід) призупинено;
- **FAILSAFE** — застарів критичний вхід (статус автопілота, поза): рішення перестає командувати й запитує утримання/посадку.

**Гістерезис:** вхід вважається відновленим, лише якщо він свіжий безперервно `recover_s` (наприклад, 1 с) — інакше «блимаюча» камера вмикатиме й вимикатиме супровід кілька разів на секунду. Watchdog — окремий вузол із власним таймером; він сам не командує автопілотом, а публікує рівень, на який підписане рішення. Останній рубіж — сам автопілот (таймаути Offboard/GUIDED): якщо впаде весь застосунок, апарат однаково перейде в безпечний режим.

### Параметри та конфігурація
Усе, що відрізняється між апаратами (зміщення камери, пороги, частоти, імена топіків), — у YAML-параметрах, що передаються через launch. Колбек `add_on_set_parameters_callback` перевіряє нові значення (діапазон, тип) і може їх відхилити — так оператор не виставить у полі поріг 10 м замість 1 м. Секрети (ключі VPN, токени хмари) — не в параметрах ROS, а у файлах із правами доступу або в змінних оточення сервісу.

### Розгортання
- **Контейнер**: образ із ROS 2, залежностями й твоїм пакетом; версія образу = версія бортового ПЗ. `docker compose` з `restart: unless-stopped` і `network_mode: host` (DDS discovery всередині контейнерів із bridge-мережею складніший).
- **Автозапуск**: systemd-сервіс, що запускає `ros2 launch` (або compose) після мережі й після появи послідовного порту (`After=`, `BindsTo=dev-ttyAMA0.device`).
- **Логи**: `ros2 bag record` ключових топіків із розбиттям на файли (`--max-bag-duration`, `--max-bag-size`; автовидалення старих файлів `--max-bag-files` є лише в нових версіях rosbag2, у Humble/Jazzy місце на диску треба чистити самому) + journald; після інциденту — вивантаження bag разом із логом автопілота.
- **Час**: chrony/NTP на companion, синхронізація з автопілотом (TIMESYNC/uXRCE) — інакше bag і лог автопілота не поєднуються.

### Налагодження та профілювання
- Відтворення bag у вузли рішення й захистів (модуль ros2-basics) — основний інструмент.
- `ros2 topic hz/bw/delay` — частота, пропускна здатність і затримка відносно `header.stamp`.
- Профілювання: `top`/`htop` за процесами, `py-spy record` для Python-вузлів, `ros2_tracing` (LTTng) для затримок колбеків; на Jetson — `tegrastats` (CPU/GPU/температура).
- Executor: важкі колбеки (нейромережа) — в окремій групі колбеків (`MutuallyExclusiveCallbackGroup`) з `MultiThreadedExecutor`, інакше таймер уставок 20 Гц чекатиме завершення інференсу.

## practice
### Крок 1. Тести watchdog
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_watchdog.py
```
Розбери `test_hysteresis_on_flapping_input`: чому після 0.5 с відновлення рівень ще DEGRADED.

### Крок 2. Скелет із чотирьох вузлів
Збери пакет `uav_app` з вузлами `bridge_monitor` (підписка на статус/позу автопілота), `perception_stub` (публікує цілі 10 Гц, падає за командою), `watchdog_node` (обгортка `watchdog.py`, публікує рівень і причини), `decision_node` (автомат з ros2-px4, підписаний на рівень). Launch-файл із параметрами з YAML.

### Крок 3. Відмова сприйняття й позиції
У SITL: запусти місію супроводу (`perception_stub` дає ціль), потім `kill -9` процесу сприйняття → рівень DEGRADED, апарат утримує позицію, місія не переривається аварійно; підніми вузол назад → через `recover_s` OK. Потім зупини міст (агента) → FAILSAFE, рішення припиняє уставки; переконайся за логом автопілота, що спрацював його власний таймаут.

### Крок 4. Автозапуск
Оформи systemd-юніт (або compose з restart) для companion: старт після мережі, перезапуск у разі падіння, кільцевий запис bag. Перезавантаж машину/контейнер і покажи, що система піднялася сама.

Лабораторну зараховано, коли проходять тести watchdog, скелет із чотирьох вузлів відпрацьовує обидві відмови в SITL (з логами) і є робочий автозапуск.

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

## diagnostics
- **Симптом:** під час зависання нейромережі апарат «підвисає» з уставками
  - Можлива причина: інференс і таймер уставок в одному потоці executor-а.
  - Що зробити: окремі групи колбеків, MultiThreadedExecutor, або сприйняття — окремий процес.
- **Симптом:** супровід вмикається й вимикається кілька разів на секунду
  - Можлива причина: немає гістерезису відновлення входу.
  - Що зробити: recover_s ≥ 0.5–1 с.
- **Симптом:** після перезавантаження companion застосунок не стартує
  - Можлива причина: сервіс стартує раніше, ніж з'явився послідовний порт/мережа.
  - Що зробити: залежності systemd (After/BindsTo), повторні спроби підключення в мосту.
- **Симптом:** bag і лог автопілота не поєднуються за часом
  - Можлива причина: годинник companion не синхронізовано.
  - Що зробити: chrony, використовувати мітки часу автопілота в повідомленнях.

## references
- ROS 2 — Managed nodes (lifecycle) design | https://design.ros2.org/articles/node_lifecycle.html | primary | A
- ROS 2 Jazzy — Executors and callback groups | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Executors.html | primary | A
- ros2_tracing | https://github.com/ros2/ros2_tracing | primary | A
- Nav2 — lifecycle manager | https://api.nav2.org/nav2-jazzy/html/md_nav2_lifecycle_manager_README.html | primary | A

## checklist
- Розділяю застосунок на міст, сприйняття, рішення й захисти з правильними залежностями
- Використовую lifecycle-вузли й розумію їхні стани
- Будую watchdog свіжості з рівнями й гістерезисом
- Виношу конфігурацію в параметри з перевіркою значень
- Розгортаю в контейнері з автозапуском і кільцевим записом bag
- Налагоджую за bag і профілюю вузли, розношу важкі колбеки по групах
