"""
BookVerse – Application Entry Point
=====================================
Run locally:
    python bookverse.py

Production (gunicorn example):
    gunicorn "app:create_app()" --bind 0.0.0.0:5000 --workers 4
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
