from functools import wraps

import pymysql
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import (
    borrow_book,
    create_user,
    get_book,
    get_dashboard_stats,
    get_recent_activity,
    get_user_borrowed_books,
    get_user_by_email,
    get_user_by_id,
    get_user_skills,
    list_books,
    return_book,
    update_user_password_hash,
)


def login_required(view):
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
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
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            remember = request.form.get("remember") == "on"
            user = get_user_by_email(email) if email else None

            if user and self._password_is_valid(user, password):
                session.clear()
                session.permanent = remember
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                flash(f"Welcome back, {user['username']}.", "success")
                return redirect(request.args.get("next") or url_for("auth.dashboard"))

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
