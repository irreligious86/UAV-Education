@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\publish.py
if errorlevel 1 pause & exit /b 1

git add index.html data\content-manifest.json content data scripts curriculum curriculum\curriculum.html 2>nul
git commit -m "content: update generated site content" 2>nul
if errorlevel 1 (
  echo Внимание: коммит не выполнен ^(нет изменений или нет git репозитория^).
) else (
  git push 2>nul
  if errorlevel 1 echo Внимание: push не выполнен — проверьте remote и сеть.
)
echo.
pause
