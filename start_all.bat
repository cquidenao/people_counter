@echo off
set ROOT=C:\people_counter

start "BACKEND" /min cmd /c "%ROOT%\scripts\start_backend.bat"
timeout /t 2 /nobreak >nul
start "COUNTER" /min cmd /c "%ROOT%\scripts\start_counter.bat"
