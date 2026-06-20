Bookverse Project/
├── run.py                          # Entry point - starts Flask app
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── controller/
│   │   ├── __init__.py
│   │   └── auth.py                 # AuthController with all page handlers
│   ├── routes/
│   │   ├── __init__.py
│   │   └── auth.py                 # Route definitions
│   ├── modal/
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── static/                     # Static files (CSS, JS, images)
│   └── templates/
│       ├── base.html               # Base template (navbar, layout)
│       ├── login.html              # Login page (index)
│       ├── register.html           # Registration page
│       ├── home.html               # Homepage
│       ├── about.html              # About page
│       ├── books.html              # Books catalog
│       ├── contact.html            # Contact form
│       ├── profile.html            # User profile
│       └── services.html           # Services overview
├── requirements.txt                # Python dependencies
└── venv/                          # Virtual environment
