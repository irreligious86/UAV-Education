@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\publish.py
if errorlevel 1 pause & exit /b 1
echo.
echo Готово. При необходимости: git add / commit / push вручную.
pause
