#!/usr/bin/env python3
"""Generate the course diagrams into assets/diagrams/*.svg.

Run: python3 scripts/diagrams/build_diagrams.py   (publish.py calls it; CI checks the output is committed)
Hand-drawn SVGs may also live in assets/diagrams/ — this script only overwrites the ids it owns.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svg import Box, Node, flow, frame, timeline, tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "diagrams"

D: dict[str, str] = {}

# ---------------------------------------------------------------- data-flow diagrams
D["fc-signal-path"] = flow(
    "Путь сигнала в полётном контроллере: от гироскопа до моторов",
    [Box("rx", ["Приёмник", "CRSF/SBUS"], 10, 20, 110), Box("rc", ["RC-команда", "rates, smoothing"], 150, 20, 120),
     Box("gyro", ["Гироскоп", "SPI, 8 кГц"], 10, 110, 110, accent=True), Box("filt", ["Фильтры", "RPM, notch, LPF"], 150, 110, 120, accent=True),
     Box("pid", ["PID", "P I D FF"], 300, 65, 110, accent=True), Box("mix", ["Миксер", "газ+roll+pitch+yaw"], 440, 65, 130),
     Box("esc", ["ESC ×4", "DShot600"], 600, 65, 100), Box("bb", ["Blackbox", "лог 2 кГц"], 300, 160, 110), Box("osd", ["OSD / телеметрия"], 440, 160, 130)],
    [("rx", "rc"), ("rc", "pid", "setpoint"), ("gyro", "filt"), ("filt", "pid", "", True), ("pid", "mix", "pidSum"), ("mix", "esc"),
     ("pid", "bb", "", False, "v"), ("mix", "osd", "", False, "v")],
    720, 230, notes=[(580, 130, "eRPM → RPM-фильтр", "m t", "start")])

D["ardupilot-fast-loop"] = flow(
    "ArduCopter: задачи быстрой петли (Copter.cpp scheduler_tasks[])",
    [Box("ins", ["AP_InertialSensor", "update()"], 10, 30, 150, accent=True), Box("rate", ["run_rate_controller", "AC_PID по осям"], 190, 30, 150, accent=True),
     Box("mot", ["motors_output", "AP_MotorsMatrix"], 370, 30, 150, accent=True), Box("out", ["RCOutput", "DShot/PWM"], 550, 30, 150),
     Box("ahrs", ["read_AHRS", "EKF3"], 10, 120, 150), Box("nav", ["read_inertia", "позиция/скорость"], 190, 120, 150),
     Box("mode", ["update_flight_mode", "angle/pos контуры"], 370, 120, 150), Box("slow", ["Медленные задачи:", "rc 250 Гц, GPS 50,", "батарея 10, геозона 25"], 550, 120, 150, 54)],
    [("ins", "rate"), ("rate", "mot"), ("mot", "out"), ("ahrs", "nav"), ("nav", "mode"), ("mode", "rate", "цель угл. скорости", True, "v")],
    720, 200)

D["estimation-sources"] = flow(
    "Оценка состояния: датчики → EKF → контуры",
    [Box("imu", ["IMU", "гиро + accel"], 10, 20, 120, accent=True), Box("baro", ["Баро"], 10, 80, 120), Box("gps", ["GNSS", "pos/vel"], 10, 140, 120),
     Box("mag", ["Компас"], 10, 200, 120), Box("ext", ["Поток, дальномер,", "ExternalNav"], 10, 260, 120),
     Box("ekf", ["EKF3", "предсказание по IMU,", "коррекция измерениями,", "ворота инноваций"], 200, 110, 170, 90, accent=True),
     Box("att", ["Ориентация", "q, углы"], 430, 40, 120), Box("vel", ["Скорость NED"], 430, 110, 120), Box("pos", ["Позиция NED"], 430, 180, 120), Box("bias", ["Bias гиро/accel", "поле, ветер"], 430, 250, 120),
     Box("ctl", ["Контуры", "rate → angle → pos"], 580, 110, 135)],
    [("imu", "ekf", "1–8 кГц", True), ("baro", "ekf"), ("gps", "ekf", "5–10 Гц"), ("mag", "ekf"), ("ext", "ekf"),
     ("ekf", "att"), ("ekf", "vel"), ("ekf", "pos"), ("ekf", "bias"), ("vel", "ctl", "", True)],
    720, 350)

D["companion-system"] = flow(
    "Companion и полётный контроллер: кто за что отвечает",
    [Box("fc", ["Полётный контроллер", "стабилизация, EKF,", "failsafe, миссии"], 10, 40, 160, 70, accent=True),
     Box("cc", ["Companion", "зрение, планирование,", "ROS 2, сеть"], 330, 40, 160, 70),
     Box("gcs", ["GCS", "оператор"], 590, 40, 120, 70), Box("cam", ["Камера"], 330, 160, 100), Box("net", ["4G / Wi-Fi"], 590, 160, 120)],
    [("cc", "fc", "цели GUIDED / Offboard", True), ("fc", "cc", "телеметрия, статус"), ("cc", "gcs", "видео"),
     ("cam", "cc", "", False, "v"), ("gcs", "net", "", False, "v"), ("net", "cc", "", False, "h")],
    720, 230, notes=[(10, 140, "Правило: companion советует, FC решает;", "m t"), (10, 154, "молчит companion — таймаут GUIDED и failsafe.", "m t")])

D["mavlink-routing"] = flow(
    "Маршрутизация MAVLink на борту",
    [Box("fc", ["FC", "TELEM2 921600"], 10, 70, 110, accent=True), Box("rt", ["mavlink-router", "UART ↔ UDP/TCP"], 180, 70, 150, accent=True),
     Box("gcs", ["QGC / MP", "UDP 14550"], 400, 10, 130), Box("scr", ["Скрипты", "udpin 14551"], 400, 70, 130), Box("log", ["tlog-логгер", "14552"], 400, 130, 130),
     Box("lte", ["4G / Wi-Fi", "→ удалённая GCS"], 580, 10, 130)],
    [("fc", "rt", "", True), ("rt", "gcs"), ("rt", "scr"), ("rt", "log"), ("gcs", "lte")],
    720, 190)

# ---------------------------------------------------------------- power & wiring
D["power-tree"] = flow(
    "Дерево питания борта (пример 6S, цифровое видео, companion)",
    [Box("bat", ["АКБ 6S", "22.2 В, XT60"], 10, 90, 110, accent=True), Box("cap", ["Конденсатор", "1000 мкФ 50 В"], 150, 20, 110),
     Box("esc", ["ESC ×4", "силовая шина"], 150, 90, 110, accent=True), Box("bec5", ["BEC 5 В / 3 А", "(на FC)"], 150, 160, 110), Box("bec9", ["BEC 9 В / 2 А"], 150, 240, 110),
     Box("becc", ["BEC 5 В / 5 А", "отдельный"], 150, 300, 110),
     Box("fc", ["FC + гиро", "0.2 А"], 320, 130, 100), Box("rx", ["Приёмник", "0.2 А"], 320, 185, 100), Box("gps", ["GPS", "0.1 А"], 440, 130, 100),
     Box("vtx", ["Air unit", "1 А"], 320, 240, 100), Box("pi", ["Raspberry Pi", "2–3 А"], 320, 300, 100)],
    [("bat", "cap", "", False, "v"), ("bat", "esc", "", True), ("bat", "bec5", "", False, "v"), ("bat", "bec9", "", False, "v"), ("bat", "becc", "", False, "v"),
     ("bec5", "fc"), ("bec5", "rx"), ("fc", "gps"), ("bec9", "vtx"), ("becc", "pi")],
    720, 370, notes=[(440, 40, "Общая земля звездой от PDB;", "m t"), (440, 54, "силовые + и − скручены;", "m t"), (440, 68, "Pi не от пада FC.", "m t")])

# ---------------------------------------------------------------- protocol frames
D["crsf-frame"] = frame("Кадр CRSF", [("sync 0xC8", 1), ("len", 1), ("type", 1, True, "0x16 каналы, 0x14 link stats"), ("payload", 22, True, "16 каналов × 11 бит"), ("CRC8 0xD5", 1, False, "по type+payload")],
                        note="len = размер кадра − 2; значения каналов: 992 тика = 1500 мкс")
D["mavlink2-frame"] = frame("Кадр MAVLink 2 (12 байт заголовка и CRC + полезная нагрузка + подпись)", [("STX 0xFD", 1), ("len", 1), ("incompat", 1, False, "бит 0 — подпись"), ("compat", 1), ("seq", 1), ("sysid", 1, True), ("compid", 1, True), ("msgid", 3, True), ("payload", 255, True, "до 255, нули в конце обрезаются", "var"), ("CRC16", 2, False, "+ CRC_EXTRA"), ("signature", 13, False, "опционально")],
                            note="CRC — MCRF4XX по кадру без STX, плюс CRC_EXTRA байт сообщения из XML")
D["dshot-frame"] = frame("Кадр DShot", [("газ", 11, True, "48–2047; 1–47 команды; 0 стоп"), ("телеметрия", 1, False, "запрос ответа"), ("CRC", 4)], unit="бит",
                         note="«1» ≈ 75 % периода бита, «0» ≈ 37 %; DShot600: бит 1.67 мкс, кадр 27 мкс; bidirectional — ответ eRPM")
D["sbus-frame"] = frame("Кадр SBUS", [("0x0F", 1), ("каналы 1–16", 22, True, "по 11 бит"), ("флаги", 1, False, "ch17/18, frame lost, failsafe"), ("0x00", 1)],
                        note="100000 бод 8E2, инвертированный UART; кадр каждые 7–14 мс")
D["i2c-transaction"] = frame("Чтение регистра I2C", [("START", 1), ("адрес+W", 8, True), ("ACK", 1), ("регистр", 8), ("ACK", 1), ("re-START", 1), ("адрес+R", 8, True), ("ACK", 1), ("данные", 8, True), ("NACK", 1), ("STOP", 1)], unit="бит",
                             note="Open-drain с подтяжками 2.2–4.7 кОм; NACK на адрес = устройства нет")

# ---------------------------------------------------------------- timelines
D["failsafe-stages"] = timeline("Betaflight failsafe: от потери пакетов до процедуры",
    [("Пакеты RC", [(0, 100, "ок", True), (100, 2000, "нет валидных кадров")]),
     ("Детекция", [(100, 200, "100 мс")]),
     ("Удержание", [(200, 500, "300 мс")]),
     ("Stage 1", [(500, 2000, "failsafe_delay (1.5 с): стики центр, газ 0, ANGLE по rxfail", True)]),
     ("Stage 2", [(2000, 2600, "DROP / LAND / RESCUE", True)])],
    2600, marks=[(100, "последний пакет"), (2000, "Stage 2")])

D["latency-chain"] = timeline("Задержка от стика до мотора (ELRS 250 Гц, типичный 5\")",
    [("Пульт", [(0, 2, "опрос")]), ("Радио", [(2, 6, "пакет 4 мс", True)]), ("RX→FC", [(6, 6.6, "CRSF")]),
     ("RC smoothing", [(6.6, 10.6, "4 мс")]), ("Фильтры", [(10.6, 12.1, "1.5 мс")]), ("PID+ESC", [(12.1, 12.3, "")]),
     ("Мотор τ", [(12.3, 32, "~20 мс", True)])],
    32, marks=[(12.3, "команда ESC")])

D["quadplane-transition"] = timeline("QuadPlane: переход VTOL → крыло",
    [("VTOL-моторы", [(0, 5, "висение", True), (5, 10, "держат, пока нет скорости"), (10, 12, "выкл")]),
     ("Тилт/тяга вперёд", [(5, 10, "разгон, Q_TILT_RATE_UP", True)]),
     ("Airspeed", [(5, 10, "0 → ARSPD_FBW_MIN")]),
     ("Крыло", [(10, 14, "FBWA: рули работают", True)])],
    14, unit="с", marks=[(5, "команда перехода"), (10, "ARSPD_FBW_MIN или Q_TRANSITION_MS")])

# ---------------------------------------------------------------- decision trees
D["arming-tree"] = tree("Не армится — дерево диагностики", Node("root", ["status / OSD:", "какой флаг?"], [
    ("RXLOSS", Node("rx", ["Нет RC"], [("", Node("rx1", ["Бинд, питание RX,", "протокол, инвертор"], leaf=True))])),
    ("THROTTLE/ANGLE", Node("th", ["Стики/наклон"], [("", Node("th1", ["Газ < min_check,", "ровно / small_angle"], leaf=True))])),
    ("DSHOT_TELEM", Node("dt", ["Нет eRPM"], [("", Node("dt1", ["dshot_bidir, ESC fw,", "провода сигнала"], leaf=True))])),
    ("MSP/CLI", Node("msp", ["Подключён", "конфигуратор"], [("", Node("msp1", ["Отключить USB —", "это защита"], leaf=True))])),
    ("ARM_SWITCH", Node("sw", ["Тумблер был", "включён"], [("", Node("sw1", ["Выкл → вкл;", "проверить Modes"], leaf=True))])),
]), width=720)

D["ekf-source-tree"] = tree("Выбор источников EKF3 под сценарий", Node("root", ["Есть GPS", "с хорошим fix?"], [
    ("да", Node("gps", ["POSXY/VELXY = GPS", "POSZ = Baro"], [("помехи", Node("g2", ["+ VELXY поток,", "POSZ дальномер"], leaf=True)), ("нет", Node("g1", ["YAW = компас /", "GPS fallback (3)"], leaf=True))], accent=True)),
    ("нет", Node("nogps", ["Текстурный пол", "и дальномер?"], [("да", Node("flow", ["VELXY поток (5),", "POSZ дальномер (2)"], leaf=True, accent=True)), ("VIO", Node("ext", ["POSXY/VELXY/YAW", "ExternalNav (6)"], leaf=True)), ("ничего", Node("none", ["Stabilize/AltHold;", "без Loiter"], leaf=True))])),
]), width=720)

D["component-choice-tree"] = tree("Подбор силовой установки", Node("r", ["Задача → масса,", "T/W, время"], [
    ("фристайл 5\"", Node("a", ["T/W ≥ 5", "2207 1700–2300KV 6S"], leaf=True)),
    ("long range 7\"", Node("b", ["T/W 3–4", "2806.5 1300KV, Li-Ion"], leaf=True)),
    ("грузовой 10–15\"", Node("c", ["T/W 2–2.5", "4008 380KV, X8, Li-Ion"], leaf=True, accent=True)),
    ("крыло", Node("d", ["по V_s и крейсеру", "тяга 0.4–0.6 веса"], leaf=True)),
]), width=720, gap_y=80)

# ---------------------------------------------------------------- physics (hand-built SVG)
D["quad-forces"] = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 290" width="100%" role="img" aria-labelledby="t" style="max-width:720px;display:block;margin:0 auto">
<title id="t">Силы и моменты квадрокоптера</title>""" + __import__("svg").STYLE + """
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker>
<marker id="ara" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--gc-accent-hud,#5ef1d2)"/></marker></defs>
<g transform="translate(180,150)">
<line class="ln" x1="-110" y1="0" x2="110" y2="0"/><line class="ln" x1="0" y1="-70" x2="0" y2="70"/>
<circle class="box" cx="-110" cy="0" r="10"/><circle class="box" cx="110" cy="0" r="10"/><circle class="box" cx="0" cy="-70" r="10"/><circle class="box" cx="0" cy="70" r="10"/>
<path class="lna" d="M-110 -10 L-110 -55" marker-end="url(#ara)"/><path class="lna" d="M110 -10 L110 -40" marker-end="url(#ara)"/>
<path class="lna" d="M0 -80 L0 -115" marker-end="url(#ara)"/><path class="lna" d="M0 60 L0 25" marker-end="url(#ara)"/>
<text x="-110" y="-62" class="a t">T₃ ↑ больше</text><text x="110" y="-47" class="a t">T₂</text>
<path class="ln" d="M0 10 L0 55" marker-end="url(#ar)"/><text x="18" y="40" class="t" text-anchor="start">m·g</text>
<text x="0" y="105" class="m t">Крен: разность тяг × плечо = момент</text>
<text x="0" y="-130" class="t">вид сзади</text>
</g>
<g transform="translate(540,150)">
<line class="ln" x1="-80" y1="-80" x2="80" y2="80"/><line class="ln" x1="-80" y1="80" x2="80" y2="-80"/>
<circle class="boxa" cx="-80" cy="-80" r="12"/><circle class="box" cx="80" cy="-80" r="12"/><circle class="boxa" cx="80" cy="80" r="12"/><circle class="box" cx="-80" cy="80" r="12"/>
<text x="-80" y="-100" class="t">CCW</text><text x="80" y="-100" class="t">CW</text><text x="80" y="104" class="t">CCW</text><text x="-80" y="104" class="t">CW</text>
<path class="lna" d="M-60 -95 A75 75 0 0 1 60 -95" marker-end="url(#ara)"/>
<text x="0" y="-5" class="t">yaw</text>
<text x="0" y="125" class="m t">Рыскание: пара CCW быстрее →</text><text x="0" y="139" class="m t">реактивный момент не скомпенсирован</text>
<text x="0" y="-125" class="t">вид сверху</text>
</g>
</svg>
"""

D["actuator-disk"] = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 220" width="100%" role="img" aria-labelledby="t" style="max-width:720px;display:block;margin:0 auto">
<title id="t">Диск-актуатор: тяга как изменение импульса воздуха</title>""" + __import__("svg").STYLE + """
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker></defs>
<rect class="boxa" x="300" y="40" width="120" height="8" rx="3"/><text x="360" y="32" class="t">проп = диск площадью A</text>
<path class="lnm" d="M250 60 C 280 90, 290 150, 300 200"/><path class="lnm" d="M470 60 C 440 90, 430 150, 420 200"/>
<g class="m"><path class="ln" d="M330 70 L330 110" marker-end="url(#ar)"/><path class="ln" d="M360 70 L360 110" marker-end="url(#ar)"/><path class="ln" d="M390 70 L390 110" marker-end="url(#ar)"/></g>
<path class="ln" d="M330 130 L330 190" marker-end="url(#ar)"/><path class="ln" d="M360 130 L360 190" marker-end="url(#ar)"/><path class="ln" d="M390 130 L390 190" marker-end="url(#ar)"/>
<text x="440" y="100" class="t" text-anchor="start">V₀ (набегающий, 0 на висении)</text>
<text x="440" y="170" class="t" text-anchor="start">Vₑ (за диском)</text>
<text x="20" y="80" class="b" text-anchor="start">F = ½·ρ·A·(Vₑ² − V₀²)</text>
<text x="20" y="104" class="m t" text-anchor="start">Тяга ~ импульс (~V), мощность ~ энергия (~V²):</text>
<text x="20" y="120" class="m t" text-anchor="start">большой диск при той же тяге тратит меньше мощности.</text>
<text x="20" y="150" class="m t" text-anchor="start">Cт = T/(ρ·n²·D⁴) — тяга ~ n²</text>
<text x="20" y="166" class="m t" text-anchor="start">Cₚ = P/(ρ·n³·D⁵) — мощность ~ n³</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in D.items():
        (OUT / f"{name}.svg").write_text(content, encoding="utf-8")
    print(f"diagrams: {len(D)} written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
