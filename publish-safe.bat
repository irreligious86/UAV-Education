@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo ОШИБКА: Python не найден в PATH.
  echo Установите Python 3 и проверьте команду: python --version
  pause
  exit /b 1
)

echo [2/3] Валидация контента...
python scripts\validate_content.py
if errorlevel 1 (
  echo.
  echo ОШИБКА: Валидация не пройдена. Исправьте ошибки выше и повторите запуск.
  pause
  exit /b 1
)

echo [3/3] Публикация в index.html...
python scripts\publish.py --skip-validate
if errorlevel 1 (
  echo.
  echo ОШИБКА: Публикация не выполнена.
  echo Проверьте:
  echo  - наличие маркеров AUTO:* в index.html;
  echo  - корректность путей sourceFile в data\content-manifest.json;
  echo  - наличие файлов content\*.md для published-статей.
  pause
  exit /b 1
)

echo.
echo УСПЕХ: index.html обновлен.
pause
