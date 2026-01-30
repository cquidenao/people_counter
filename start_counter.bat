@echo off
setlocal

set ROOT=C:\people_counter
set VENV=%ROOT%\venv
set LOGDIR=%ROOT%\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

cd /d "%ROOT%"

call "%VENV%\Scripts\activate.bat"

REM Arranca el contador (sin UI). Log a archivo.
python "%ROOT%\people_counter.py" >> "%LOGDIR%\counter.log" 2>&1
