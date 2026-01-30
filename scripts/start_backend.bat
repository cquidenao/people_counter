@echo off
setlocal enabledelayedexpansion

REM ============================
REM People Counter - Start Backend
REM ============================

REM Root del proyecto (scripts\ -> ..\)
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

set "LOGDIR=%ROOT%\logs"
set "VENV=%ROOT%\venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Timestamp simple
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do set "D=%%c%%b%%a"
for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set "T=%%a%%b%%c"
set "TS=%D%_%T%"

set "LOG=%LOGDIR%\backend_%TS%.log"

echo [backend] ROOT=%ROOT%
echo [backend] LOG=%LOG%
echo [backend] Starting...

REM Si no existe venv, te avisa
if not exist "%PY%" (
  echo [backend] ERROR: No encuentro venv en "%VENV%".
  echo [backend] Crea el venv en la carpeta del proyecto: python -m venv venv
  pause
  exit /b 1
)

pushd "%ROOT%"

REM Inicia uvicorn en este mismo proceso (Task Scheduler lo mantiene vivo)
"%PY%" -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --log-level info >> "%LOG%" 2>&1

popd
endlocal
