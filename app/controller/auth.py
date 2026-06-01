from functools import wraps
import secrets
from datetime import datetime, timedelta

import pymysql
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import (
    add_book,
    borrow_book,
    clear_password_reset_token,
    create_password_reset_request,
    create_user,
    delete_book,
    delete_user,
    get_all_books,
    get_all_users,
    get_book,
    get_dashboard_stats,
    get_recent_activity,
    get_user_by_email,
    get_user_by_id,
    get_user_by_reset_token,
    get_user_by_verification_token,
    get_user_borrowed_books,
    get_user_skills,
    list_books,
    mark_email_verified,
    return_book,
    set_email_verification_token,
    update_book,
    update_user_email_username,
    update_user_password_hash,
    update_user_role,
)


def login_required(view):
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(self, *args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if not session.get("is_admin"):
            flash("Admin access is required to view that page.", "danger")
            return redirect(url_for("auth.dashboard"))
        return view(self, *args, **kwargs)

    return wrapped


class AuthController:
    def _generate_token(self):
        return secrets.token_urlsafe(24)

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
                session["is_admin"] = bool(user.get("is_admin"))
                flash(f"Welcome back, {user['username']}.", "success")
                if not user.get("email_verified"):
                    flash(
                        "Your email is not verified yet. Please check the verification link below.",
                        "info",
                    )
                next_page = request.form.get("next") or request.args.get("next")
                return redirect(next_page or url_for("auth.dashboard"))

            flash("Invalid email or password.", "danger")

        return render_template(template_name)

    def login(self):
        return self._login_template("login.html")

    def login_enhanced(self):
        return self._login_template("index_enhanced.html")

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
                    is_admin = len(get_all_users()) == 0
                    verification_token = self._generate_token()
                    user_id = create_user(
                        username,
                        email,
                        password_hash,
                        is_admin=is_admin,
                        verification_token=verification_token,
                    )
                    session.clear()
                    session["user_id"] = user_id
                    session["username"] = username
                    session["is_admin"] = bool(is_admin)
                    flash("Your BookVerse account is ready.", "success")
                    flash(
                        f"Verify your email: {url_for('auth.verify_email_token', token=verification_token, _external=False)}",
                        "info",
                    )
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

    def view_book(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("That book could not be found.", "warning")
            return redirect(url_for("auth.books"))
        return render_template("book_details.html", book=book)

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

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not username or not email:
                flash("Username and email cannot be blank.", "warning")
            elif email != user["email"] and get_user_by_email(email):
                flash("That email address is already in use.", "danger")
            else:
                update_user_email_username(user["id"], username, email)
                session["username"] = username
                if email != user["email"]:
                    token = self._generate_token()
                    set_email_verification_token(user["id"], token)
                    flash(
                        "Email updated. Please verify your new address using the link below.",
                        "info",
                    )
                    flash(
                        f"Verify here: {url_for('auth.verify_email_token', token=token, _external=False)}",
                        "info",
                    )
                else:
                    flash("Profile updated successfully.", "success")
                user = get_user_by_id(session["user_id"])

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

    def forgot_password(self):
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = get_user_by_email(email) if email else None
            if user:
                token = self._generate_token()
                expires_at = datetime.utcnow() + timedelta(hours=1)
                create_password_reset_request(user["id"], token, expires_at)
                flash(
                    "If that email exists, a reset link has been prepared.",
                    "info",
                )
                flash(
                    f"Reset here: {url_for('auth.reset_password', token=token, _external=False)}",
                    "info",
                )
            else:
                flash(
                    "If that email exists, a reset link has been prepared.",
                    "info",
                )

        return render_template("forgot_password.html")

    def reset_password(self, token):
        user = get_user_by_reset_token(token)
        if not user:
            flash("The password reset link is invalid or expired.", "warning")
            return redirect(url_for("auth.forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "warning")
            elif password != confirm_password:
                flash("Passwords do not match.", "warning")
            else:
                update_user_password_hash(user["id"], generate_password_hash(password))
                clear_password_reset_token(user["id"])
                flash("Your password has been reset. Please sign in again.", "success")
                return redirect(url_for("auth.login"))

        return render_template("reset_password.html", token=token)

    def verify_email(self):
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = get_user_by_email(email) if email else None
            if user and not user.get("email_verified"):
                token = self._generate_token()
                set_email_verification_token(user["id"], token)
                flash(
                    "A verification link has been prepared for your address.",
                    "info",
                )
                flash(
                    f"Verify here: {url_for('auth.verify_email_token', token=token, _external=False)}",
                    "info",
                )
            else:
                flash("If that email exists and is unverified, a link will be prepared.", "info")

        return render_template("verify_email.html")

    def verify_email_token(self, token):
        user = get_user_by_verification_token(token)
        if user:
            if user.get("email_verified"):
                flash("Your email is already verified.", "info")
            else:
                mark_email_verified(user["id"])
                flash("Your email has been verified.", "success")
        else:
            flash("This verification link is invalid or expired.", "warning")
        return redirect(url_for("auth.login"))

    @admin_required
    def admin_users(self):
        users = get_all_users()
        return render_template("admin_users.html", users=users)

    @admin_required
    def edit_user(self, user_id):
        user_record = get_user_by_id(user_id)
        if not user_record:
            flash("User not found.", "warning")
            return redirect(url_for("auth.admin_users"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            is_admin = request.form.get("is_admin") == "on"
            if not username or not email:
                flash("Username and email are required.", "warning")
            elif email != user_record["email"] and get_user_by_email(email):
                flash("That email is already in use.", "danger")
            else:
                update_user_email_username(user_id, username, email)
                update_user_role(user_id, is_admin)
                flash("User record updated.", "success")
                return redirect(url_for("auth.admin_users"))

        return render_template("admin_user_edit.html", user=user_record)

    @admin_required
    def delete_user(self, user_id):
        if session.get("user_id") == user_id:
            flash("You cannot delete your own account while signed in.", "warning")
            return redirect(url_for("auth.admin_users"))
        delete_user(user_id)
        flash("User removed from the platform.", "success")
        return redirect(url_for("auth.admin_users"))

    @admin_required
    def admin_books(self):
        books = get_all_books()
        return render_template("admin_books.html", books=books)

    @admin_required
    def add_book(self):
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            author = request.form.get("author", "").strip()
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()
            image = request.form.get("image", "").strip()
            available = request.form.get("available") == "on"
            if not title or not author or not category:
                flash("Title, author, and category are required.", "warning")
            else:
                add_book(title, author, category, description, image, available)
                flash("Book added successfully.", "success")
                return redirect(url_for("auth.admin_books"))

        return render_template("book_form.html", form_title="Add Book", book=None)

    @admin_required
    def edit_book(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.admin_books"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            author = request.form.get("author", "").strip()
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()
            image = request.form.get("image", "").strip()
            available = request.form.get("available") == "on"
            if not title or not author or not category:
                flash("Title, author, and category are required.", "warning")
            else:
                update_book(book_id, title, author, category, description, image, available)
                flash("Book information updated.", "success")
                return redirect(url_for("auth.admin_books"))

        return render_template("book_form.html", form_title="Edit Book", book=book)

    @admin_required
    def delete_book(self, book_id):
        delete_book(book_id)
        flash("Book removed from the catalog.", "success")
        return redirect(url_for("auth.admin_books"))
