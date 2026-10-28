@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-all.ps1" -Service backend -Profile mysql -EnableSerial
if errorlevel 1 (
  echo.
  echo Backend startup failed. Check logs folder for details.
  pause
  exit /b 1
)
echo.
echo Backend is running: http://localhost:8080/api/dashboard
pause
