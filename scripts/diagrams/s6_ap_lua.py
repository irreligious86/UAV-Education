"""Stage 6 diagrams for ap-lua (ArduPilot 4.7.2 scripting).

lua-script-lifecycle — one script from load to removal: update() returns (fn, ms) and is rescheduled; a runtime
                       error, an overrun of SCR_VM_I_COUNT or a bad return removes the script until reboot and
                       makes arming fail with "Scripting: ..." (svg.flow). Numbers from the module's SITL run:
                       100 ms requested, about 113 ms measured (112.8); COMMAND_ACK 4 on arm.
"""
from __future__ import annotations

from svg import Box, flow


def _lifecycle() -> str:
    bw, bh = 160, 50
    boxes = [
        Box("load", ["Загрузка при старте", "scripts/*.lua", "SCR_ENABLE = 1"], 12, 46, 190, 58),
        Box("run", ["вызов update()", "лимит инструкций", "SCR_VM_I_COUNT 10000"], 236, 46, 200, 58, accent=True),
        Box("ret", ["return update, 100", "следующий вызов", "через ≥ 100 мс"], 470, 46, 238, 58),
        Box("err", ["ошибка / превышение /", "1 или ≥ 3 значения"], 236, 170, 200, bh),
        Box("rm", ["скрипт снят до", "перезапуска скриптинга"], 470, 170, 238, bh),
        Box("pre", ["PreArm: Scripting: …", "арм отклонён (ACK 4)"], 470, 270, 238, bh, accent=True),
    ]
    links = [
        ("load", "run", "", False, "h"),
        ("run", "ret", "ок", True, "h"),
        ("run", "err", "", False, "v"),
        ("err", "rm", "", False, "h"),
        ("rm", "pre", "", False, "v"),
    ]
    notes = [
        (470, 122, "прогон SITL: запрошено 100 мс,", "m t"),
        (470, 136, "измерено ≈ 113 мс", "m t"),
        (236, 240, "return без значений — снят молча", "m t"),
        (470, 36, "планировщик вызовет снова", "m t"),
        (12, 262, "Остальные скрипты работают дальше.", "m t"),
        (12, 278, "Повтор ошибки: раз в 10 с, до 10 раз.", "m t"),
        (12, 294, "Исправить файл → перезагрузка", "m t"),
        (12, 310, "или MAV_CMD_SCRIPTING (3), RCx 316.", "m t"),
    ]
    return flow("Жизнь Lua-скрипта: перепланирование или снятие", boxes, links, 720, 336, notes)


def build(D: dict) -> None:
    D["lua-script-lifecycle"] = _lifecycle()
