# 🚀 BookVerse – Quick Start Guide

## ✅ VERIFIED & READY TO RUN

---

### Step 1: Install Python dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure your MySQL database
Open `config.py` and update these values (or set them as environment variables):

```python
MYSQL_HOST     = "localhost"
MYSQL_USER     = "root"
MYSQL_PASSWORD = "your_password"
MYSQL_DATABASE = "class_db"
SECRET_KEY     = "change-this-to-something-random"
```

### Step 3: Run the application
```bash
python run.py
```
Both `python run.py` and `python bookverse.py` work identically.

### Step 4: Open in your browser
```
http://127.0.0.1:5000/
```

The **Login Page** loads automatically. All MySQL tables are created on first run — no manual SQL setup needed.

---

## 📋 All Routes at a Glance

```
/                       ← Login page (index)
/login                  ← Sign in
/register               ← Create account
/logout                 ← Sign out (POST)
/forgot-password        ← Request reset email
/reset-password/<token> ← Set new password
/home                   ← Landing page
/about                  ← About BookVerse
/services               ← Library services
/contact                ← Contact form
/books                  ← Book catalog
/books/<id>             ← Book detail page
/books/<id>/borrow      ← Borrow a book (POST)
/borrowed               ← My borrowed books
/borrowed/<id>/return   ← Return a book (POST)
/dashboard              ← Dashboard (login required, stays open)
/profile                ← View profile
/profile/edit           ← Edit profile + social links
/profile/change-password← Change password
/admin/books/add        ← Add book (admin only)
/admin/books/<id>/edit  ← Edit book (admin only)
/admin/books/<id>/delete← Delete book (admin only)
/admin/users/<id>/edit  ← Edit user (admin only)
/admin/users/<id>/delete← Delete user (admin only)
```

---

## 🔑 Making an Admin Account

After registering, run this SQL:
```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
```
Or add your email to `ADMIN_EMAILS` in `config.py`.

Admin users see **Edit** and **Delete** buttons on the dashboard for both books and users, and can access the **Add Book** form.

---

## 🔐 Password Reset (Forgot Password)

1. Click **Forgot password?** on the login page
2. Enter your registered email
3. A reset link is sent (in dev mode the link prints to the terminal if MAIL_PASSWORD is not set)
4. Click the link → enter a new password → sign in

To enable real email sending, set these in `config.py`:
```python
MAIL_USERNAME = "your@gmail.com"
MAIL_PASSWORD = "your_app_password"   # Gmail App Password
MAIL_SERVER   = "smtp.gmail.com"
MAIL_PORT     = 587
MAIL_USE_TLS  = True
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `run.py` | **Start here** — `python run.py` |
| `bookverse.py` | Alias entry point |
| `config.py` | DB, mail, and app settings |
| `app/__init__.py` | Flask app factory |
| `app/database.py` | All database queries |
| `app/controller/auth.py` | All route logic |
| `app/routes/auth.py` | URL → controller mapping |
| `app/modal/auth.py` | Form validation |
| `app/static/css/main.css` | All styles |
| `app/static/js/app.js` | All client-side JS |

---

## 📚 Book Availability

Books can be marked **Available** or **Unavailable** when adding or editing them via the admin panel. The catalog shows a colour-coded badge on every card, and filter buttons let readers quickly find available titles.

---

## 🎉 READY TO LAUNCH

```bash
python run.py
```

→ **http://127.0.0.1:5000/** — Login page loads by default  
→ Register an account or sign in  
→ Explore the dashboard, browse books, borrow titles  
→ Make your account an admin to unlock the full control panel  
