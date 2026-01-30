@echo off
setlocal EnableExtensions

REM === ROOT del proyecto (carpeta padre de /scripts) ===
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

REM === Logs ===
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
for /f "tokens=1-3 delims=/: " %%a in ("%date%") do set "D=%%c%%a%%b"
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do set "T=%%a%%b%%c"
set "LOG=%ROOT%\logs\backend_%D%_%T%.log"

echo [backend] ROOT=%ROOT%
echo [backend] LOG=%LOG%
echo [backend] Starting...

REM === VENV ===
if not exist "%ROOT%\venv\Scripts\python.exe" (
  echo [backend] ERROR: No existe venv en %ROOT%\venv
  echo [backend] Crea venv y instala requirements.
  pause
  exit /b 1
)

REM === Start FastAPI (puerto 8000 local) ===
"%ROOT%\venv\Scripts\python.exe" -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --log-level info >> "%LOG%" 2>&1
