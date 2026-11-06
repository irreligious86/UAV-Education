@echo off
rem Validate content and rebuild index.html. Commit and push manually (CI re-checks on push).
chcp 65001 >nul
cd /d "%~dp0"
python scripts\publish.py
if errorlevel 1 (
  echo.
  echo FAILED: see errors above.
  pause
  exit /b 1
)
echo.
echo OK: index.html rebuilt. Next: git add -A ^&^& git commit ^&^& git push
pause
