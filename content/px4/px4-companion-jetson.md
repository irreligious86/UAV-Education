---
id: px4-companion-jetson
title: "PX4 + Jetson Nano (companion)"
level: L3
readingTime: 15 мин
firmware: PX4 1.15+
status: published
tags:
  - Jetson
  - offboard
related: []
next: []
---

## summary
Этот модуль описывает способы подключения одноплатного компьютера NVIDIA Jetson Nano к полетному контроллеру Pixhawk (на прошивке PX4) для организации offboard-управления, передачи телеметрии и обработки данных с камеры (компьютерное зрение).

## theory
### Роли и граница
Pixhawk (PX4) — стабилизация, EKF, failsafe, миссии; Jetson — зрение, планирование, ROS 2, сеть. Граница та же, что в модуле «Companion: роль и границы»: без Jetson аппарат обязан лететь и возвращаться. Jetson Orin Nano/NX — текущий стандарт (Nano первого поколения снят с поддержки JetPack 5+); JetPack ставит Ubuntu, CUDA, TensorRT, OpenCV.

### Физическое подключение
- **UART**: TELEM2 Pixhawk (TX, RX, GND; 3.3 В логика) ↔ UART Jetson (`/dev/ttyTHS1` на 40-пиновой гребёнке Orin Nano: пины 8/10, TX↔RX перекрёстно, общая земля). Скорость 921600 (`SER_TEL2_BAUD`). Отключить консоль на этом порту в Jetson (`nvgetty`), добавить пользователя в `dialout`.
- **Ethernet** (Pixhawk 6X и др. с Ethernet): MAVLink/DDS по UDP — удобнее для больших потоков и видео.
- **USB** — для стенда; в полёте USB-соединение ненадёжно (виброразъём, перезагрузка энумерации).
- **Питание**: Jetson Orin Nano 7–15 Вт — отдельный BEC 5 В/5 А (или 12–19 В в модульный разъём), не от полётника; общая земля с Pixhawk; радиатор и вентилятор — троттлинг по температуре ломает задержки.

### Два варианта связи
1. **MAVLink** (MAVROS для ROS 2 или pymavlink/MAVSDK): `MAV_1_CONFIG` = TELEM2, `MAV_1_MODE` = Onboard (2) — режим с нужными потоками для companion; на Jetson `ros2 launch mavros px4.launch fcu_url:=serial:///dev/ttyTHS1:921600`. Плюс: стандарт, работает с ArduPilot тоже; минус: задержка и ограниченный набор данных.
2. **uXRCE-DDS**: `UXRCE_DDS_CFG` = TELEM2 (и MAVLink тогда на другом порту — не на том же!), на Jetson `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600`; топики `/fmu/out/*`, `/fmu/in/*` с `px4_msgs` той же версии, что прошивка. Плюс: низкая задержка, внутренние топики; минус: только PX4, версии должны совпадать.

### Что крутится на Jetson
ROS 2 узлы: камера (`per-camera`), детектор на TensorRT (`per-cv`), VIO/внешняя навигация (`per-visual-nav`), контур слежения с защитами (`per-tracking`), логгер (`ros2 bag` + синхронизация времени с PX4 через `/fmu/out/timesync_status`). Разделение по процессам: падение детектора не должно останавливать узел защит. Автозапуск — systemd-сервисы с рестартом; watchdog-узел, который сообщает в QGC (`STATUSTEXT`) о здоровье companion.

### Разобранный пример: задержка цепочки
Камера CSI 60 fps (16 мс) → TensorRT YOLO-nano FP16 12 мс → трекер 2 мс → DDS 2 мс → PX4 position controller (`MPC_XY_VEL_P_ACC`, постоянная времени ~0.5 с). Чистая задержка ~35 мс + динамика — контур слежения с K_p ≈ 1 1/с устойчив с запасом (модуль «Слежение»); при USB-камере MJPEG (+60 мс) и Wi-Fi-мосте вместо UART (+20–50 мс, джиттер) — запас исчезает. Отсюда: CSI и провод, не USB и радио.

{{diagram:px4-jetson-link|PX4 и Jetson: камера на Jetson, связь с полётным контроллером по TELEM2 через MAVLink или uXRCE-DDS.}}

## practice

### Вариант 1: Подключение через USB (простой и надежный)
Этот способ рекомендуется для начальной отладки, так как он наиболее стабилен и не требует сложных манипуляций с аппаратными UART Jetson.

**Соединение:**
1. Возьмите USB-кабель (Micro-USB или USB-C в зависимости от модели Pixhawk, например, Pixhawk 6C или Cube Orange)
2. Подключите кабель к порту USB на Pixhawk (обычно это порт для подключения к Mission Planner/QGC) и к любому USB-порту Jetson Nano
3. Примечание: прямое подключение по USB дает полный поток данных MAVLink без потери пакетов

**Настройка параметров PX4:**
1. В QGroundControl перейдите в Параметры (Parameters)
2. Убедитесь, что порт, к которому подключен USB, настроен на передачу MAVLink. Обычно USB порт включен по умолчанию
3. Если вы используете uXRCE-DDS, необходимо отключить MAVLink на используемом порту и активировать UXRCE_DDS_CFG

**Проверка на Jetson:**
1. Подключитесь к Jetson по SSH или через монитор
2. Найдите устройство: `ls /dev/ttyACM*` или `ls /dev/ttyUSB*`. Обычно USB подключение отображается как ttyACM0
3. Дайте права доступа: `sudo chmod 666 /dev/ttyACM0`

### Вариант 2: Подключение через UART (аппаратный последовательный порт)
Этот способ используется для встраиваемых решений, где USB-порт может быть занят или требуется минимизация кабелей.

**Схема подключения:**
1. Подключите TX (передатчик) пикса к RX (приемнику) нано, и наоборот (RX -> TX). Обязательно соедините GND
2. Рекомендуемые пины на 40-pin разъеме Jetson Nano: Pin 8 (TX) и Pin 10 (RX) — это аппаратный UART1 (обычно /dev/ttyTHS1)
3. На Pixhawk используйте порт TELEM 2 или TELEM 1

**Настройка UART на Jetson Nano (критически важно):**

По умолчанию последовательный порт на джамперных пинах (GPIO) часто занят службой последовательной консоли (serial console). Её необходимо отключить, чтобы освободить порт для связи с дроном.

**Отключите сервис nvgetty:**
```bash
sudo systemctl stop nvgetty.service
sudo systemctl disable nvgetty.service
```
Это одна из главных причин ошибок "Permission denied".

**Добавьте пользователя в группу dialout:**
```bash
sudo usermod -aG dialout $USER
```
После этого нужно перезагрузиться (логаут/логин).

**Настройка параметров PX4:**
1. Для MAVLink на TELEM2 (так настроено по умолчанию): `MAV_1_CONFIG = TELEM 2`, `MAV_1_MODE = Onboard` (набор сообщений для companion), `SER_TEL2_BAUD = 921600`.
2. Для uXRCE-DDS вместо MAVLink: отключить MAVLink на порту (`MAV_1_CONFIG = Disabled`), затем `UXRCE_DDS_CFG = TELEM2` и та же `SER_TEL2_BAUD`. После изменения этих параметров — перезагрузка.
3. На одном порту не могут одновременно жить MAVLink и uXRCE-DDS: выбери одно.

**Диагностика UART на Jetson:**

Проверьте, что порт виден и имеет правильную группу:
```bash
ls -l /dev/ttyTHS*
```
Если вы видите `crw------- 1 root tty`, значит порт все еще заблокирован консолью. После отключения nvgetty группа должна измениться на dialout.

### Вариант 3: Использование FTDI-адаптера
Если прямое UART-подключение нестабильно (частая проблема с некоторыми версиями Cube Orange), используйте переходник USB-to-UART.

**Схема:**
1. FTDI адаптер подключается к USB порту Jetson Nano
2. Провода TX/RX/GND от адаптера идут к пиксу
3. Jetson увидит адаптер как /dev/ttyUSB0
4. Преимущество: Обходит аппаратные проблемы UART на плате Jetson или Pixhawk, обеспечивая стабильную связь

## diagnostics

- **Permission denied: '/dev/ttyTHS1'** — Порт используется системной консолью (nvgetty) или у пользователя нет прав. Решение: выполните шаги из раздела "Настройка UART на Jetson Nano" (остановка nvgetty и добавление в группу dialout)

- **MAVLink работает, но uXRCE-DDS не подключается** — Неправильные параметры прошивки или несоответствие версий PX4. Решение: убедитесь, что на телеметрийном порту выключен MAVLink (`MAV_1_CONFIG = Disabled`) и задан `UXRCE_DDS_CFG = TELEM2`, перепрошейте контроллер стабильной версией, запустите агент вручную: `sudo MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600`

- **Нет связи, но порт виден** — Перепутаны пины RX/TX или низкое напряжение питания Jetson. Решение: проверьте перекрестное соединение (TX->RX, RX->TX), убедитесь, что Jetson Nano получает достаточное питание (5В 2-4А)

- **Прерывистая связь или потеря пакетов по UART** — Отсутствие аппаратного контроля потока (RTS/CTS) или электрические помехи. Решение: используйте USB-кабель или FTDI адаптер вместо прямых пинов GPIO

## references

- PX4 User Guide: Companion Computer | https://docs.px4.io/main/en/companion_computer/pixhawk_companion.html | primary | A
- PX4 User Guide: uXRCE-DDS (PX4-ROS 2 Bridge) | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- ArduPilot Dev Docs: Turnkey Companion Computer Solutions | https://ardupilot.org/ | primary | A
- ArduPilot Discourse: Jetson Nano - Pixhawk Cube Communication | https://discuss.ardupilot.org/ | secondary | B
- NVIDIA Developer Forums: Jetson Nano Setup | https://forums.developer.nvidia.com/ | secondary | B
- GitHub: terrytaylorbonn/auxdrone | https://github.com/terrytaylorbonn/auxdrone | secondary | C

## checklist

- Проверить совместимость версии PX4 (1.15+) с Jetson Nano
- Подключить Pixhawk и Jetson Nano (USB, UART или FTDI адаптер)
- Отключить сервис nvgetty на Jetson (для подключения по UART)
- Добавить пользователя в группу dialout
- Настроить параметры PX4 (MAV_1_CONFIG/MAV_1_MODE или UXRCE_DDS_CFG, SER_TEL2_BAUD)
- Проверить доступность портов (`ls /dev/ttyACM*`, `ls /dev/ttyTHS*`)
- Убедиться в правильности соединения RX/TX и питания
- Запустить тестирование связи (MAVLink или XRCE-DDS)