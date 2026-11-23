"""Visual pass (stage 7), batch v3_comp_mav: one new diagram per companion / embedded / MAVLink / engineering module.

mav-cmd-ack-flow            comp-mavlink — the module's worked cmd() helper as a flow: COMMAND_LONG, wait for a
                            COMMAND_ACK of the same command for up to 1 s, ACCEPTED (0) -> done, IN_PROGRESS (5) -> keep
                            waiting, any other result (1–4, 6–10 of MAV_RESULT) -> exception, reason in STATUSTEXT «PreArm: …»; no ACK ->
                            resend, after 3 tries -> TimeoutError.
rpi-throttled-bits          comp-raspberry — the vcgencmd get_throttled bit mask of the module: bits 0–3 «now»
                            (under-voltage, frequency capped, throttled, soft temperature limit), bits 16–19 the same
                            «since boot»; the module's values 0x0, 0x50000 and 0x50005 decoded bit by bit.
esp32-tx-companion-states   comp-esp32 — the TX16S companion worked example as a state machine: Lua sends S-lines every
                            500 ms (tick() from refresh() and background()); FLIGHT (radio off) by default and on > 2 s
                            without lines; GROUND after armed=0 for >= 3 s (Wi-Fi AP, STAGE -> APPLY into NVS with a
                            backup); any armed=1 -> FLIGHT; Lua blocks APPLY when telemetry shows arm.
emb-blocking-timeline       emb-basics — why blocking in the main loop is an accident: a control task that waits 50 ms
                            for UART misses 50 ms × 8 kHz = 400 cycles; the correct variant keeps the 125 us cycle and
                            reads data the UART ISR / DMA already put into the ring buffer.
chart-bus-imu-read-time     emb-protocols — time to move a 14-byte IMU block on each bus, from the frame rules of the
                            module: SPI (1 + 14) bytes × 8 clocks; I2C register read (3 + 14) bytes × 9 clocks + START,
                            repeated START, STOP; UART 10 bits per byte (8N1); against the 125 us cycle of 8 kHz.
fw-gyro-motor-paths         fw-reading — the gyro -> motors path in both code bases, stage by stage with the file to
                            open: scheduler, gyro + filters, rate PID, mixer, output. The PID row is highlighted: D from
                            the filtered gyro in Betaflight, D from the error through FLTD in ArduPilot.
ci-sitl-failsafe-seq        eng-ci-configs — the module's SITL autotest as a message sequence: SITL with
                            --add-param-file, GUIDED + arm, takeoff 10 m, SIM_RC_FAIL = 1, RTL/LAND expected within 5 s
                            (assert -> red CI if failsafe is broken), then a separate run: 4-waypoint mission.
eng-trace-chain             eng-systems — the trace chain of the worked FMEA row «new firmware renamed parameters»
                            (S 9 · O 3 · D 8 = RPN 216): measure -> requirement R-PRC-02 -> test check_params.py -> test
                            record (date, tag, log, verdict) -> trace matrix; RPN recalculated after the measure,
                            incident review adds a row; empty matrix cells = open requirements.
mav-rx-frame-flow           mav-protocol — what a receiver does with incoming bytes, in the module's terms: STX, unknown
                            incompat bit, len + 2 (+13), CRC-16/MCRF4XX + CRC_EXTRA (silent drop = dialect mismatch),
                            signature and timestamp (with the unsigned exceptions: channel 0, RADIO_STATUS, 4.7+
                            MAVn_OPTIONS bit 0 — GCS_Signing.cpp), seq loss count per sysid/compid, zero padding.
mav-forward-tree            mav-routing — the forwarding rules of MAVLink_routing.cpp forward() as the module states them:
                            broadcast -> ports with any learned route; foreign sysid -> ports where it was seen; own
                            sysid with target_component 0 / absent -> ports where any own-sysid component was seen
                            (+ local); own sysid with a component -> ports where that pair was seen.
mav-rangefinder-timeout     mav-component — AP_RANGEFINDER_MAVLINK_TIMEOUT_MS = 500: a component that stops sending is
                            dropped 0.5 s later; one that repeats its last value is never dropped; ~2 Hz with one lost
                            packet gives a 1 s gap and a healthy / no-data flicker.
mav-offboard-loss-timeline  mav-sdk — the practice step 3 (kill -9 of the offboard script) on a time axis: PX4 leaves
                            Offboard after COM_OF_LOSS_T = 1 s (COM_OBL_RC_ACT 0 = Position; without RC NAV_RCL_ACT
                            2 = Return), ArduPilot stays in GUIDED and zeroes the velocity target after GUID_TIMEOUT = 3 s.
chart-fleet-min-separation  mav-multi-vehicle — the module's separation rule d = 2v·(t_tel + t_dec + t_brake) + 2·e for
                            t_tel 0.2 / 0.5 / 1 s, t_dec 0.5 s, t_brake 1.5 s, e = 3 m; the worked 10 m/s case 56 m
                            («около 60») and the lab threshold MIN_H = 15 m, enough only below ~1.8 m/s.
"""
from __future__ import annotations

import math
import re

from plot import Axis, chart
from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, Node, flow, sequence, svg, text, tree


# ---------------------------------------------------------------- small helpers for hand-placed diagrams
def _rect(x, y, w, h, cls="box", rx=6, extra=""):
    return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"{extra}/>'


def _arrow(d, acc=False, extra=""):
    return f'<path class="{"lna" if acc else "ln"}" d="{d}" marker-end="url(#{"ara" if acc else "ar"})"{extra}/>'


def _vlabels_beside(svg_str: str) -> str:
    """flow() centres link labels on x + 6, so on a vertical link the label sits on the line; start them beside it."""
    return svg_str.replace('text-anchor="middle" class="m t" style="font-size:10px"',
                           'text-anchor="start" class="m t" style="font-size:10px"')


def _add_footer(svg_str: str, lines: list[str], lh: int = 16) -> str:
    """Grow a helper-built SVG downwards and add muted footnote lines under it."""
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    nh = h + lh * len(lines) + 6
    body = "".join(text(16, h + 4 + lh * (i + 1) - 4, s, "m t", "start") for i, s in enumerate(lines))
    svg_str = svg_str.replace(m.group(0), f'viewBox="0 0 {w:g} {nh:g}"', 1)
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


# ---------------------------------------------------------------- comp-mavlink
def cmd_ack_flow() -> str:
    x0, w = 10, 330
    boxes = [
        Box("s", ["Попытка k из 3: COMMAND_LONG", "(target_system, target_component, cmd)"], x0, 36, w, 46, accent=True),
        Box("w", ["Ждать COMMAND_ACK до 1 с", "(timeout = 1.0)"], x0, 112, w, 46),
        Box("c", ["ack.command == cmd?"], x0, 188, w, 38),
        Box("r", ["ack.result?"], x0, 256, w, 38),
        Box("ok", ["0 ACCEPTED → return True"], x0, 324, w, 38, accent=True),
        Box("to", ["Нет ACK за 1 с:", "k < 3 → повтор, k = 3 → TimeoutError"], 410, 112, 300, 46),
        Box("oth", ["ACK другой команды:", "не наш — ждать дальше"], 410, 185, 300, 44),
        Box("ip", ["5 IN_PROGRESS: ждать дальше", "в том же окне 1 с"], 410, 246, 300, 44),
        Box("rej", ["любой другой код (1–4, 6–10:", "отказ, ошибка…) → RuntimeError"], 410, 306, 300, 44),
    ]
    links = [("s", "w", "", True, "v"), ("w", "c", "ACK пришёл", False, "v"), ("c", "r", "да", False, "v"),
             ("r", "ok", "", True, "v"), ("w", "to", "", False, "h"), ("c", "oth", "нет", False, "h"),
             ("r", "ip", "", False, "h"), ("r", "rej", "", False, "h")]
    notes = [(10, 20, "Надёжная команда из модуля: cmd(m, command, *params, retries=3, timeout=1.0)", "m t"),
             (420, 368, "причина отказа — в STATUSTEXT:", "m t"), (420, 384, "«PreArm: …»", "m t")]
    out = _vlabels_beside(flow("Команда с проверкой COMMAND_ACK", boxes, links, 720, 396, notes=notes))
    # retry loop: from the timeout box back to the send box (drawn by hand, the helper routes only straight links)
    loop = _arrow("M560 112 L560 59 L340 59", extra=' style="stroke-dasharray:5 4"')
    lab = text(450, 52, "повтор", "m t", "middle", 10)
    i = out.rfind("</svg>")
    return out[:i] + loop + lab + out[i:]


# ---------------------------------------------------------------- comp-raspberry
def throttled_bits() -> str:
    names = {0: ["просадка", "питания"], 1: ["частота", "ограни-", "чена"], 2: ["троттлинг"], 3: ["мягкий", "темп.", "предел"]}
    values = [("0x0", 0x0, "всё хорошо"),
              ("0x50000", 0x50000, "была просадка и троттлинг (с загрузки)"),
              ("0x50005", 0x50005, "просадка и троттлинг прямо сейчас")]
    bit = lambda v, b: (v >> b) & 1
    assert [b for b in range(20) if bit(0x50000, b)] == [16, 18]
    assert [b for b in range(20) if bit(0x50005, b)] == [0, 2, 16, 18]
    W, L, bw, gap, top = 720, 96, 70, 64, 84
    hi_bits, lo_bits = [19, 18, 17, 16], [3, 2, 1, 0]
    xs, x = {}, L
    for b in hi_bits:
        xs[b] = x
        x += bw
    x_gap = x
    x += gap
    for b in lo_bits:
        xs[b] = x
        x += bw
    out = [text(16, 18, "vcgencmd get_throttled: биты 0–3 — «сейчас», биты 16–19 — то же «было с загрузки»", "m t", "start")]
    out.append(text((xs[19] + xs[16] + bw) / 2, top - 38, "было с момента загрузки", "a t b", "middle", 11))
    out.append(text((xs[3] + xs[0] + bw) / 2, top - 38, "происходит сейчас", "w t b", "middle", 11))
    for b in hi_bits + lo_bits:
        out.append(text(xs[b] + bw / 2, top - 14, f"бит {b}", "m t", "middle", 11))
    out.append(text(x_gap + gap / 2, top - 14, "15–4", "m t", "middle", 11))
    mh = 54
    for b in hi_bits + lo_bits:
        lines = names[b - 16 if b >= 16 else b]
        out.append(_rect(xs[b] + 2, top, bw - 4, mh, "box", 4))
        y0 = top + mh / 2 - (len(lines) - 1) * 6.5 + 4
        for k, s_ in enumerate(lines):
            out.append(text(xs[b] + bw / 2, y0 + k * 13, s_, "", "middle", 10.5))
    out.append(text(x_gap + gap / 2, top + mh / 2 + 4, "…", "m", "middle"))
    ry0, rh = top + mh + 22, 36
    for k, (label, v, meaning) in enumerate(values):
        y = ry0 + k * (rh + 26)
        out.append(text(L - 10, y + 23, label, "b", "end", 12))
        for b in hi_bits + lo_bits:
            on = bit(v, b)
            st = "" if on else ' style="opacity:0.45"'
            out.append(_rect(xs[b] + 2, y, bw - 4, rh, "boxa" if on else "box", 4, st))
            out.append(text(xs[b] + bw / 2, y + 23, str(on), "a b" if on else "m", "middle", 13))
        out.append(text(x_gap + gap / 2, y + 23, "0…0", "m", "middle", 12))
        out.append(text(L, y + rh + 15, f"{label}: {meaning}", "m t", "start", 11))
    H = ry0 + 3 * (rh + 26) + 10
    out.append(text(16, H - 2, "Цифра hex = 4 бита: «5» в старшей тетраде — биты 16 и 18, в младшей — биты 0 и 2", "m t", "start"))
    return svg(W, H + 8, "Битовая маска vcgencmd get_throttled", "".join(out))


# ---------------------------------------------------------------- comp-esp32
def tx_companion_states() -> str:
    W, H = 720, 376
    out = [text(16, 18, "Компаньон TX16S: радио включается только по явному «disarmed» от пульта", "m t", "start")]
    # the Lua side, top right
    out.append(_rect(232, 36, 252, 70, "box"))
    out.append(text(358, 55, "Lua на пульте (AUX, режим Lua)", "b", "middle", 11))
    out.append(text(358, 73, "tick() из refresh() и background():", "", "middle", 10.5))
    out.append(text(358, 89, "шлёт, даже когда виджет скрыт", "m t", "middle", 10.5))
    out.append(_arrow("M484 60 L512 60"))
    out.append(_rect(514, 36, 196, 70, "box"))
    out.append(text(612, 54, "каждые 500 мс:", "m t", "middle", 10.5))
    out.append(text(612, 70, "S,<mode>,<armed>,", "", "middle", 10.5))
    out.append(text(612, 85, "<vbat>,<rssi>\\n", "", "middle", 10.5))
    # states
    fx, gx, sy, sw, sh = 20, 470, 140, 230, 110
    out.append(_rect(fx, sy, sw, sh, "boxa", 10))
    out.append(text(fx + sw / 2, sy + 24, "FLIGHT", "a b", "middle", 14))
    for i, s_ in enumerate(["радио выключено:", "WiFi.mode(WIFI_OFF)", "+ esp_wifi_stop()", "настройки недоступны"]):
        out.append(text(fx + sw / 2, sy + 46 + i * 16, s_, "" if i else "m t", "middle", 11))
    out.append(_rect(gx, sy, sw, sh, "box", 10))
    out.append(text(gx + sw / 2, sy + 24, "GROUND", "b", "middle", 14))
    for i, s_ in enumerate(["Wi-Fi AP, веб-настройки", "STAGE: JSON в RAM", "APPLY: запись NVS", "с копией прошлой версии"]):
        out.append(text(gx + sw / 2, sy + 46 + i * 16, s_, "", "middle", 11))
    # ESP32 container: the S-lines reach it in both states
    out.append(f'<rect x="10" y="124" width="700" height="158" rx="12" fill="none" stroke="{MUTED}" stroke-width="1" stroke-dasharray="5 4"/>')
    out.append(_arrow("M612 106 L612 124"))
    out.append(text(fx + 4, 272, "ESP32-S3 (строки читает в обоих состояниях)", "m t", "start", 10.5))
    # start: a dot above FLIGHT
    cx = fx + sw / 2
    out.append(f'<circle cx="{cx}" cy="86" r="5" fill="{ACCENT}"/>')
    out.append(text(cx, 70, "старт, неопределённость", "a t", "middle", 10.5))
    out.append(_arrow(f"M{cx} 91 L{cx} {sy}", True))
    # FLIGHT -> GROUND (top lane) and back (bottom lane)
    y1, y2 = sy + 34, sy + 78
    mx = (fx + sw + gx) / 2
    out.append(_arrow(f"M{fx + sw} {y1} L{gx} {y1}"))
    out.append(text(mx, y1 - 8, "armed=0 ≥ 3 с подряд", "t", "middle", 10.5))
    out.append(_arrow(f"M{gx} {y2} L{fx + sw} {y2}", True))
    out.append(text(mx, y2 - 8, "любое armed=1", "a t", "middle", 10.5))
    out.append(text(mx, y2 + 16, "или нет строк > 2 с", "a t", "middle", 10.5))
    # APPLY guard, attached to GROUND
    out.append(f'<line class="lnm" x1="{gx + sw / 2}" y1="{sy + sh}" x2="{gx + sw / 2}" y2="292"/>')
    out.append(_rect(gx - 30, 292, sw + 30, 54, "box"))
    out.append(text(gx - 15 + sw / 2, 310, "APPLY — только в GROUND;", "", "middle", 10.5))
    out.append(text(gx - 15 + sw / 2, 325, "Lua блокирует при арме в", "", "middle", 10.5))
    out.append(text(gx - 15 + sw / 2, 340, "телеметрии, прошивка ESP32 тоже", "", "middle", 10.5))
    out.append(text(16, H - 8, "Heartbeat только в refresh() → пилот сменил экран, строки пропали, через 2 с ESP32 ушёл в FLIGHT", "m t", "start"))
    return svg(W, H, "Состояния компаньона пульта на ESP32", "".join(out))


# ---------------------------------------------------------------- emb-basics
def blocking_timeline() -> str:
    W, L, R = 720, 150, 20
    t_max = 60.0
    X = lambda t: L + (W - L - R) * t / t_max
    f_loop, wait_ms = 8000, 50
    lost = round(wait_ms / 1000 * f_loop)
    assert lost == 400 and 1e6 / f_loop == 125
    t0 = 5.0                                                  # the moment the task starts to wait (schematic)
    top, lh = 50, 52
    out = [text(16, 18, f"Задача управления ждёт UART {wait_ms} мс: {wait_ms} мс × 8 кГц = {lost} пропущенных циклов", "m t", "start")]
    lanes = ["Блокирующий цикл", "Правильный цикл", "UART: ISR / DMA"]
    for i, name in enumerate(lanes):
        y = top + i * lh
        out.append(text(L - 10, y + 22, name, "", "end", 11.5))

    def cycles(a, b, y, cls="boxa"):
        # one band = many 125 us cycles; tick marks every 1 ms show the cadence (8 cycles per tick)
        s = [_rect(X(a), y + 6, X(b) - X(a), 26, cls, 3)]
        s += [f'<line x1="{X(t):.1f}" y1="{y + 8}" x2="{X(t):.1f}" y2="{y + 30}" stroke="{ACCENT}" stroke-width="0.6" opacity="0.6"/>'
              for t in [a + k for k in range(int(b - a) + 1)] if t <= b]
        return s

    y = top
    out += cycles(0, t0, y)
    out.append(f'<rect x="{X(t0):.1f}" y="{y + 6}" width="{X(t0 + wait_ms) - X(t0):.1f}" height="26" rx="3" fill="{DANGER}" opacity="0.18" stroke="{DANGER}"/>')
    out.append(text((X(t0) + X(t0 + wait_ms)) / 2, y + 24, f"ждёт байты UART: {lost} циклов не выполнено", "d b", "middle", 11))
    out += cycles(t0 + wait_ms, t_max, y)
    y = top + lh
    out += cycles(0, t_max, y)
    out.append(_rect(X(18), y + 9, X(42) - X(18), 20, "box", 3, ' style="opacity:0.92"'))
    out.append(text(X(30), y + 23, "каждые 125 мкс: читает готовое", "", "middle", 10.5))
    y = top + 2 * lh
    for t in [2, 9, 16, 51, 58]:            # schematic: bytes arrive while the cycle runs
        out.append(f'<line x1="{X(t):.1f}" y1="{y + 8}" x2="{X(t):.1f}" y2="{y + 30}" stroke="{INK}" stroke-width="1.6"/>')
    out.append(text(X(33.5), y + 23, "байт → ISR → кольцевой буфер", "", "middle", 10.5))
    # consequences, attached to the moment the blocking loop resumes
    xr = X(t0 + wait_ms)
    out.append(f'<line class="lnm" x1="{xr:.1f}" y1="{top + 4}" x2="{xr:.1f}" y2="{top - 10}"/>')
    out.append(text(xr - 4, top - 14, "снова считает: гироскоп устарел → скачок D, моторы дёргают", "d t", "end", 10.5))
    # axis, drawn under the lanes (no grid through the labels)
    ay = top + 3 * lh + 6
    out.append(f'<line class="ln" x1="{X(0):.1f}" y1="{ay}" x2="{X(t_max):.1f}" y2="{ay}"/>')
    for t in range(0, 61, 10):
        out.append(f'<line class="ln" x1="{X(t):.1f}" y1="{ay - 4}" x2="{X(t):.1f}" y2="{ay + 4}"/>')
        out.append(text(X(t), ay + 18, f"{t}", "m t", "middle", 11))
    out.append(text(X(30), ay + 34, "время, мс (риска на полосе — 1 мс = 8 циклов)", "m t", "middle", 11))
    H = ay + 80
    out.append(text(16, H - 22, "Правило: контур управления не ждёт ничего — байты собирает прерывание или DMA, цикл берёт готовое.", "m t", "start"))
    out.append(text(16, H - 6, "В худшем случае зависание кончается сбросом по watchdog прямо в полёте.", "m t", "start"))
    return svg(W, H, "Блокировка в основном цикле против прерывания", "".join(out))


# ---------------------------------------------------------------- emb-protocols
def bus_imu_read_time() -> str:
    n = 14                                                    # IMU burst: 14 bytes (emb-basics, emb-protocols)
    spi = lambda f: (1 + n) * 8 / f * 1e6                    # address byte + 14 data bytes, 8 clocks each
    i2c = lambda f: ((3 + n) * 9 + 3) / f * 1e6              # addr+W, reg, addr+R + 14 data, 9 clocks each; START, Sr, STOP
    uart = lambda baud: n * 10 / baud * 1e6                  # 8N1: 10 bits per byte
    rows = [("SPI 24 МГц", spi(24e6), "a"), ("SPI 8 МГц", spi(8e6), "a"),
            ("I2C 1 МГц", i2c(1e6), "w"), ("I2C 400 кГц", i2c(400e3), "w"), ("I2C 100 кГц", i2c(100e3), "w"),
            ("UART 921600", uart(921600), "ink"), ("UART 115200", uart(115200), "ink")]
    assert round(spi(8e6)) == 15 and round(i2c(400e3)) == 390 and round(i2c(1e6)) == 156
    assert round(uart(115200)) == 1215 and round(uart(921600)) == 152
    W, L, R, top, rh = 720, 120, 30, 50, 34
    lo, hi = 1.0, 3000.0
    X = lambda us: L + (W - L - R) * (math.log10(us) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    out = [text(16, 18, f"Сколько идёт блок IMU из {n} байт по шине (такты по правилам кадра, без пауз)", "m t", "start")]
    budget = 125.0
    yb = top + len(rows) * rh
    for i, (name, us, cls) in enumerate(rows):
        y = top + i * rh
        out.append(text(L - 10, y + 21, name, "", "end", 11.5))
        col = {"a": ACCENT, "w": WARN, "ink": INK}[cls]
        out.append(f'<rect x="{L}" y="{y + 7}" width="{X(us) - L:.1f}" height="20" rx="2" fill="{col}" opacity="0.35" stroke="{col}"/>')
        lab = f"{us:.0f} мкс" if us < 1000 else f"{us / 1000:.2f} мс"
        out.append(text(X(us) + 6, y + 21, lab, "b t", "start", 11))
    # 125 us budget line
    out.append(f'<line x1="{X(budget):.1f}" y1="{top - 6}" x2="{X(budget):.1f}" y2="{yb + 2}" stroke="{DANGER}" stroke-width="1.4" stroke-dasharray="5 3"/>')
    out.append(text(X(budget) + 4, top - 10, "весь цикл 8 кГц — 125 мкс", "d t", "start", 11))
    # log axis
    out.append(f'<line class="ln" x1="{L}" y1="{yb + 4}" x2="{W - R}" y2="{yb + 4}"/>')
    for v, s in [(1, "1"), (3, "3"), (10, "10"), (30, "30"), (100, "100"), (300, "300"), (1000, "1000"), (3000, "3000")]:
        out.append(f'<line class="ln" x1="{X(v):.1f}" y1="{yb}" x2="{X(v):.1f}" y2="{yb + 8}"/>')
        out.append(text(X(v), yb + 22, s, "m t", "middle", 11))
    out.append(text((L + W - R) / 2, yb + 38, "время, мкс (логарифмическая шкала: каждая риска — ×3 или ×3.3)", "m t", "middle", 11))
    H = yb + 104
    out.append(text(16, H - 38, "SPI: (1 + 14) байт × 8 тактов.  I2C: (адрес+W, регистр, адрес+R + 14) байт × 9 тактов", "m t", "start"))
    out.append(text(16, H - 22, "(8 бит + ACK) + START, повторный START, STOP.  UART 8N1: 10 бит на байт.", "m t", "start"))
    out.append(text(16, H - 6, "Гироскоп на 8 кГц живёт только на SPI: даже I2C 1 МГц не укладывается в цикл.", "m t", "start"))
    return svg(W, H, "Время чтения блока IMU по разным шинам", "".join(out))


# ---------------------------------------------------------------- fw-reading
def gyro_motor_paths() -> str:
    lx, rx, w, h, step, top = 10, 370, 340, 50, 66, 56
    bf = [("Планировщик: TASK_GYRO, TASK_PID", "scheduler/scheduler.c, fc/tasks.c"),
          ("Гироскоп: LPF2, RPM, notch 1–2, LPF1, dyn", "sensors/gyro.c, gyro_filter_impl.c"),
          ("PID: D от гироскопа (D-LPF до производной)", "flight/pid.c  pidController()"),
          ("Миксер: pidSum × матрица + газ", "flight/mixer.c  mixTable()"),
          ("DShot: таймер + DMA", "drivers/dshot.c, src/platform/…/dshot_*.c")]
    ap = [("Планировщик: FAST_TASK по порядку", "ArduCopter/Copter.cpp  scheduler_tasks[]"),
          ("IMU: гармонический notch, LPF", "AP_InertialSensor, Filter/HarmonicNotch…"),
          ("Rate PID: D от ошибки через FLTD", "AC_PID/AC_PID.cpp  update_all()"),
          ("Миксер: roll/pitch → yaw → газ", "AP_MotorsMatrix  output_armed_stabilizing()"),
          ("Вывод: DShot / PWM", "SRV_Channel → AP_HAL RCOutput")]
    boxes, links = [], []
    for col, (x, rows, p) in enumerate(((lx, bf, "b"), (rx, ap, "a"))):
        for i, (what, where) in enumerate(rows):
            boxes.append(Box(f"{p}{i}", [what, where], x, top + i * step, w, h, accent=(i == 2)))
            if i:
                links.append((f"{p}{i - 1}", f"{p}{i}", "", i == 2, "v"))
    H = top + 5 * step + 30
    notes = [(lx, 22, "Путь гироскоп → моторы: где открыть файл (в блоке: что ищешь, под ним — файл)", "m t"),
             (lx, 44, "Betaflight: src/main/", "b"), (rx, 44, "ArduPilot: libraries/, ArduCopter/", "b"),
             (lx, H - 10, "Выделено: место D-составляющей — то, что нельзя переносить с одной прошивки на другую", "m t")]
    return flow("Путь гироскоп → моторы в Betaflight и ArduPilot", boxes, links, 720, H, notes=notes)


# ---------------------------------------------------------------- eng-ci-configs
def ci_sitl_seq() -> str:
    steps = [(0, 0, "sim_vehicle.py --add-param-file params.param"),
             (0, 1, "режим GUIDED, арм (COMMAND_LONG)"),
             (1, 0, "COMMAND_ACK ACCEPTED", False, True),
             (0, 1, "взлёт на 10 м (MAV_CMD_NAV_TAKEOFF)"),
             (1, 0, "GLOBAL_POSITION_INT: 10 м", False, True),
             (0, 1, "PARAM_SET SIM_RC_FAIL = 1 — пульт «пропал»", True),
             (1, 0, "HEARTBEAT: режим RTL или LAND за ≤ 5 с", True, True),
             (0, 0, "отдельный прогон: SIM_RC_FAIL = 0"),
             (0, 1, "миссия из 4 точек, AUTO"),
             (1, 0, "все 4 точки достигнуты", False, True)]
    notes = [(2, "assert арм"), (4, "assert высота"), (6, "assert: нет → CI красный"),
             (9, "assert: миссия пройдена")]
    s = sequence("SITL-автотест в CI: падает, если failsafe сломан (2–4 мин)", ["sitl_test.py", "SITL ArduCopter"],
                 steps, width=720, step_h=30, notes=notes)
    return _add_footer(s, ["Сломан failsafe (FS_THR_ENABLE = 0 или параметр переименован) → режим за 5 с",
                           "не сменился → assert падает → CI красный, PR не сливается"])


# ---------------------------------------------------------------- eng-systems
def trace_chain() -> str:
    S, O, Dd = 9, 3, 8
    assert S * O * Dd == 216
    w, h = 214, 74
    xs = [10, 253, 496]
    y1, y2 = 64, 200
    boxes = [
        Box("f", ["FMEA: прошивка сменила", "имена параметров", f"S {S} · O {O} · D {Dd} = RPN {S * O * Dd}"], xs[0], y1, w, h, accent=True),
        Box("m", ["Мера: инварианты в CI,", "diff параметров", "после обновления"], xs[1], y1, w, h),
        Box("r", ["Требование R-PRC-02:", "ID, критерий, метод,", "источник, владелец"], xs[2], y1, w, h),
        Box("t", ["Тест: check_params.py", "(метод: анализ", "конфига в CI)"], xs[2], y2, w, h),
        Box("rec", ["Запись теста: дата,", "тег конфига, лог,", "вердикт"], xs[1], y2, w, h),
        Box("mx", ["Матрица трассировки:", "требование ↔ тест", "↔ результат"], xs[0], y2, w, h, accent=True),
    ]
    links = [("f", "m"), ("m", "r"), ("r", "t", "", False, "v"), ("t", "rec"), ("rec", "mx")]
    H = 336
    yl = y1 + h + 50                                          # the feedback line
    notes = [(10, 20, "Строка FMEA превращается в требование, тест и запись — цепочку можно пройти в обе стороны", "m t"),
             (xs[0] + w / 2 + 10, yl - 24, "результат теста → RPN", "w t"), (xs[0] + w / 2 + 10, yl - 10, "пересчитать после меры", "w t"),
             (xs[0], y2 + h + 18, "пустая клетка — требование не закрыто;", "m t"),
             (xs[0], y2 + h + 32, "тест без требования — лишний", "m t"), (xs[0], y2 + h + 46, "или требование забыто", "m t"),
             (48, 50, "инцидент → разбор → новая строка FMEA или обновлённая мера", "m t")]
    out = flow("Трассировка: от строки FMEA до матрицы", boxes, links, 720, H, notes=notes)
    # feedback from the test record back to the FMEA row (RPN after the measure), dashed, drawn by hand
    back = _arrow(f"M{xs[1] + w / 2} {y2} L{xs[1] + w / 2} {yl} L{xs[0] + w / 2} {yl} L{xs[0] + w / 2} {y1 + h}",
                  extra=f' style="stroke:{WARN};stroke-dasharray:5 4"')
    inc = _arrow(f"M36 32 L36 {y1}")
    i = out.rfind("</svg>")
    return out[:i] + back + inc + out[i:]


# ---------------------------------------------------------------- mav-protocol
def rx_frame_flow() -> str:
    x0, w, ex, ew = 10, 380, 430, 280
    ys = [40, 106, 176, 246, 316, 386, 456]
    steps = [("1", ["1. Байт = STX 0xFD (v1 — 0xFE)?"], 38),
             ("2", ["2. Заголовок 10 байт: все биты", "incompat_flags известны?"], 44),
             ("3", ["3. Добрать len + 2 байта CRC", "(+13 подписи, если бит 0)"], 44),
             ("4", ["4. CRC-16/MCRF4XX по байтам 1…payload", "+ CRC_EXTRA(msgid) = checksum?"], 44),
             ("5", ["5. Подписан: SHA-256 (6 байт) верна", "и timestamp растёт?"], 44),
             ("6", ["6. seq: потеряно (seq − seq_прошл − 1) mod 256", "— отдельно для пары sysid/compid"], 44),
             ("7", ["7. len < размера структуры →", "дополнить нулями, распаковать"], 44)]
    boxes = [Box(k, lab, x0, y, w, h, accent=(k in ("1", "7"))) for (k, lab, h), y in zip(steps, ys)]
    boxes += [Box("e1", ["нет: пропустить байт,", "искать STX дальше"], ex, ys[0] - 3, ew, 44),
              Box("e2", ["неизвестный бит: кадр отбросить"], ex, ys[1] + 3, ew, 38),
              Box("e4", ["нет: тихо отбросить — битый", "байт или разные диалекты:", "heartbeat есть, данных нет"], ex, ys[3] - 6, ew, 56),
              Box("e5", ["нет: отбросить (подмена, повтор)"], ex, ys[4] + 3, ew, 38)]
    links = [(steps[i][0], steps[i + 1][0], "да" if i in (0, 1, 3, 4) else "", i == 5, "v") for i in range(len(steps) - 1)]
    links += [("1", "e1", "", False, "h"), ("2", "e2", "", False, "h"), ("4", "e4", "", False, "h"), ("5", "e5", "", False, "h")]
    H = ys[-1] + 44 + 66
    notes = [(10, 20, "Приём кадра MAVLink 2: где пакет теряется молча", "m t"),
             (ex, ys[4] + 58, "неподписанный при включённой подписи —", "m t"),
             (ex, ys[4] + 72, "отбросить; ArduPilot принимает его на", "m t"),
             (ex, ys[4] + 86, "канале 0 (USB), RADIO_STATUS, а в 4.7+", "m t"), (ex, ys[4] + 100, "на канале с MAVn_OPTIONS бит 0", "m t"),
             (10, H - 28, "Парсер, который вместо шага 7 проверяет len == sizeof(struct), отбрасывает обрезанные кадры —", "m t"),
             (10, H - 12, "это выглядит как «случайные потери» команд.", "m t")]
    return _vlabels_beside(flow("Приём кадра MAVLink 2", boxes, links, 720, H, notes=notes))


# ---------------------------------------------------------------- mav-routing
def forward_tree() -> str:
    # MAVLink_routing.cpp forward(): a broadcast goes to every channel with a learned route (HEARTBEAT separately, to
    # all active channels); a foreign sysid to channels where that sysid was seen; our sysid with target_component
    # 0 / absent to channels where any component of our sysid was seen (and is processed locally too); our sysid with
    # another target_component to channels where that sysid/compid pair was seen.
    t = tree("Куда переслать пакет, пришедший на порт A (MAVLink_routing.cpp, порт A — никогда)",
             Node("ts", ["target_system", "в пакете есть и ≠ 0?"], [
                 ("нет", Node("bc", ["Широковещательный:", "во все порты, где", "кого-то уже видели;", "+ обработать самому"],
                              leaf=True, accent=True)),
                 ("да", Node("own", ["target_system =", "свой sysid?"], [
                     ("нет", Node("sys", ["Только в порты,", "где этот sysid", "уже видели"], leaf=True, accent=True)),
                     ("да", Node("tc", ["target_component", "есть и ≠ 0?"], [
                         ("нет", Node("c0", ["В порты, где видели", "любой компонент", "своего sysid;", "+ обработать самому"],
                                      leaf=True, accent=True)),
                         ("да", Node("c1", ["Только в порты, где", "видели эту пару", "sysid/compid; молчащий", "скрипт недостижим"],
                                      leaf=True, accent=True)),
                     ])),
                 ])),
             ], accent=True), width=720, box_w=168, box_h=64, gap_y=88)
    return _add_footer(t, ["Обработать самому: без target, target_system 0, адресован FC — или своему sysid с compid,",
                           "которого нигде не видели. «Видели» — по таблице маршрутов: пополняется с первого пакета",
                           "отправителя, сбрасывается при перезагрузке. HEARTBEAT уходит во все активные порты.",
                           "Порт с MAVn_OPTIONS бит 1 (до 4.7 — SERIALn_OPTIONS бит 10) не пересылает."])


# ---------------------------------------------------------------- mav-component
def rangefinder_timeout() -> str:
    W, L, R = 720, 128, 20
    t_max = 3.0
    X = lambda t: L + (W - L - R) * t / t_max
    TO = 0.5                                                  # AP_RANGEFINDER_MAVLINK_TIMEOUT_MS = 500
    lh = 30
    out = [text(16, 18, "ArduPilot: нет DISTANCE_SENSOR дольше 0.5 с → дальномер «нет данных» (AP_RangeFinder_MAVLink)", "m t", "start")]

    def packets(ts, y):
        return [f'<line x1="{X(t):.1f}" y1="{y + 4}" x2="{X(t):.1f}" y2="{y + 24}" stroke="{INK}" stroke-width="1.4"/>' for t in ts]

    def health(ts, end):
        # healthy while the newest packet is not older than TO (sampled every 10 ms)
        segs, cur, start = [], None, 0.0
        for k in range(0, int(end * 100) + 1):
            t = k / 100
            last = max([p for p in ts if p <= t + 1e-9], default=None)
            ok = last is not None and t - last <= TO + 1e-9
            if cur is None:
                cur, start = ok, t
            elif ok != cur:
                segs.append((start, t, cur))
                cur, start = ok, t
        segs.append((start, end, cur))
        return segs

    def state(segs, y):
        s_ = []
        for a_, b_, ok in segs:
            if ok:
                s_.append(_rect(X(a_), y + 4, X(b_) - X(a_), 20, "boxa", 3))
            else:
                s_.append(f'<rect x="{X(a_):.1f}" y="{y + 4}" width="{X(b_) - X(a_):.1f}" height="20" rx="3" fill="{DANGER}" opacity="0.18" stroke="{DANGER}"/>')
            if X(b_) - X(a_) > 60:
                s_.append(text((X(a_) + X(b_)) / 2, y + 18, "здоров" if ok else "нет данных", "a t" if ok else "d t", "middle", 10.5))
        return s_

    groups = [
        ("1. Честный компонент: измерение потеряно в 1.0 с — перестал слать (10 Гц)", [k / 10 for k in range(0, 11)]),
        ("2. Шлёт последнее значение: с 1.0 с число застыло, пакеты идут (10 Гц)", [k / 10 for k in range(0, 31)]),
        ("3. ≈ 2 Гц, пакет в 1.5 с потерян: пауза 1 с", [0.0, 0.5, 1.0, 2.0, 2.5, 3.0]),
    ]
    y = 40
    seg_all = []
    for head, ts in groups:
        out.append(text(16, y + 12, head, "b t", "start", 11))
        out.append(text(L - 10, y + 36, "пакеты", "m t", "end", 11))
        out += packets(ts, y + 20)
        out.append(text(L - 10, y + 36 + lh, "статус в FC", "m t", "end", 11))
        hs = health(ts, t_max)
        seg_all.append(hs)
        out += state(hs, y + 20 + lh)
        y += 20 + 2 * lh + 18
    assert seg_all[0] == [(0.0, 1.51, True), (1.51, 3.0, False)] or abs(seg_all[0][0][1] - 1.5) < 0.02
    assert all(ok for _, _, ok in seg_all[1])
    assert [ok for _, _, ok in seg_all[2]] == [True, False, True]
    # notes attached to the events, in the free part of each lane
    y0 = 40 + 20
    out.append(text(X(1.0) + 8, y0 + 18, "молчит", "m t", "start", 10.5))
    out.append(text(X(1.5) + 6, y0 + lh - 4, "1.0 + 0.5 = 1.5 с", "d t", "start", 10.5))
    y1 = y0 + 20 + 2 * lh + 18
    y2 = y1 + 20 + 2 * lh + 18
    out.append(text(X(1.5), y2 + 18, "> 0.5 с без пакета", "w t", "middle", 10.5))
    ay = y - 8
    out.append(f'<line class="ln" x1="{X(0):.1f}" y1="{ay}" x2="{X(t_max):.1f}" y2="{ay}"/>')
    for k in range(0, 7):
        t = k * 0.5
        out.append(f'<line class="ln" x1="{X(t):.1f}" y1="{ay - 4}" x2="{X(t):.1f}" y2="{ay + 4}"/>')
        out.append(text(X(t), ay + 18, f"{t:g}", "m t", "middle", 11))
    out.append(text(X(1.5), ay + 34, "время, с (штрих — пакет DISTANCE_SENSOR)", "m t", "middle", 11))
    H = ay + 82
    out.append(text(16, H - 22, "Случай 2 опаснее всех: таймаута нет, автопилот держит высоту по мёртвому дальномеру.", "m t", "start"))
    out.append(text(16, H - 6, "Случай 3 — «мигает» healthy / unhealthy: слать по таймеру ≥ 10 Гц, приём не блокировать.", "m t", "start"))
    return svg(W, H, "Таймаут MAVLink-дальномера в ArduPilot", "".join(out))


# ---------------------------------------------------------------- mav-sdk
def offboard_loss_timeline() -> str:
    W, L, R = 720, 150, 20
    t0, t1 = -1.0, 5.0
    X = lambda t: L + (W - L - R) * (t - t0) / (t1 - t0)
    COM_OF_LOSS_T, GUID_TIMEOUT = 1.0, 3.0                  # PX4 commander_params.c; ArduCopter Parameters.cpp
    top, lh = 56, 56
    out = [text(16, 18, "Скрипт offboard убит (kill -9) в 0 с: кто и когда реагирует — умолчания параметров", "m t", "start")]
    names = ["уставки скрипта", "PX4", "ArduPilot"]
    for i, n in enumerate(names):
        out.append(text(L - 10, top + i * lh + 22, n, "b", "end", 11.5))
    # setpoints: 10 Hz until the kill
    y = top
    for k in range(0, 10):
        t = -1.0 + k * 0.1
        out.append(f'<line x1="{X(t):.1f}" y1="{y + 8}" x2="{X(t):.1f}" y2="{y + 30}" stroke="{ACCENT}" stroke-width="1.4"/>')
    out.append(text(X(0) + 8, y + 23, "уставок нет", "m t", "start", 10.5))
    # PX4
    y = top + lh
    out.append(_rect(X(t0), y + 4, X(COM_OF_LOSS_T) - X(t0), 36, "boxa", 3))
    out.append(text(X(0.5), y + 26, "Offboard", "a b", "middle", 11))
    out.append(_rect(X(COM_OF_LOSS_T), y + 4, X(t1) - X(COM_OF_LOSS_T), 36, "box", 3))
    out.append(text((X(COM_OF_LOSS_T) + X(t1)) / 2, y + 19, "COM_OBL_RC_ACT 0 → Position;", "", "middle", 10.5))
    out.append(text((X(COM_OF_LOSS_T) + X(t1)) / 2, y + 33, "без пульта — NAV_RCL_ACT 2 → Return", "", "middle", 10.5))
    # ArduPilot
    y = top + 2 * lh
    out.append(_rect(X(t0), y + 4, X(GUID_TIMEOUT) - X(t0), 36, "boxa", 3))
    out.append(text(X(2), y + 26, "GUIDED: прежняя скорость", "a", "middle", 10.5))
    out.append(_rect(X(GUID_TIMEOUT), y + 4, X(t1) - X(GUID_TIMEOUT), 36, "box", 3))
    out.append(text((X(GUID_TIMEOUT) + X(t1)) / 2, y + 19, "GUIDED, скорость = 0:", "", "middle", 10.5))
    out.append(text((X(GUID_TIMEOUT) + X(t1)) / 2, y + 33, "стоп и висение", "", "middle", 10.5))
    # event marks, labels above the lanes
    for t, lab, cls, anc, dx in [(0, "kill -9", "d", "end", 4), (COM_OF_LOSS_T, "COM_OF_LOSS_T = 1 с", "a", "middle", 0),
                                 (GUID_TIMEOUT, "GUID_TIMEOUT = 3 с", "a", "middle", 0)]:
        col = DANGER if cls == "d" else ACCENT
        out.append(f'<line x1="{X(t):.1f}" y1="{top - 6}" x2="{X(t):.1f}" y2="{top + 3 * lh}" stroke="{col}" stroke-width="1.2" stroke-dasharray="4 3"/>')
        out.append(text(X(t) + dx, top - 10, lab, f"{cls} t b", anc, 10.5))
    ay = top + 3 * lh + 8
    out.append(f'<line class="ln" x1="{X(t0):.1f}" y1="{ay}" x2="{X(t1):.1f}" y2="{ay}"/>')
    for t in range(-1, 6):
        out.append(f'<line class="ln" x1="{X(t):.1f}" y1="{ay - 4}" x2="{X(t):.1f}" y2="{ay + 4}"/>')
        out.append(text(X(t), ay + 18, f"{t}", "m t", "middle", 11))
    out.append(text(X(2), ay + 34, "время после остановки скрипта, с", "m t", "middle", 11))
    H = ay + 82
    out.append(text(16, H - 22, "Безопасность — на автопилоте; перезапущенный скрипт заново шлёт уставки и входит в Offboard.", "m t", "start"))
    out.append(text(16, H - 6, "Практика, шаг 3: время смены режима по логу сравнить с этими параметрами.", "m t", "start"))
    return svg(W, H, "Остановка скрипта offboard: таймауты автопилота", "".join(out))


# ---------------------------------------------------------------- mav-multi-vehicle
def fleet_min_separation() -> str:
    t_dec, t_brake, e = 0.5, 1.5, 3.0                         # s, s, m (GNSS error per vehicle, upper bound 1–3 m)
    d = lambda v, tt: 2 * v * (tt + t_dec + t_brake) + 2 * e
    assert 2 * 10 * (0.5 + t_dec + t_brake) == 50 and d(10, 0.5) == 56
    MIN_H = 15.0
    v_ok = (MIN_H - 2 * e) / (2 * (0.5 + t_dec + t_brake))
    assert abs(v_ok - 1.8) < 1e-9
    vs = [0.25 * i for i in range(0, 81)]                    # 0 … 20 m/s
    return chart(
        "Минимальная дистанция срабатывания супервизора: d = 2v·(t_тел + 0.5 + 1.5) + 2·3 м",
        [dict(name="телеметрия 1 с", xs=vs, ys=[d(v, 1.0) for v in vs], cls="d", label_at=15.5, label_dy=-10),
         dict(name="0.5 с", xs=vs, ys=[d(v, 0.5) for v in vs], cls="a", label_at=19, label_dy=-10),
         dict(name="0.2 с", xs=vs, ys=[d(v, 0.2) for v in vs], cls="ink", label_at=17, label_dy=22, label_anchor="start"),
         dict(name="", xs=[10], ys=[d(10, 0.5)], cls="ink", dots=True),
         dict(name="", xs=[v_ok], ys=[MIN_H], cls="w", dots=True)],
        Axis("скорость каждого аппарата навстречу, м/с (сближение — 2v; решение 0.5 с, торможение 1.5 с)", 0, 20,
             ticks=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]),
        Axis("дистанция, м", 0, 130, ticks=[0, 20, 40, 60, 80, 100, 120]),
        hmarks=[(MIN_H, "MIN_H = 15 м (супервизор шага 3)", "w")],
        marks=[(10, "10 м/с, 0.5 с: 50 м пути + 6 м ошибок = 56 м", "ink", 202)],
        notes=[(136, 298, f"← при 0.5 с 15 м хватит до {v_ok:.1f} м/с", "w")])


def build(D: dict) -> None:
    D["mav-cmd-ack-flow"] = cmd_ack_flow()
    D["rpi-throttled-bits"] = throttled_bits()
    D["esp32-tx-companion-states"] = tx_companion_states()
    D["emb-blocking-timeline"] = blocking_timeline()
    D["chart-bus-imu-read-time"] = bus_imu_read_time()
    D["fw-gyro-motor-paths"] = gyro_motor_paths()
    D["ci-sitl-failsafe-seq"] = ci_sitl_seq()
    D["eng-trace-chain"] = trace_chain()
    D["mav-rx-frame-flow"] = rx_frame_flow()
    D["mav-forward-tree"] = forward_tree()
    D["mav-rangefinder-timeout"] = rangefinder_timeout()
    D["mav-offboard-loss-timeline"] = offboard_loss_timeline()
    D["chart-fleet-min-separation"] = fleet_min_separation()
