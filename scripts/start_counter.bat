@echo off
cd /d "%~dp0.."

call venv\Scripts\activate.bat

mkdir logs 2>nul

python counter_webcam.py >> logs\counter.log 2>&1
