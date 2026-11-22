"""Stage 6 diagrams for px4-console-params.

1. px4-console-param-layers — where a parameter value comes from in PX4 1.17.0
   (src/lib/parameters/parameters.cpp: firmware_defaults / runtime_defaults / user_config layers,
   param_export_internal() skips values equal to the runtime default; autosave.cpp: 300 ms, 2 s rate limit;
   ROMFS/px4fmu_common/init.d/rcS: order of param import, board defaults, airframe, config.txt).
   The example numbers are the RTL_RETURN_ALT chain of the module's practice step 1
   (rtl_params.c: 60 m, rc.mc_defaults: 30 m).
2. px4-console-tool-choice — "which tool for which question": the command and the field to read,
   each taken from the command's source (listener_main.cpp, module.h, Commander.cpp, param.cpp, print_load.cpp).
"""
from __future__ import annotations

from svg import Box, flow


def build(D: dict) -> None:
    # ---- 1. layers of a parameter value ------------------------------------------------------
    boxes = [
        Box("fw", ["1. Умолчание прошивки", "(вшито при сборке)", "RTL_RETURN_ALT = 60"], 10, 44, 164, 58),
        Box("rt", ["2. Умолчание запуска", "param set-default:", "плата, airframe"], 196, 44, 164, 58,
            note="rc.mc_defaults: 30"),
        Box("us", ["3. Сохранённое", "param set, QGC,", "калибровка, драйвер"], 382, 44, 150, 58, accent=True),
        Box("get", ["4. param_get()", "видит модуль:", "RTL_RETURN_ALT = 30"], 556, 44, 154, 58),
        Box("bson", ["BSON: /fs/mtd_params", "parameters_backup.bson"], 366, 150, 182, 46, accent=True),
        Box("boot", ["Загрузка: param import", "→ плата → airframe", "→ config.txt → модули"], 10, 144, 164, 58),
        Box("rb", ["reboot_required:", "модуль прочитал", "значение при старте"], 556, 144, 154, 58),
    ]
    links = [
        ("fw", "rt"), ("rt", "us"), ("us", "get", "", True),
        ("us", "bson", "через 0.3–2 с", True, "v"),
        ("get", "rb", "", False, "v"),
    ]
    D["px4-console-param-layers"] = flow(
        "PX4 1.17: откуда берётся значение параметра", boxes, links, 720, 268,
        notes=[
            (10, 30, "Побеждает верхний непустой слой: сохранённое → умолчание запуска → умолчание прошивки.", "m t"),
            (10, 228, "В файл уходит только то, что отличается от слоя 2. Значение, совпавшее с умолчанием", "m t"),
            (10, 243, "airframe, не хранится и после обновления прошивки молча получит новое умолчание.", "m t"),
            (10, 258, "Слой 2 живёт в RAM и собирается заново при каждой загрузке; param reset убирает запись слоя 3.", "m t"),
        ])

    # ---- 2. which tool for which question ----------------------------------------------------
    rows = [
        ("q1", ["Датчик виден?"], "c1", ["listener <топик>", "<драйвер> status · dmesg"],
         "f1", ["never published /", "N instances, not running"]),
        ("q2", ["Почему нет арма?"], "c2", ["commander check", "dmesg · QGC Arming checks"],
         "f2", ["Preflight check: FAILED", "строки Preflight Fail: …"]),
        ("q3", ["Драйвер запущен?"], "c3", ["<модуль> status", "work_queue status"],
         "f3", ["not running /", "строка с частотой, Гц"]),
        ("q4", ["Что изменено", "в параметрах?"], "c4", ["param show -c", "param show-for-airframe"],
         "f4", ["метки + и *,", "строки param set-default"]),
        ("q5", ["CPU перегружен?"], "c5", ["top once", "listener cpuload"],
         "f5", ["CPU usage: … % idle", "load против COM_CPU_MAX"]),
    ]
    tb = []
    tl = []
    y = 40
    for qid, ql, cid, cl, fid, fl in rows:
        tb.append(Box(qid, ql, 10, y, 150, 40, accent=True))
        tb.append(Box(cid, cl, 200, y, 232, 40))
        tb.append(Box(fid, fl, 472, y, 238, 40))
        tl.append((qid, cid))
        tl.append((cid, fid))
        y += 52
    D["px4-console-tool-choice"] = flow(
        "PX4: какой командой отвечать на вопрос", tb, tl, 720, 340,
        notes=[
            (10, 30, "Вопрос", "m t"), (200, 30, "Команда (первая — основная)", "m t"),
            (472, 30, "Куда смотреть в выводе", "m t"),
            (10, 312, "Эти команды только читают. Меняют состояние param set, commander arm, actuator_test, reboot:", "m t"),
            (10, 327, "их набирают без пропеллеров и не в полёте. В SITL (pxh) нет top, dmesg и reboot.", "m t"),
        ])
