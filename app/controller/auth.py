"""
BookVerse – Auth / Main Controller
=====================================
Handles all route logic:
  - Login / Register / Logout
  - Forgot password → email token → Reset password
  - Dashboard (protected, stays open after login)
  - Profile edit (username, email, social links, contact email)
  - Admin: Add book, Edit book, Delete book, Edit user, Delete user
  - Books catalog with availability states
  - Borrow / Return books
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

import pymysql
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import config
from app.controller.dashb import (
    build_dashboard_context,
    handle_add_book,
    handle_delete_book,
    handle_delete_user,
    handle_edit_book,
    handle_edit_user,
)
from app.database import (
    borrow_book,
    create_password_reset_token,
    create_user,
    get_book,
    get_user_borrowed_books,
    get_user_by_email,
    get_user_by_id,
    get_user_skills,
    get_valid_reset_token,
    list_books,
    list_users,
    mark_reset_token_used,
    return_book,
    update_user_password_hash,
    update_user_profile,
)
from app.modal.auth import (
    BookForm,
    ForgotPasswordForm,
    LoginForm,
    ProfileForm,
    RegisterForm,
    ResetPasswordForm,
)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(view):
    """Redirect unauthenticated users to the login page."""
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(self, *args, **kwargs)
    return wrapped


def admin_required(view):
    """Allow only admin users (role == 'admin' OR email in ADMIN_EMAILS)."""
    @wraps(view)
    def wrapped(self, *args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        user = get_user_by_id(session["user_id"])
        is_admin = (
            user
            and (
                user.get("role") == "admin"
                or user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
            )
        )
        if not is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.dashboard"))
        return view(self, *args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Email helper
# ---------------------------------------------------------------------------

def _send_reset_email(to_email, reset_url):
    """
    Send a password-reset email via SMTP.
    Falls back to a console print when MAIL_PASSWORD is not configured
    (safe for local development).
    """
    if not config.MAIL_PASSWORD:
        print(f"[BookVerse] Password-reset link (dev mode): {reset_url}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your BookVerse password"
        msg["From"]    = config.MAIL_DEFAULT_SENDER
        msg["To"]      = to_email

        html_body = f"""
        <html>
        <body style="font-family:Inter,sans-serif;background:#0f0f11;color:#e5e5e5;padding:40px;">
          <div style="max-width:520px;margin:auto;background:#1a1a2e;border-radius:16px;padding:40px;">
            <h2 style="color:#7c6af7;margin-bottom:8px;">BookVerse</h2>
            <h3 style="margin-top:0;">Reset your password</h3>
            <p>We received a request to reset the password for your BookVerse account.</p>
            <a href="{reset_url}"
               style="display:inline-block;margin:24px 0;padding:14px 28px;
                      background:#7c6af7;color:#fff;border-radius:10px;
                      text-decoration:none;font-weight:600;">
              Reset Password
            </a>
            <p style="font-size:13px;color:#888;">
              This link expires in 1 hour. If you did not request a reset,
              you can safely ignore this email.
            </p>
          </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT) as server:
            if config.MAIL_USE_TLS:
                server.starttls()
            server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            server.sendmail(config.MAIL_USERNAME, to_email, msg.as_string())
        return True
    except Exception as exc:
        print(f"[BookVerse] Email send error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Controller class
# ---------------------------------------------------------------------------

class AuthController:
    """
    Central request handler.  Each public method maps 1-to-1 to a Flask route.
    """

    # ------------------------------------------------------------------
    # Auth: Login
    # ------------------------------------------------------------------

    def login(self):
        return self._login_template("login.html")

    def login_enhanced(self):
        return self._login_template("index_enhanced.html")

    def _password_is_valid(self, user, password):
        try:
            if check_password_hash(user["password_hash"], password):
                return True
        except (TypeError, ValueError):
            pass
        # Legacy plain-text column fallback
        if user.get("password") == password:
            update_user_password_hash(user["id"], generate_password_hash(password))
            return True
        return False

    def _login_template(self, template_name):
        # If already logged in, go straight to dashboard
        if "user_id" in session:
            return redirect(url_for("auth.dashboard"))

        if request.method == "POST":
            form = LoginForm(request.form)
            if not form.validate():
                for err in form.errors:
                    flash(err, "warning")
            else:
                user = get_user_by_email(form.email)
                if user and self._password_is_valid(user, form.password):
                    session.clear()
                    session.permanent = form.remember
                    session["user_id"]  = user["id"]
                    session["username"] = user["username"]
                    session["role"]     = user.get("role", "user")
                    flash(f"Welcome back, {user['username']}!", "success")
                    next_page = request.args.get("next") or url_for("auth.dashboard")
                    return redirect(next_page)
                flash("Invalid email or password.", "danger")

        return render_template(template_name)

    # ------------------------------------------------------------------
    # Auth: Register
    # ------------------------------------------------------------------

    def register(self):
        if "user_id" in session:
            return redirect(url_for("auth.dashboard"))

        if request.method == "POST":
            form = RegisterForm(request.form)
            if not form.validate():
                for err in form.errors:
                    flash(err, "warning")
            elif get_user_by_email(form.email):
                flash("An account with that email already exists.", "danger")
            else:
                try:
                    password_hash = generate_password_hash(form.password)
                    user_id = create_user(form.username, form.email, password_hash)
                    session.clear()
                    session["user_id"]  = user_id
                    session["username"] = form.username
                    session["role"]     = "user"
                    flash("Your BookVerse account is ready!", "success")
                    return redirect(url_for("auth.dashboard"))
                except pymysql.err.IntegrityError:
                    flash("An account with that email already exists.", "danger")
                except pymysql.MySQLError:
                    flash("We could not create your account right now. Please try again.", "danger")

        return render_template("register.html")

    # ------------------------------------------------------------------
    # Auth: Logout
    # ------------------------------------------------------------------

    def logout(self):
        session.clear()
        flash("You have been signed out successfully.", "info")
        return redirect(url_for("auth.login"))

    # ------------------------------------------------------------------
    # Forgot password
    # ------------------------------------------------------------------

    def forgot_password(self):
        if request.method == "POST":
            form = ForgotPasswordForm(request.form)
            if not form.validate():
                for err in form.errors:
                    flash(err, "warning")
            else:
                user = get_user_by_email(form.email)
                if user:
                    token = create_password_reset_token(user["id"])
                    reset_url = url_for("auth.reset_password", token=token, _external=True)
                    sent = _send_reset_email(user["email"], reset_url)
                    if sent:
                        flash(
                            "A password-reset link has been sent to your email address. "
                            "Please check your inbox (and spam folder).",
                            "success",
                        )
                    else:
                        flash(
                            "Could not send the reset email right now. "
                            "Please contact the library team.",
                            "warning",
                        )
                else:
                    # Generic message to prevent email enumeration
                    flash(
                        "If that email is registered you will receive a reset link shortly.",
                        "info",
                    )
                return redirect(url_for("auth.forgot_password"))

        return render_template("forgot_password.html")

    # ------------------------------------------------------------------
    # Reset password
    # ------------------------------------------------------------------

    def reset_password(self, token):
        reset_row = get_valid_reset_token(token)
        if not reset_row:
            flash("This reset link is invalid or has expired. Please request a new one.", "danger")
            return redirect(url_for("auth.forgot_password"))

        if request.method == "POST":
            form = ResetPasswordForm(request.form)
            if not form.validate():
                for err in form.errors:
                    flash(err, "warning")
                return render_template("reset_password.html", token=token)

            new_hash = generate_password_hash(form.password)
            update_user_password_hash(reset_row["user_id"], new_hash)
            mark_reset_token_used(token)
            flash("Your password has been reset. You can now sign in with your new password.", "success")
            return redirect(url_for("auth.login"))

        return render_template("reset_password.html", token=token)

    # ------------------------------------------------------------------
    # Public pages
    # ------------------------------------------------------------------

    def home(self):
        from app.database import get_dashboard_stats
        books = list_books()[:3]
        stats = get_dashboard_stats()
        return render_template("home.html", books=books, stats=stats)

    def about(self):
        return render_template("about.html")

    def services(self):
        return render_template("services.html")

    def contact(self):
        if request.method == "POST":
            flash("Thanks for reaching out. The library team will review your message soon.", "success")
            return redirect(url_for("auth.contact"))
        return render_template("contact.html")

    # ------------------------------------------------------------------
    # Books catalog
    # ------------------------------------------------------------------

    def books(self):
        all_books  = list_books()
        categories = sorted({b["category"] for b in all_books})
        return render_template("books.html", books=all_books, categories=categories)

    def book_detail(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.books"))
        return render_template("book_detail.html", book=book)

    # ------------------------------------------------------------------
    # Borrow / Return
    # ------------------------------------------------------------------

    @login_required
    def borrow(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("That book could not be found.", "warning")
        elif borrow_book(session["user_id"], book_id):
            flash(f"You borrowed \"{book['title']}\".", "success")
        else:
            flash(f"\"{book['title']}\" is not available right now.", "warning")
        return redirect(url_for("auth.books"))

    @login_required
    def return_borrowed(self, borrowed_id):
        if return_book(session["user_id"], borrowed_id):
            flash("Book returned successfully.", "success")
        else:
            flash("That borrowed record could not be found.", "warning")
        return redirect(url_for("auth.borrowed"))

    # ------------------------------------------------------------------
    # Borrowed page
    # ------------------------------------------------------------------

    @login_required
    def borrowed(self):
        borrowed_books = get_user_borrowed_books(session["user_id"])
        return render_template("borrowedpage.html", borrowed_books=borrowed_books)

    # ------------------------------------------------------------------
    # Dashboard (login-protected, stays open while session is active)
    # ------------------------------------------------------------------

    @login_required
    def dashboard(self):
        ctx = build_dashboard_context(session["user_id"])
        user = get_user_by_id(session["user_id"])
        ctx["current_user"] = user
        ctx["is_admin"] = (
            user.get("role") == "admin"
            or user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
        )
        return render_template("dashboard.html", **ctx)

    # ------------------------------------------------------------------
    # Profile (view + edit)
    # ------------------------------------------------------------------

    @login_required
    def profile(self):
        user           = get_user_by_id(session["user_id"])
        borrowed_books = get_user_borrowed_books(session["user_id"])
        skills         = get_user_skills(session["user_id"])
        return render_template(
            "profile.html",
            user=user,
            borrowed_books=borrowed_books,
            skills=skills,
        )

    @login_required
    def edit_profile(self):
        user = get_user_by_id(session["user_id"])
        if request.method == "POST":
            form = ProfileForm(request.form)
            if not form.validate():
                for err in form.errors:
                    flash(err, "warning")
                return render_template("edit_profile.html", user=user)

            update_user_profile(
                user_id       = session["user_id"],
                username      = form.username,
                email         = form.email,
                linkedin_url  = form.linkedin_url or None,
                github_url    = form.github_url or None,
                instagram_url = form.instagram_url or None,
                contact_email = form.contact_email or None,
            )
            session["username"] = form.username
            flash("Profile updated successfully.", "success")
            return redirect(url_for("auth.profile"))

        return render_template("edit_profile.html", user=user)

    @login_required
    def change_password(self):
        if request.method == "POST":
            current  = request.form.get("current_password", "")
            new_pw   = request.form.get("new_password", "")
            confirm  = request.form.get("confirm_password", "")
            user     = get_user_by_id(session["user_id"])

            if not self._password_is_valid(user, current):
                flash("Current password is incorrect.", "danger")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "warning")
            elif new_pw != confirm:
                flash("Passwords do not match.", "warning")
            else:
                update_user_password_hash(session["user_id"], generate_password_hash(new_pw))
                flash("Password changed successfully.", "success")
                return redirect(url_for("auth.profile"))

        return render_template("change_password.html")

    # ------------------------------------------------------------------
    # Admin: Books CRUD
    # ------------------------------------------------------------------

    @login_required
    def admin_add_book(self):
        user = get_user_by_id(session["user_id"])
        is_admin = (
            user.get("role") == "admin"
            or user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
        )
        if not is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.dashboard"))

        if request.method == "POST":
            success, errors = handle_add_book(request.form)
            if success:
                flash("Book added to the catalog.", "success")
                return redirect(url_for("auth.dashboard"))
            for err in errors:
                flash(err, "warning")

        return render_template("admin_book_form.html", book=None, action="add")

    @login_required
    def admin_edit_book(self, book_id):
        user = get_user_by_id(session["user_id"])
        is_admin = (
            user.get("role") == "admin"
            or user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
        )
        if not is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.dashboard"))

        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.dashboard"))

        if request.method == "POST":
            success, errors = handle_edit_book(book_id, request.form)
            if success:
                flash("Book updated successfully.", "success")
                return redirect(url_for("auth.dashboard"))
            for err in errors:
                flash(err, "warning")
            # re-render form with submitted values so user doesn't lose input
            book = {**book, **request.form}

        return render_template("admin_book_form.html", book=book, action="edit")

    @login_required
    def admin_delete_book(self, book_id):
        user = get_user_by_id(session["user_id"])
        is_admin = (
            user.get("role") == "admin"
            or user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
        )
        if not is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.dashboard"))

        handle_delete_book(book_id)
        flash("Book deleted from catalog.", "info")
        return redirect(url_for("auth.dashboard"))

    # ------------------------------------------------------------------
    # Admin: Users CRUD
    # ------------------------------------------------------------------

    @login_required
    def admin_edit_user(self, user_id):
        current_user = get_user_by_id(session["user_id"])
        is_admin = (
            current_user.get("role") == "admin"
            or current_user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
        )
        if not is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.dashboard"))

        target_user = get_user_by_id(user_id)
        if not target_user:
            flash("User not found.", "warning")
            return redirect(url_for("auth.dashboard"))

        if request.method == "POST":
            success, errors = handle_edit_user(user_id, request.form)
            if success:
                flash("User updated successfully.", "success")
                return redirect(url_for("auth.dashboard"))
            for err in errors:
                flash(err, "warning")

        return render_template("admin_user_form.html", target_user=target_user)

    @login_required
    def admin_delete_user(self, user_id):
        current_user = get_user_by_id(session["user_id"])
        is_admin = (
            current_user.get("role") == "admin"
            or current_user.get("email", "").lower() in [e.lower() for e in config.ADMIN_EMAILS]
        )
        if not is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.dashboard"))

        if str(user_id) == str(session["user_id"]):
            flash("You cannot delete your own account from the admin panel.", "warning")
            return redirect(url_for("auth.dashboard"))

        handle_delete_user(user_id)
        flash("User account deleted.", "info")
        return redirect(url_for("auth.dashboard"))
