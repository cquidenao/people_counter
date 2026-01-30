@echo off
setlocal enabledelayedexpansion

REM ============================
REM People Counter - Start Counter
REM ============================

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

set "LOGDIR=%ROOT%\logs"
set "VENV=%ROOT%\venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f "tokens=1-3 delims=/- " %%a in ("%date%") do set "D=%%c%%b%%a"
for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set "T=%%a%%b%%c"
set "TS=%D%_%T%"

set "LOG=%LOGDIR%\counter_%TS%.log"

echo [counter] ROOT=%ROOT%
echo [counter] LOG=%LOG%
echo [counter] Starting...

if not exist "%PY%" (
  echo [counter] ERROR: No encuentro venv en "%VENV%".
  pause
  exit /b 1
)

REM OJO: ajusta este nombre si tu script final se llama distinto
set "COUNTER_PY=%ROOT%\people_counter.py"

if not exist "%COUNTER_PY%" (
  echo [counter] ERROR: No encuentro "%COUNTER_PY%".
  echo [counter] Revisa el nombre del archivo (por ejemplo counter_webcam.py).
  pause
  exit /b 1
)

pushd "%ROOT%"

REM Ejecuta counter (usa config.yaml desde ROOT)
"%PY%" "%COUNTER_PY%" >> "%LOG%" 2>&1

popd
endlocal
