"""
Entry point – YouTube Short Generator API

Run with:
    py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from app.app import create_app

app = create_app()
