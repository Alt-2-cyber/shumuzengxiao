@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-all.ps1" -Service frontend -Profile mysql
if errorlevel 1 (
  echo.
  echo Frontend startup failed. Check logs folder for details.
  pause
  exit /b 1
)
echo.
echo Frontend is running: http://localhost:5173
pause
