@echo off
setlocal

set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

REM abre dos consolas separadas
start "PeopleCounter Backend" cmd /k "%ROOT%\start_backend.bat"
timeout /t 2 /nobreak >nul
start "PeopleCounter Counter" cmd /k "%ROOT%\start_counter.bat"
