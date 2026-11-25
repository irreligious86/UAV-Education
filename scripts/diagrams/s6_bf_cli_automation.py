"""Stage 6 (thin-module pass) diagram for module bf-cli-automation.

bf-cli-silent-fix — where a value written with `set` can change without any CLI message: validateAndFixConfig()
                    runs inside save (writeUnmodifiedConfigToEEPROM) and again at boot (readEEPROM)
                    (config/config.c, Betaflight 4.5.3 and 2025.12.5). Examples are the ones the module verified:
                    the SITL lab output (d_max_roll 20 -> 0; GPS-RESCUE -> DROP on 2025.12.5 via the out-of-range check, SITL has
                    no GPS) and config.c lines (d_min > D -> 0 in 4.5.3, GPS-RESCUE without feature GPS, bidir). A batch with an error refuses save.
"""
from __future__ import annotations

from svg import Box, flow


def build(D: dict) -> None:
    D["bf-cli-silent-fix"] = flow("Где значение после set меняется без сообщений", [
        Box("set", ["set → RAM", "«set to 20»"], 10, 16, 120, 48),
        Box("save", ["save", "(ошибка в batch → отказ)"], 150, 16, 190, 48),
        Box("fix1", ["validateAndFixConfig", "① перед записью"], 360, 16, 180, 48, accent=True),
        Box("eep", ["EEPROM"], 560, 16, 150, 48),
        Box("boot", ["перезагрузка:", "save / exit"], 560, 120, 150, 48),
        Box("fix2", ["validateAndFixConfig", "② при загрузке"], 360, 120, 180, 48, accent=True),
        Box("get", ["get / diff all:", "фактическое значение"], 130, 120, 190, 48, accent=True),
        Box("cmp", ["сравнить", "с записанным"], 10, 120, 104, 48),
    ], [("set", "save"), ("save", "fix1"), ("fix1", "eep"), ("eep", "boot", "", False, "v"),
        ("boot", "fix2"), ("fix2", "get"), ("get", "cmp", "", True)],
        720, 250, notes=[
            (10, 198, "SITL 2025.12.5: d_max_roll = 20 при d_roll = 30 → 0; GPS-RESCUE вне перечня сборки (GPS нет) → DROP.", "m t"),
            (10, 214, "По config.c: d_min > D → 0 (4.5.3); GPS-RESCUE без feature GPS → DROP; bidir без DShot → OFF.", "m t"),
            (10, 236, "Правило скрипта: после save перечитать get каждый изменённый ключ; ответ «set to» ничего не гарантирует.", "a t")])
