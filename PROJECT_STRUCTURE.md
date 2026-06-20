# Bookverse Project - Complete Configuration Guide

## Project Structure
```
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
```

## URL Routes (All accessible from navbar)

| Page | URL | Route | Controller Method |
|------|-----|-------|-------------------|
| **Login (Index/Home)** | `http://127.0.0.1:5000/` | `/` | `AuthController.login()` |
| Login | `http://127.0.0.1:5000/login` | `/login` | `AuthController.login()` |
| Register | `http://127.0.0.1:5000/register` | `/register` | `AuthController.register()` |
| Home | `http://127.0.0.1:5000/home` | `/home` | `AuthController.home()` |
| Books | `http://127.0.0.1:5000/books` | `/books` | `AuthController.books()` |
| About | `http://127.0.0.1:5000/about` | `/about` | `AuthController.about()` |
| Services | `http://127.0.0.1:5000/services` | `/services` | `AuthController.services()` |
| Contact | `http://127.0.0.1:5000/contact` | `/contact` | `AuthController.contact()` |
| Profile | `http://127.0.0.1:5000/profile` | `/profile` | `AuthController.profile()` |

## How It Works

### 1. Entry Point (run.py)
```python
from app import create_app
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)  # Runs on http://127.0.0.1:5000
```

### 2. App Initialization (app/__init__.py)
- Creates Flask app
- Registers AuthRoutes blueprint
- Blueprint registered with no url_prefix, so routes are at root level

### 3. Route Registration (app/routes/auth.py)
- Defines all URL routes (/, /login, /register, /home, /books, /about, /services, /contact, /profile)
- Maps each route to AuthController methods

### 4. Controllers (app/controller/auth.py)
- `login()` → renders login.html
- `register()` → renders register.html
- `home()` → renders home.html
- `books()` → renders books.html
- `about()` → renders about.html
- `services()` → renders services.html
- `contact()` → renders contact.html
- `profile()` → renders profile.html

### 5. Templates (app/templates/)
- **base.html**: Master template with responsive Bootstrap navbar
- All other pages extend base.html using `{% extends "base.html" %}`
- Navbar links to all pages using Flask's `url_for()` function

## Navigation Structure

The **base.html** template includes a responsive navbar with links to:
- Bookverse Logo (links to login)
- Home
- Books
- About
- Services
- Contact
- Profile
- Login

All pages inherit this navbar automatically!

## To Run the Project

1. Activate virtual environment:
   ```bash
   .\venv\Scripts\Activate.ps1
   ```

2. Run the application:
   ```bash
   python run.py
   ```

3. Open your browser and navigate to:
   - **Login Page (Default)**: http://127.0.0.1:5000/
   - **Homepage**: http://127.0.0.1:5000/home
   - Or use the navbar links to navigate

## Key Features

✅ **Responsive Design**: Bootstrap 5.3.2 for mobile-friendly layout
✅ **Template Inheritance**: All pages extend base.html
✅ **Dynamic Navigation**: url_for() ensures links always work
✅ **Clean Architecture**: Separation of routes, controllers, and templates
✅ **Easy to Extend**: Add new pages by:
   1. Creating new route in app/routes/auth.py
   2. Adding controller method in app/controller/auth.py
   3. Creating new template in app/templates/

## Fixed Issues

✅ Fixed import path: Changed `from app.controllers.auth` to `from app.controller.auth`
✅ Verified all templates exist and are properly linked
✅ Confirmed all routes are registered correctly
✅ Verified controller methods match routes

---
**Status**: ✅ Ready to run! Execute `python run.py` to start the application.
