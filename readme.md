source venv/Scripts/activate

python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000


python people_counter.py