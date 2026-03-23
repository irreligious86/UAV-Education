# -*- coding: utf-8 -*-
"""Описание разделов для генерации data/content-manifest.json."""
SECTIONS = [
    {
        "tabId": "tab-betaflight",
        "sectionKey": "betaflight",
        "title": "Betaflight",
        "articles": [
            {"id": "bf-intro", "title": "Введение в Betaflight", "level": "L1", "order": 1, "readingTime": "10 мин", "status": "published", "tags": ["Betaflight 4.5+"], "sourceFile": "content/betaflight/bf-intro.md", "type": "article"},
            {"id": "bf-ports", "title": "Порты и приёмник", "level": "L1", "order": 2, "readingTime": "12–15 мин", "status": "published", "tags": ["ports", "RX"], "sourceFile": "content/betaflight/bf-ports.md", "type": "article"},
            {"id": "bf-modes-osd", "title": "Режимы и OSD", "level": "L1", "order": 3, "readingTime": "15 мин", "status": "published", "tags": ["modes", "OSD"], "sourceFile": "content/betaflight/bf-modes-osd.md", "type": "article"},
            {"id": "bf-pid", "title": "PID-тюнинг", "level": "L2", "order": 4, "readingTime": "20 мин", "status": "published", "tags": ["PID"], "sourceFile": "content/betaflight/bf-pid.md", "type": "article"},
            {"id": "bf-filters", "title": "Фильтры", "level": "L2", "order": 5, "readingTime": "15–20 мин", "status": "published", "tags": ["filters"], "sourceFile": "content/betaflight/bf-filters.md", "type": "article"},
            {"id": "bf-blackbox", "title": "Blackbox", "level": "L2", "order": 6, "readingTime": "20 мин", "status": "published", "tags": ["Blackbox"], "sourceFile": "content/betaflight/bf-blackbox.md", "type": "article"},
            {"id": "bf-cli", "title": "CLI и remap", "level": "L3", "order": 7, "readingTime": "15 мин", "status": "published", "tags": ["CLI"], "sourceFile": "content/betaflight/bf-cli.md", "type": "article"},
            {"id": "bf-custom", "title": "Кастомная сборка", "level": "L4", "order": 8, "readingTime": "15–20 мин", "status": "published", "tags": ["build"], "sourceFile": "content/betaflight/bf-custom.md", "type": "article"},
        ],
    },
    {
        "tabId": "tab-inav",
        "sectionKey": "inav",
        "title": "INAV",
        "articles": [
            {"id": "inav-intro", "title": "Введение в INAV", "level": "L1", "order": 1, "readingTime": "12 мин", "status": "published", "tags": ["INAV 7.0+"], "sourceFile": "content/inav/inav-intro.md", "type": "article"},
            {"id": "inav-gps", "title": "GPS-навигация в INAV", "level": "L2", "order": 2, "readingTime": "20 мин", "status": "published", "tags": ["GPS", "MAG", "RTH"], "sourceFile": "content/inav/inav-gps.md", "type": "article"},
            {"id": "inav-wing", "title": "Настройка крыла", "level": "L2", "order": 3, "readingTime": "25 мин", "status": "published", "tags": ["fixed-wing"], "sourceFile": "content/inav/inav-wing.md", "type": "article"},
            {"id": "inav-missions", "title": "Автономные миссии", "level": "L3", "order": 4, "readingTime": "25 мин", "status": "published", "tags": ["waypoints"], "sourceFile": "content/inav/inav-missions.md", "type": "article"},
            {"id": "inav-ipf", "title": "IPF и JavaScript", "level": "L3", "order": 5, "readingTime": "30 мин", "status": "published", "tags": ["IPF"], "sourceFile": "content/inav/inav-ipf.md", "type": "article"},
        ],
    },
    {
        "tabId": "tab-ardupilot",
        "sectionKey": "ardupilot",
        "title": "ArduPilot",
        "articles": [
            {"id": "ap-intro", "title": "Введение в ArduPilot", "level": "L1", "order": 1, "readingTime": "15 мин", "status": "published", "tags": ["ArduPilot 4.5+"], "sourceFile": "content/ardupilot/ap-intro.md", "type": "article"},
            {"id": "ap-missions", "title": "Миссии и планирование", "level": "L2", "order": 2, "readingTime": "25 мин", "status": "published", "tags": ["missions"], "sourceFile": "content/ardupilot/ap-missions.md", "type": "article"},
            {"id": "ap-lua", "title": "Lua скриптинг", "level": "L3", "order": 3, "readingTime": "25 мин", "status": "published", "tags": ["Lua"], "sourceFile": "content/ardupilot/ap-lua.md", "type": "article"},
            {"id": "ap-ekf", "title": "EKF и навигация", "level": "L3", "order": 4, "readingTime": "25 мин", "status": "published", "tags": ["EKF"], "sourceFile": "content/ardupilot/ap-ekf.md", "type": "article"},
            {"id": "ap-companion", "title": "Companion + ArduPilot", "level": "L3", "order": 5, "readingTime": "30 мин", "status": "published", "tags": ["companion"], "sourceFile": "content/ardupilot/ap-companion.md", "type": "article"},
        ],
    },
    {
        "tabId": "tab-px4",
        "sectionKey": "px4",
        "title": "PX4",
        "articles": [
            {"id": "px4-intro", "title": "Введение в PX4", "level": "L1", "order": 1, "readingTime": "15 мин", "status": "published", "tags": ["PX4 1.15+"], "sourceFile": "content/px4/px4-intro.md", "type": "article"},
            {"id": "px4-architecture", "title": "Архитектура и uORB", "level": "L2", "order": 2, "readingTime": "25 мин", "status": "published", "tags": ["uORB"], "sourceFile": "content/px4/px4-architecture.md", "type": "article"},
            {"id": "px4-control", "title": "Control Allocation и миксер", "level": "L2", "order": 3, "readingTime": "25 мин", "status": "published", "tags": ["actuators"], "sourceFile": "content/px4/px4-control.md", "type": "article"},
            {"id": "px4-ros2", "title": "ROS 2 интеграция", "level": "L3", "order": 4, "readingTime": "35 мин", "status": "published", "tags": ["ROS 2"], "sourceFile": "content/px4/px4-ros2.md", "type": "article"},
        ],
    },
    {
        "tabId": "tab-companion",
        "sectionKey": "companion",
        "title": "Companion",
        "articles": [
            {"id": "comp-intro", "title": "Введение в Companion", "level": "L2", "order": 1, "readingTime": "15 мин", "status": "published", "tags": ["MAVLink"], "sourceFile": "content/companion/comp-intro.md", "type": "article"},
            {"id": "comp-mavlink", "title": "MAVLink и MAVSDK", "level": "L2", "order": 2, "readingTime": "25 мин", "status": "published", "tags": ["MAVSDK"], "sourceFile": "content/companion/comp-mavlink.md", "type": "article"},
            {"id": "comp-raspberry", "title": "Raspberry Pi + ArduPilot", "level": "L3", "order": 3, "readingTime": "40 мин", "status": "published", "tags": ["Raspberry Pi"], "sourceFile": "content/companion/comp-raspberry.md", "type": "article"},
            {"id": "comp-esp32", "title": "ESP32 и периферия", "level": "L2", "order": 4, "readingTime": "30 мин", "status": "published", "tags": ["ESP32"], "sourceFile": "content/companion/comp-esp32.md", "type": "article"},
        ],
    },
    {
        "tabId": "tab-tools",
        "sectionKey": "tools",
        "title": "Инструменты",
        "articles": [
            {"id": "tools-overview", "title": "Инструментарий", "level": "L1", "order": 1, "readingTime": "10 мин", "status": "published", "tags": ["GCS", "tools"], "sourceFile": "content/tools/tools-overview.md", "type": "article"},
        ],
    },
]
