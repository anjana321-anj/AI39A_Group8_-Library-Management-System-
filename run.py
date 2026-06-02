"""
BookVerse – Primary Entry Point
=================================
Run the development server:
    python run.py

Production (gunicorn):
    gunicorn "app:create_app()" --bind 0.0.0.0:5000 --workers 4

This file is an alias for bookverse.py so that both
`python run.py` and `python bookverse.py` work correctly.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
        use_reloader=True,
    )
