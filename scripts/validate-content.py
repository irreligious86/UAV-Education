#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обёртка: вызывает validate_content.py (имя с подчёркиванием — основной модуль)."""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "validate_content.py"), run_name="__main__")
