from functools import wraps
from datetime import datetime, timedelta
from email.message import EmailMessage
import hashlib
import secrets
import smtplib

import pymysql
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import config
from app.database import (
    borrow_book,
    create_book,
    create_password_reset_token,
    create_user,
    delete_book,
    delete_user,
    get_book,
    get_dashboard_stats,
    get_recent_activity,
    get_user_borrowed_books,
    get_user_by_email,
    get_user_by_id,
    get_user_skills,
    get_valid_password_reset_token,
    list_books,
    list_users,
    mark_password_reset_token_used,
    return_book,
    update_book,
    update_user,
    update_user_password_hash,
)


def login_required(view):
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        user = get_user_by_id(session["user_id"])
        if not user or user.get("status", "active") != "active":
            session.clear()
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        session["username"] = user["username"]
        session["role"] = user.get("role", "user")
        return view(self, *args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))

        user = get_user_by_id(session["user_id"])
        if not user or user.get("role") != "admin" or user.get("status", "active") != "active":
            flash("Admin access is required for that page.", "danger")
            return redirect(url_for("auth.dashboard"))
        return view(self, *args, **kwargs)

    return wrapped


class AuthController:
    def login(self):
        return self._login_template("login.html")

    def _password_is_valid(self, user, password):
        try:
            if check_password_hash(user["password_hash"], password):
                return True
        except (TypeError, ValueError):
            pass

        if user.get("password") == password:
            update_user_password_hash(user["id"], generate_password_hash(password))
            return True

        return False

    def _login_template(self, template_name):
        if request.method == "GET" and session.get("user_id"):
            return redirect(url_for("auth.dashboard"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            remember = request.form.get("remember") == "on"
            user = get_user_by_email(email) if email else None

            if user and user.get("status", "active") != "active":
                flash("This account is not active. Please contact support.", "danger")
            elif user and self._password_is_valid(user, password):
                session.clear()
                session.permanent = remember
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user.get("role", "user")
                flash(f"Welcome back, {user['username']}.", "success")
                return redirect(request.args.get("next") or url_for("auth.dashboard"))
            else:
                flash("Invalid email or password.", "danger")

        return render_template(template_name)

    def register(self):
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not username or not email or not password:
                flash("Please complete all required fields.", "warning")
            elif len(password) < 8:
                flash("Password must be at least 8 characters long.", "warning")
            elif password != confirm_password:
                flash("Passwords do not match.", "warning")
            elif get_user_by_email(email):
                flash("An account with that email already exists.", "danger")
            else:
                try:
                    password_hash = generate_password_hash(password)
                    user_id = create_user(username, email, password_hash)
                    session.clear()
                    session["user_id"] = user_id
                    session["username"] = username
                    session["role"] = "user"
                    flash("Your BookVerse account is ready.", "success")
                    return redirect(url_for("auth.dashboard"))
                except pymysql.err.IntegrityError:
                    flash("An account with that email already exists.", "danger")
                except pymysql.MySQLError:
                    flash("We could not create your account right now.", "danger")

        return render_template("register.html")

    def logout(self):
        session.clear()
        flash("You have been signed out.", "info")
        return redirect(url_for("auth.login"))

    def forgot_password(self):
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = get_user_by_email(email) if email else None

            if user:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                expires_at = datetime.now() + timedelta(hours=1)
                create_password_reset_token(user["id"], token_hash, expires_at)
                reset_link = url_for("auth.reset_password", token=token, _external=True)
                try:
                    self._send_password_reset_email(user["email"], reset_link)
                except (OSError, smtplib.SMTPException) as error:
                    print(f"Password reset email failed for {user['email']}: {error}")

            flash("If that email is registered, a password reset link has been sent.", "info")
            return redirect(url_for("auth.login"))

        return render_template("forgot_password.html")

    def reset_password(self, token):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        reset_record = get_valid_password_reset_token(token_hash)
        if not reset_record:
            flash("That password reset link is invalid or expired.", "danger")
            return redirect(url_for("auth.forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "warning")
            elif password != confirm_password:
                flash("Passwords do not match.", "warning")
            else:
                update_user_password_hash(reset_record["user_id"], generate_password_hash(password))
                mark_password_reset_token_used(reset_record["id"])
                flash("Your password has been reset. Please sign in.", "success")
                return redirect(url_for("auth.login"))

        return render_template("reset_password.html", token=token, reset_record=reset_record)

    def _send_password_reset_email(self, email, reset_link):
        if not config.SMTP_HOST:
            print(f"Password reset link for {email}: {reset_link}")
            return

        message = EmailMessage()
        message["Subject"] = "Reset your BookVerse password"
        message["From"] = config.SMTP_FROM
        message["To"] = email
        message.set_content(
            f"Use this link to reset your BookVerse password:\n\n{reset_link}\n\n"
            "This link expires in 1 hour."
        )

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(message)

    def home(self):
        books = list_books()[:3]
        stats = get_dashboard_stats()
        return render_template("home.html", books=books, stats=stats)

    def about(self):
        return render_template("about.html")

    def books(self):
        books = list_books()
        categories = sorted({book["category"] for book in books})
        return render_template("books.html", books=books, categories=categories)

    def contact(self):
        if request.method == "POST":
            flash("Thanks for reaching out. The library team will review your message.", "success")
            return redirect(url_for("auth.contact"))
        return render_template("contact.html")

    @login_required
    def profile(self):
        user = get_user_by_id(session["user_id"])
        borrowed_books = get_user_borrowed_books(session["user_id"])
        skills = get_user_skills(session["user_id"])
        return render_template(
            "profile.html",
            user=user,
            borrowed_books=borrowed_books,
            skills=skills,
        )

    @login_required
    def reset_logged_in_password(self):
        user = get_user_by_id(session["user_id"])
        if request.method == "POST":
            current_password = request.form.get("current_password", "")
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not self._password_is_valid(user, current_password):
                flash("Current password is incorrect.", "danger")
            elif len(password) < 8:
                flash("New password must be at least 8 characters long.", "warning")
            elif password != confirm_password:
                flash("New passwords do not match.", "warning")
            else:
                update_user_password_hash(user["id"], generate_password_hash(password))
                flash("Password updated successfully.", "success")
                return redirect(url_for("auth.profile"))

        return render_template("account_reset_password.html", user=user)

    def services(self):
        return render_template("services.html")

    @login_required
    def dashboard(self):
        stats = get_dashboard_stats()
        books = list_books()
        recent_activity = get_recent_activity()
        return render_template(
            "dashboard.html",
            stats=stats,
            books=books,
            recent_activity=recent_activity,
        )

    @login_required
    def borrowed(self):
        borrowed_books = get_user_borrowed_books(session["user_id"])
        return render_template("borrowedpage.html", borrowed_books=borrowed_books)

    def login_enhanced(self):
        return self._login_template("index_enhanced.html")

    @login_required
    def borrow(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("That book could not be found.", "warning")
        elif borrow_book(session["user_id"], book_id):
            flash(f"You borrowed {book['title']}.", "success")
        else:
            flash(f"{book['title']} is not available right now.", "warning")
        return redirect(url_for("auth.books"))

    @login_required
    def return_borrowed(self, borrowed_id):
        if return_book(session["user_id"], borrowed_id):
            flash("Book returned successfully.", "success")
        else:
            flash("That borrowed book could not be returned.", "warning")
        return redirect(url_for("auth.borrowed"))

    @admin_required
    def admin_users(self):
        return render_template("admin_users.html", users=list_users())

    @admin_required
    def edit_user(self, user_id):
        user = get_user_by_id(user_id)
        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("auth.admin_users"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            role = request.form.get("role", "user")
            status = request.form.get("status", "active")

            if not username or not email:
                flash("User name and email are required.", "warning")
            elif role not in {"user", "admin"} or status not in {"active", "inactive"}:
                flash("Invalid role or status selected.", "warning")
            else:
                try:
                    update_user(user_id, username, email, role, status)
                    if session.get("user_id") == user_id:
                        session["username"] = username
                        session["role"] = role
                    flash("User updated successfully.", "success")
                    return redirect(url_for("auth.admin_users"))
                except pymysql.err.IntegrityError:
                    flash("That email address is already in use.", "danger")

        return render_template("admin_user_form.html", user=user)

    @admin_required
    def delete_user(self, user_id):
        if session.get("user_id") == user_id:
            flash("You cannot delete your own account while signed in.", "warning")
        else:
            delete_user(user_id)
            flash("User deleted successfully.", "success")
        return redirect(url_for("auth.admin_users"))

    @admin_required
    def admin_books(self):
        return render_template("admin_books.html", books=list_books())

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _book_form_data(self):
        total_copies = max(self._safe_int(request.form.get("total_copies"), 1), 1)
        available_copies = max(self._safe_int(request.form.get("available_copies"), 0), 0)
        available_copies = min(available_copies, total_copies)
        status = request.form.get("availability_status", "Available")
        if status not in {"Available", "Unavailable"}:
            status = "Available"
        if status == "Unavailable":
            available_copies = 0
        if available_copies == 0:
            status = "Unavailable"

        publication_year = request.form.get("publication_year", "").strip()
        return {
            "title": request.form.get("title", "").strip(),
            "author": request.form.get("author", "").strip(),
            "category": request.form.get("genre", "").strip(),
            "isbn": request.form.get("isbn", "").strip() or None,
            "publication_year": self._safe_int(publication_year, None) if publication_year else None,
            "publisher": request.form.get("publisher", "").strip() or None,
            "language": request.form.get("language", "").strip() or "English",
            "description": request.form.get("description", "").strip() or None,
            "image": request.form.get("image", "").strip() or None,
            "total_copies": total_copies,
            "available_copies": available_copies,
            "availability_status": status,
        }

    def _book_data_is_valid(self, data):
        return bool(data["title"] and data["author"] and data["category"])

    @admin_required
    def add_book(self):
        if request.method == "POST":
            data = self._book_form_data()
            if not self._book_data_is_valid(data):
                flash("Book title, author, and genre are required.", "warning")
            else:
                create_book(data)
                flash("Book added successfully.", "success")
                return redirect(url_for("auth.admin_books"))

        return render_template("admin_book_form.html", book=None)

    @admin_required
    def edit_book(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.admin_books"))

        if request.method == "POST":
            data = self._book_form_data()
            if not self._book_data_is_valid(data):
                flash("Book title, author, and genre are required.", "warning")
            else:
                update_book(book_id, data)
                flash("Book updated successfully.", "success")
                return redirect(url_for("auth.admin_books"))

        return render_template("admin_book_form.html", book=book)

    @admin_required
    def delete_book(self, book_id):
        delete_book(book_id)
        flash("Book deleted successfully.", "success")
        return redirect(url_for("auth.admin_books"))

    def book_details(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.books"))
        return render_template("book_details.html", book=book)
