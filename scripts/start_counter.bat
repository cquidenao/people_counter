@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
for /f "tokens=1-3 delims=/: " %%a in ("%date%") do set "D=%%c%%a%%b"
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do set "T=%%a%%b%%c"
set "LOG=%ROOT%\logs\counter_%D%_%T%.log"

echo [counter] ROOT=%ROOT%
echo [counter] LOG=%LOG%
echo [counter] Starting...

if not exist "%ROOT%\venv\Scripts\python.exe" (
  echo [counter] ERROR: No existe venv en %ROOT%\venv
  pause
  exit /b 1
)

REM === TU ARCHIVO REAL (CAMBIAR SI ES NECESARIO) ===
REM Opciones comunes: people_counter.py / counter_webcam.py
set "COUNTER_FILE=people_counter.py"

if not exist "%ROOT%\%COUNTER_FILE%" (
  echo [counter] ERROR: No existe %ROOT%\%COUNTER_FILE%
  echo [counter] Revisa el nombre del archivo del counter y actualiza COUNTER_FILE.
  pause
  exit /b 1
)

REM Importante: arrancar desde ROOT para que encuentre config.yaml y snapshots/
pushd "%ROOT%"

"%ROOT%\venv\Scripts\python.exe" "%ROOT%\%COUNTER_FILE%" >> "%LOG%" 2>&1

popd
