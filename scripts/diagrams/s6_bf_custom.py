"""Stage 6 diagram for module bf-custom (Betaflight 4.5.3, Configurator 10.10).

bf-cloud-build-pipeline — the Cloud Build path as the module describes it from the sources: Configurator
                          sends {target, release, options} (firmware_flasher.js:828-863: CLOUD_BUILD or CORE_BUILD,
                          the USE_* values of the four lists, custom defines in expert mode) to
                          build.betaflight.com /api/builds; the server builds with the gates of common_pre.h and
                          embeds BUILD_KEY (build/version.c:33-43); flashing without expert mode always erases
                          the chip (firmware_flasher.js:581-585); on the board `status` prints "BUILD KEY: …"
                          (cli.c:4732-4738) and MSP_BUILD_INFO lists the options (msp.c:749-754), the Setup tab
                          links Config / Log / Options and hides the GPS, LED strip, OSD, servo and transponder tabs
                          of absent options (gui.js:57-63, serial_backend.js:611-620). A local `make` has no
                          BUILD_KEY: no status line, "Local Build - no Cloud information".
"""
from __future__ import annotations

from svg import Box, flow


def build(D: dict) -> None:
    W, H = 168, 62
    boxes = [
        Box("cfg", ["Configurator 10.10", "плата, версия,", "опции, Core Only"], 8, 40, W, H, accent=True),
        Box("req", ["POST /api/builds", "target, release,", "CLOUD_BUILD + USE_*"], 188, 40, W, H),
        Box("srv", ["Сервер сборки", "make с этими USE_*", "без лишнего кода"], 368, 40, W, H, accent=True),
        Box("hex", ["hex + BUILD KEY", "32 символа,", "зашит в прошивку"], 548, 40, W, H),
        Box("fl", ["Прошивка", "без Expert mode —", "Full chip erase"], 548, 160, W, H),
        Box("fc", ["Плата", "status: BUILD KEY", "MSP: опции сборки"], 368, 160, W, H, accent=True),
        Box("ui", ["Вкладка Setup", "Config/Log/Options", "вкладки по опциям"], 188, 160, W, H),
        Box("cli", ["Проверка в CLI", "get → INVALID NAME", "help: нет команды"], 8, 160, W, H),
        Box("loc", ["Локально: make", "CONFIG=… OPTIONS=…", "BUILD KEY нет"], 548, 268, W, H),
    ]
    links = [("cfg", "req"), ("req", "srv"), ("srv", "hex"), ("hex", "fl", "", True, "v"), ("fl", "fc", "", True),
             ("fc", "ui"), ("ui", "cli"), ("loc", "fl", "", False, "v")]
    D["bf-cloud-build-pipeline"] = flow(
        "Cloud Build: от списка опций до проверки на плате (Betaflight 4.5.3)",
        boxes, links, 720, 345,
        notes=[(10, 136, "Чего нет в запросе, того нет в коде: настройка, команда и вкладка исчезают молча.", "w t"),
               (10, 286, "Локальная сборка: в status нет строки BUILD KEY,", "m t"),
               (10, 300, "Setup пишет «Local Build - no Cloud information».", "m t"),
               (10, 322, "Ключ из status → build.betaflight.com/api/builds/<ключ>/json — состав сборки.", "m t")])
