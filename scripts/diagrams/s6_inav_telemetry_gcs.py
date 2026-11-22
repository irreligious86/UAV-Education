"""Stage 6 diagrams for module inav-telemetry-gcs (INAV 9.1.0 telemetry, MSP RC and ground stations).

inav-telemetry-port-map     — protocol -> serial function (bit value from io/serial.h) -> consumer, with the
                              sharing rules of isSerialConfigValid() as notes.
chart-inav-mavlink-budget   — nominal MAVLink 2 byte budget from the module's formula
                              55*ext + 54*rc + 136*pos + 40*extra1 + 32*extra2 + 94*extra3 + 45 (bytes/s):
                              sweep of mavlink_pos_rate and of mavlink_extra1_rate with the other rates at
                              their defaults (2, 1, 2, 2, 2, 1 -> 719 B/s), against the link capacities of the
                              practice step 2 (SiK 2880 B/s; ELRS 4.1.0 1:2 at 500 / 250 / 150 Hz:
                              1240 / 615 / 365 B/s).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def _budget(ext=2, rc=1, pos=2, e1=2, e2=2, e3=1) -> int:
    return 55 * ext + 54 * rc + 136 * pos + 40 * e1 + 32 * e2 + 94 * e3 + 45


def _elrs_bytes(hz: int, ratio: int, full: bool = False) -> float:
    burst = 512 * hz // ratio // 1000
    burst = burst - 1 if burst > 1 else 1
    bps = (10 if full else 5) * 8 * burst * hz // ratio // (burst + 1)
    if full:
        bps += 48
    return bps / 8


def build(D: dict) -> None:
    w, h = 205, 40
    rows = [
        ("crsf", ["CRSF-телеметрия", "+ MSP в кадрах 0x7A–7C"], "p_rx", ["RX_SERIAL · 64", "420000, порт приёмника"], "c_tx", ["Пульт EdgeTX", "сенсоры, FM, Lua"]),
        ("sp", ["SmartPort", "по опросу, + MSP"], "p_sp", ["SMARTPORT · 32", "57600, один провод TX"], "c_fr", ["Приёмник FrSky", "пульт, Lua-панели"]),
        ("ltm", ["LTM", "только вниз, 105–303 Б/с"], "p_ltm", ["LTM · 16", "AUTO = 19200"], "c_tr", ["Антенный трекер", "OSD, наземка LTM"]),
        ("mav", ["MAVLink 1 / 2", "потоки + узкий приём"], "p_mav", ["MAVLINK · 256", "AUTO = 57600"], "c_gcs", ["Наземка MAVLink", "компаньон, ADS-B"]),
        ("msp", ["MSP", "запрос — ответ"], "p_msp", ["MSP · 1", "не больше 3 портов"], "c_cfg", ["Configurator, BLE/Wi-Fi", "скрипт MSP RC"]),
    ]
    boxes, links = [], []
    for i, (a, al, b, bl, c, cl) in enumerate(rows):
        y = 14 + i * 54
        boxes += [Box(a, al, 10, y, w, h), Box(b, bl, 258, y, w, h, accent=True), Box(c, cl, 506, y, w, h)]
        links += [(a, b, "", False, "h"), (b, c, "", i in (3, 4), "h")]
    D["inav-telemetry-port-map"] = flow(
        "INAV 9.1: протокол → функция порта → кто читает",
        boxes, links, 722, 350,
        notes=[(10, 296, "Пара на одном UART: MSP + одна телеметрия (идёт в арме) или RX_SERIAL + LTM / IBUS.", "m t"),
               (10, 312, "Любая другая пара или четвёртый MSP-порт — сброс всей таблицы портов.", "w t"),
               (10, 328, "Без feature TELEMETRY молчат все протоколы, кроме MSP.", "m t")])

    rates = list(range(0, 11))
    pos = [_budget(pos=r) for r in rates]
    att = [_budget(e1=r) for r in rates]
    assert _budget() == 719 and _budget(pos=5, e1=10) == 1447 and _budget(1, 0, 1, 1, 1, 1) == 402
    caps = {"SiK 57600, половина": 2880.0, "ELRS 500 Гц 1:2": _elrs_bytes(500, 2),
            "ELRS 250 Гц 1:2": _elrs_bytes(250, 2), "ELRS 150 Гц 1:2": _elrs_bytes(150, 2)}
    assert [round(v) for v in caps.values()] == [2880, 1240, 615, 365]
    D["chart-inav-mavlink-budget"] = chart(
        "Бюджет MAVLink 2 в INAV 9.1: цена одного герца потока",
        [dict(name="меняем mavlink_pos_rate", xs=rates, ys=pos, cls="a", label_at=8, label_dy=-10),
         dict(name="меняем mavlink_extra1_rate", xs=rates, ys=att, cls="m", dash=True, label_at=9, label_dy=16)],
        Axis("частота потока в настройке, Гц", 0, 10), Axis("номинальный бюджет, байт/с", 0, 3200),
        hmarks=[(v, f"{k}: {v:.0f}", "w") for k, v in caps.items()],
        marks=[(2, "умолчание: 719", "ink", 150)],
        notes=[(198, 294, "Остальные потоки — по умолчанию (2, 1, 2, 2, 2, 1).", "m"),
               (198, 307, "Позиция: 136 байт/с на герц, ATTITUDE: 40.", "m")])
