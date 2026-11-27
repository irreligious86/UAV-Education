"""Stage 6 diagrams for px4-hardware-peripherals.

1. px4-periph-ports-v6x — serial ports of px4/fmu-v6x in PX4 1.17.0 and 1.18.0, same port list (boards/px4/fmu-v6x/default.px4board
   lines 4-10, Tools/serial/generate_config.py port indexes and default baud rates) with the reference
   plan from the module's practice step 1 written under each port; I2C, CAN and Ethernet in a second row.
2. px4-periph-enable-flow — the "pick a port or enable the driver -> reboot -> verify" pattern
   (Tools/serial/rc.serial.jinja, rc.serial_port.jinja, ROMFS/px4fmu_common/init.d/rc.sensors, rcS).
"""
from __future__ import annotations

from svg import Box, flow

# (tag, config value, device, SER_*_BAUD default, driver parameter from the reference plan, what is connected)
UARTS = [
    ("TELEM1", 101, "ttyS6", "57600", "MAV_0_CONFIG", "SiK, Normal"),
    ("TELEM2", 102, "ttyS4", "921600", "MAV_1_CONFIG", "companion, Onboard"),
    ("TELEM3", 103, "ttyS1", "57600", "SENS_TFMINI_CFG", "TFmini, 115200"),
    ("GPS1", 201, "ttyS0", "0 (авто)", "GPS_1_CONFIG", "GPS 1"),
    ("GPS2", 202, "ttyS7", "0 (авто)", "GPS_2_CONFIG", "GPS 2"),
    ("EXT2", 401, "ttyS3", "57600", "MSP_OSD_CONFIG", "msp_osd, 115200"),
]
BUSES = [
    ("I²C", ["I²C (внешняя шина)", "SENS_EN_MS4525DO = 1"], "airspeed, компас"),
    ("CAN", ["CAN1 / CAN2", "UAVCAN_ENABLE = 3"], "ESC: UAVCAN_EC_FUNC1…4"),
    ("ETH", ["Ethernet = 1000", "MAV_2_CONFIG"], "UDP 14550, 100000 B/s"),
    ("RC", ["RC = 300 · ttyS5", "линия PX4IO/RC"], "занята IO; в списке с 1.17"),
]


def build(D: dict) -> None:
    # ---- 1. port map of px4/fmu-v6x ----------------------------------------------------------
    boxes = []
    x = 10
    w = 108
    for tag, idx, dev, baud, par, what in UARTS:
        boxes.append(Box("u" + tag, [f"{tag} = {idx}", dev + " · " + baud, par], x, 54, w, 58,
                         accent=tag in ("TELEM1", "GPS1"), note=what))
        x += w + 10
    x = 10
    for bid, lines, what in BUSES:
        boxes.append(Box("b" + bid, lines, x, 182, 166, 46, note=what))
        x += 166 + 12
    D["px4-periph-ports-v6x"] = flow(
        "px4/fmu-v6x, PX4 1.18: порты и кто на них сидит", boxes, [], 720, 296,
        notes=[
            (10, 44, "UART: число — значение параметра *_CONFIG / *_CFG; вторая строка — устройство и умолчание SER_*_BAUD", "m t"),
            (10, 172, "Остальное: I²C и CAN включаются своим параметром; Ethernet — значение 1000 для MAVLink и uXRCE-DDS", "m t"),
            (10, 268, "Выделены порты, занятые по умолчанию (MAV_0_CONFIG = 101, GPS_1_CONFIG = 201). Под блоками — план из шага 1.", "m t"),
            (10, 283, "Один порт — один драйвер: второй получит «Conflicting config for /dev/ttyS…» и не запустится.", "m t"),
        ])

    # ---- 2. enable -> reboot -> verify --------------------------------------------------------
    fb = [
        Box("uart", ["UART: порт", "<DRIVER>_CONFIG / _CFG", "+ SER_<порт>_BAUD"], 10, 40, 170, 58, accent=True),
        Box("i2c", ["I²C / SPI:", "SENS_EN_<датчик> = 1…"], 10, 112, 170, 46, accent=True),
        Box("can", ["DroneCAN:", "UAVCAN_ENABLE ≥ 1,", "UAVCAN_SUB_<тип>"], 10, 172, 170, 58, accent=True),
        Box("rb", ["Перезагрузка", "(reboot_required)"], 214, 112, 118, 46),
        Box("rc", ["rc.serial, rc.sensors,", "rcS: uavcan start", "→ драйвер запущен"], 366, 106, 150, 58),
        Box("st", ["<driver> status,", "dmesg"], 556, 40, 152, 46),
        Box("ls", ["listener <топик>,", "uorb top"], 556, 112, 152, 46),
        Box("pf", ["SYS_HAS_NUM_DIST,", "SYS_HAS_NUM_ASPD", "→ preflight"], 556, 172, 152, 58),
    ]
    fl = [
        ("uart", "rb"), ("i2c", "rb"), ("can", "rb"), ("rb", "rc", "", True),
        ("rc", "st"), ("rc", "ls"), ("rc", "pf"),
    ]
    D["px4-periph-enable-flow"] = flow(
        "PX4: подключение периферии — параметр → перезагрузка → проверка", fb, fl, 720, 276,
        notes=[
            (10, 252, "Параметр только разрешает запуск: драйвер стартует скриптом при загрузке, поэтому без перезагрузки ничего не появится.", "m t"),
            (10, 267, "Проверка в два шага: драйвер жив (status) и данные идут (listener: sensor_gps, distance_sensor, differential_pressure).", "m t"),
        ])
