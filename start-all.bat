@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-all.ps1" -Service all -Profile mysql -EnableSerial
if errorlevel 1 (
  echo.
  echo Startup failed. Check logs folder for details.
  pause
  exit /b 1
)
echo.
echo Services are running.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8080/api/dashboard
pause
