@echo off
cd /d "%~dp0.."

call venv\Scripts\activate.bat

mkdir logs 2>nul

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 >> logs\backend.log 2>&1
