---
id: px4-companion-jetson
title: "PX4 Companion Jatson Nano"
level: L3
readingTime: 15 мин
firmware: PX4 1.15+
status: draft
tags:
  - черновик
references:
  - title: Official docs (заменить)
    url: https://example.com
    tier: primary | A
related: []
next: []
---

## summary
Этот модуль описывает способы подключения одноплатного компьютера NVIDIA Jetson Nano к полетному контроллеру Pixhawk (на прошивке PX4) для организации offboard-управления, передачи телеметрии и обработки данных с камеры (компьютерное зрение).

## theory
Jetson Nano выступает в роли бортового компьютера (Companion Computer). Он берет на себя сложные вычислительные задачи (компьютерное зрение, планирование миссий, управление через ROS 2), в то время как Pixhawk отвечает за стабилизацию полета и низкоуровневые сенсоры.

Использование связки Pixhawk + Jetson Nano позволяет создавать полностью автономные дроны с функцией распознавания объектов, облета препятствий и выполнения сложных миссий без участия оператора.

**Архитектура связи:** Существует два основных подхода к организации связи:
- **MAVLink** (через MAVROS или Pymavlink): Классический способ. Поток телеметрии передается по последовательному интерфейсу (UART). На Jetson данные принимаются и парсятся библиотеками.
- **uXRCE-DDS** (Micro XRCE-DDS): Современный протокол, используемый в PX4 и ROS 2. Позволяет напрямую обмениваться топиками ROS 2 с внутренней шиной uORB полетного контроллера.

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
1. В QGroundControl выберите параметр SER_TEL2_BAUD и установите скорость 921600 (рекомендуемая для высокой нагрузки)
2. Для протокола MAVLink: SER_TEL2_PROTOCOL = 2 (MAVLink 2)
3. Для uXRCE-DDS: SER_TEL2_PROTOCOL = 26 (XRCE-DDS). Также необходимо задать параметр UXRCE_DDS_CFG

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

- **MAVLink работает, но uXRCE-DDS не подключается** — Неправильные параметры прошивки или несоответствие версий PX4. Решение: убедитесь, что на телеметрийном порту выключен MAVLink (SER_TEL2_PROTOCOL = 0 или 26), перепрошейте контроллер стабильной версией, запустите агент вручную: `sudo MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600`

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
- Настроить параметры PX4 (SER_TEL2_BAUD, SER_TEL2_PROTOCOL)
- Проверить доступность портов (`ls /dev/ttyACM*`, `ls /dev/ttyTHS*`)
- Убедиться в правильности соединения RX/TX и питания
- Запустить тестирование связи (MAVLink или XRCE-DDS)