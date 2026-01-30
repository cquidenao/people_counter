@echo off
setlocal

set ROOT=C:\people_counter
set VENV=%ROOT%\venv
set LOGDIR=%ROOT%\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

cd /d "%ROOT%"

call "%VENV%\Scripts\activate.bat"

REM Arranca FastAPI local (solo si lo necesitas local)
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 >> "%LOGDIR%\backend.log" 2>&1
