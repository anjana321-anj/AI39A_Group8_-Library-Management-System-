# BookVerse – Complete Project Structure & Configuration Guide

## Overview

BookVerse is a Flask-based digital library management platform that allows readers to browse books, borrow and return titles, and manage their profiles. Administrators can add, edit, and delete books and user accounts directly from the dashboard.

---

## Directory Structure

```
main verse/
├── run.py                              ← Primary entry point  (python run.py)
├── bookverse.py                        ← Alias entry point    (python bookverse.py)
├── config.py                           ← All config: DB, mail, secrets
├── requirements.txt                    ← Python dependencies
├── .gitignore                          ← Git ignore rules
├── PROJECT_STRUCTURE.md                ← This file
├── QUICK_START.md                      ← Fast setup guide
│
└── app/
    ├── __init__.py                     ← Flask application factory (create_app)
    ├── database.py                     ← All MySQL helpers (no raw SQL in controllers)
    │
    ├── controller/
    │   ├── __init__.py
    │   ├── auth.py                     ← Main controller: login, register, dashboard,
    │   │                                  profile, forgot/reset password, admin CRUD
    │   └── dashb.py                    ← Dashboard/admin helper functions
    │
    ├── routes/
    │   ├── __init__.py
    │   └── auth.py                     ← URL → controller method bindings (blueprint)
    │
    ├── modal/
    │   ├── __init__.py
    │   └── auth.py                     ← Form validation classes (no ORM)
    │
    ├── image/
    │   └── Logo.png                    ← BookVerse logo
    │
    ├── static/
    │   ├── style.css                   ← Legacy entry: @import css/main.css
    │   ├── css/
    │   │   └── main.css                ← All styles (base + extended features)
    │   └── js/
    │       └── app.js                  ← All client-side JS (base + extended)
    │
    └── templates/
        ├── base.html                   ← Master layout: navbar, footer, flash messages
        │
        ├── ── Public pages ──
        ├── login.html                  ← Sign-in form  (route: / and /login)
        ├── register.html               ← Create account
        ├── home.html                   ← Landing page with hero + stats
        ├── about.html                  ← About BookVerse
        ├── services.html               ← Library services overview
        ├── contact.html                ← Contact form
        │
        ├── ── Auth / Password ──
        ├── forgot_password.html        ← Enter email → receive reset link
        ├── reset_password.html         ← Set new password via token
        ├── change_password.html        ← Change password while logged in
        │
        ├── ── Books ──
        ├── books.html                  ← Full catalog with Available/Unavailable filters
        ├── book_detail.html            ← Single book: all metadata + borrow button
        ├── borrowedpage.html           ← My borrowed books + return button
        │
        ├── ── Profile ──
        ├── profile.html                ← View profile + social links
        ├── edit_profile.html           ← Edit name, email, contact email, social URLs
        │
        ├── ── Dashboard ──
        ├── dashboard.html              ← Stats, book table, user table, activity feed
        │
        ├── ── Admin forms ──
        ├── admin_book_form.html        ← Add or edit a book (admin only)
        ├── admin_user_form.html        ← Edit a user account (admin only)
        │
        └── index_enhanced.html         ← Enhanced login page variant
```

---

## All URL Routes

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/` | GET | Public | Login page (index) |
| `/login` | GET, POST | Public | Sign in |
| `/register` | GET, POST | Public | Create account |
| `/logout` | POST | User | Clear session and redirect |
| `/forgot-password` | GET, POST | Public | Request reset email |
| `/reset-password/<token>` | GET, POST | Public | Set new password via token |
| `/home` | GET | Public | Landing page |
| `/about` | GET | Public | About page |
| `/services` | GET | Public | Services page |
| `/contact` | GET, POST | Public | Contact form |
| `/books` | GET | Public | Book catalog |
| `/books/<id>` | GET | Public | Book detail |
| `/books/<id>/borrow` | POST | User | Borrow a book |
| `/borrowed` | GET | User | My borrowed books |
| `/borrowed/<id>/return` | POST | User | Return a book |
| `/dashboard` | GET | User | Dashboard (stays open while logged in) |
| `/profile` | GET | User | View profile |
| `/profile/edit` | GET, POST | User | Edit profile + social links |
| `/profile/change-password` | GET, POST | User | Change password |
| `/admin/books/add` | GET, POST | Admin | Add a new book |
| `/admin/books/<id>/edit` | GET, POST | Admin | Edit a book |
| `/admin/books/<id>/delete` | POST | Admin | Delete a book |
| `/admin/users/<id>/edit` | GET, POST | Admin | Edit any user |
| `/admin/users/<id>/delete` | POST | Admin | Delete a user |

---

## MySQL Tables

| Table | Purpose |
|-------|---------|
| `users` | Registered readers and admins |
| `books` | Library catalog with availability flag |
| `borrowed_books` | Borrow/return ledger |
| `skills` | Reader skill tags on the profile page |
| `password_resets` | One-time tokens for forgot-password flow |

---

## Feature Summary

### Authentication & Session
- Login keeps dashboard open (session stays active until logout)
- Logout clears session and redirects to login
- Register creates a new account and auto-logs in

### Password Recovery
- Forgot password → email with a secure 1-hour token link
- Reset password page verifies token and updates password hash
- Change password from profile (requires current password)

### Profile
- Edit: username, login email, contact email (public), LinkedIn, GitHub, Instagram
- Social pills with brand icons shown on the profile card
- Contact email can differ from login email

### Books Catalog
- Available / Unavailable badge on every book card
- Filter buttons: All, Available, Unavailable, by Category
- Book detail page: description, ISBN, publisher, year, pages, language

### Borrow / Return
- Borrow button only active when book is available and user is signed in
- Return button on borrowed books list
- Due date shown (21 days from borrow date)

### Dashboard
- Stats row: Total Books, Available, Unavailable, Borrowed, Members
- Book catalog table with Edit/Delete (admin only)
- Users table with Edit/Delete (admin only)
- Recent activity feed

### Admin Controls (role = 'admin' or email in ADMIN_EMAILS)
- Add book with full metadata (title, author, category, description, cover URL, ISBN, publisher, year, pages, language, availability)
- Edit / Delete any book
- Edit / Delete any user account

---

## Running the Application

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure MySQL
Edit `config.py` or set environment variables:
```
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=class_db
SECRET_KEY=your-secret-key
```

### 3. Start the server
```bash
python run.py
# or
python bookverse.py
```

### 4. Open in browser
```
http://127.0.0.1:5000/
```

The database tables are created automatically on first run.

---

## Making a User an Admin

Run this SQL in your MySQL client:
```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
```

Or add the email to `ADMIN_EMAILS` in `config.py`:
```python
ADMIN_EMAILS = "your@email.com"
```

---

**Status**: ✅ Ready to run — `python run.py`
