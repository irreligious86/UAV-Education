"""Stage 6 diagram for module link-elrs (ExpressLRS 4.1.0).

elrs-uid-model-match — binding phrase -> MD5 of `-DMY_BINDING_PHRASE="…"` -> first 6 bytes = UID
                       (python/build_flags.py:71-74, lib/CONFIG/config.cpp:14-41) and the three places the UID is
                       used on air: FHSS seed from UID[2..5] with UID[5]^OTA_VERSION_ID (lib/OTA/OTA.cpp:41-45),
                       CRC init from UID[4..5] ^ 0x0400 (OTA.cpp:28-39), UID4/UID5 in the SYNC packet where the low
                       6 bits of UID5 are XORed with ~model id when Model Match is on (tx_main.cpp:407-415) and the
                       receiver checks UID4, the top 2 bits (link) and the low 6 bits (channels to the FC)
                       (rx_main.cpp:1010-1090). Numbers = the module's lab (phrase "my-quad-2026", uid_lab output).
"""
from __future__ import annotations

from svg import Box, flow


def build(D: dict) -> None:
    boxes = [
        Box("ph", ["Binding phrase", "«my-quad-2026»"], 10, 30, 150, 58, accent=True),
        Box("md5", ["MD5 строки", "-DMY_BINDING_PHRASE=", "\"my-quad-2026\""], 200, 30, 230, 58),
        Box("uid", ["UID = первые 6 байт", "250,147,85,15,155,38"], 480, 30, 220, 58, accent=True),
        Box("fh", ["Seed прыжков", "UID[2..5], UID[5]^4", "= 0x550F9B22"], 10, 140, 220, 62),
        Box("crc", ["Начало CRC пакета", "(UID[4]<<8|UID[5])^0x400", "= 0x9F26"], 250, 140, 220, 62),
        Box("sy", ["UID4, UID5 в SYNC", "Model Match On: младшие", "6 бит UID5 ^ ~ID модели"], 480, 140, 220, 62),
        Box("rx", ["Приёмник", "UID4 + биты 7–6 → связь;", "биты 5–0 → каналы в FC"], 480, 250, 220, 62, accent=True),
    ]
    links = [("ph", "md5"), ("md5", "uid"), ("uid", "fh", "", False, "v"), ("uid", "crc", "", False, "v"),
             ("uid", "sy", "", False, "v"), ("sy", "rx", "", True, "v")]
    D["elrs-uid-model-match"] = flow(
        "ExpressLRS 4.1: что делает фраза привязки и где проверяется Model Match",
        boxes, links, 720, 330,
        notes=[(10, 236, "Другая фраза → другой порядок прыжков (совпало 7 из 240);", "m t"),
               (10, 250, "чужой SYNC на общем sync-канале отбрасывается по UID4 и CRC.", "m t"),
               (10, 272, "UID[0..1] в эфир не идут; шифрования нет:", "w t"),
               (10, 286, "фраза отделяет линки, но не защищает их.", "w t"),
               (10, 308, "ID 1, Model Match On: UID5 38 → 24 в SYNC.", "m t")])
