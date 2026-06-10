from functools import wraps
from datetime import datetime, timedelta
from email.message import EmailMessage
import csv
import hashlib
import io
import os
import secrets
import smtplib

import pymysql
from flask import Response, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
from app.database import (
    add_favourite,
    borrow_book,
    cancel_reservation,
    create_book,
    create_fine_payment,
    create_backup_record,
    create_notification,
    create_order,
    create_password_reset_token,
    create_reservation,
    create_user,
    delete_book,
    delete_borrow_record,
    delete_fine_payment,
    delete_fine_record,
    delete_notification,
    delete_notification_admin,
    delete_order,
    delete_review,
    delete_library_review,
    delete_reservation,
    delete_waitlist_admin,
    delete_user,
    expire_reservations,
    force_return_borrow_record,
    generate_return_reminders,
    get_active_profile_picture,
    get_book,
    get_book_review_eligibility,
    get_book_review_statistics,
    get_borrow_record,
    get_dashboard_stats,
    get_favourite_book_ids,
    get_fine_payment,
    get_fine_per_day,
    get_library_review_summary,
    get_library_rating_summary,
    get_order,
    get_recent_activity,
    get_reservation,
    get_user_library_review,
    get_user_active_borrowed_books,
    get_user_borrowed_books,
    get_user_book_rating,
    get_user_by_email,
    get_user_by_id,
    get_user_skills,
    get_valid_password_reset_token,
    is_book_favourite,
    join_waitlist,
    leave_waitlist,
    list_activity_logs,
    list_admin_fine_payments,
    list_admin_fine_records,
    list_admin_book_reviews,
    list_admin_borrows,
    list_admin_library_reviews,
    list_admin_notifications,
    list_admin_orders,
    list_admin_profile_pictures,
    list_admin_reservations,
    list_admin_waitlists,
    list_backup_history,
    list_book_reviews,
    list_borrow_timeline,
    list_profile_picture_history,
    list_books,
    list_profile_updates,
    list_review_moderation_logs,
    list_security_logs,
    list_user_reviews_and_ratings,
    list_user_favourites,
    list_user_fines,
    list_user_notifications,
    list_user_orders,
    list_user_waitlists,
    list_user_profile_updates,
    list_user_reservations,
    list_users,
    log_security_event,
    mark_password_reset_token_used,
    mark_notification_read,
    moderate_book_review,
    moderate_library_review,
    refresh_fine_records,
    remove_favourite,
    remove_profile_picture,
    restore_profile_picture,
    return_book,
    save_profile_picture,
    set_book_rating,
    update_borrow_record,
    update_fine_payment,
    update_fine_record,
    update_fine_record_status,
    update_fine_payment_status,
    update_fine_per_day,
    update_book,
    update_order_admin,
    update_order_payment,
    update_order_status,
    update_profile,
    update_reservation_admin,
    update_reservation_status,
    update_user,
    update_user_password_hash,
    update_waitlist_admin,
    upsert_library_review,
    upsert_review,
    log_event,
)

PROFILE_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "profile_pictures")
ALLOWED_PROFILE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


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
                log_security_event(user["id"], email, "login", request.remote_addr, "Successful login")
                log_event(user["id"], "login", "user", user["id"], "User logged in")
                flash(f"Welcome back, {user['username']}.", "success")
                return redirect(request.args.get("next") or url_for("auth.dashboard"))
            else:
                log_security_event(user["id"] if user else None, email, "failed_login", request.remote_addr, "Failed login attempt")
                flash("Invalid email or password.", "danger")

        return render_template(template_name)

    def register(self):
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone_number = request.form.get("phone_number", "").strip()
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
                    user_id = create_user(username, email, password_hash, phone_number=phone_number)
                    log_event(user_id, "user_created", "user", user_id, "User created")
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
        if session.get("user_id"):
            log_security_event(session["user_id"], None, "logout", request.remote_addr, "Successful logout")
            log_event(session["user_id"], "logout", "user", session["user_id"], "User logged out")
        session.clear()
        flash("You have been signed out.", "info")
        return redirect(url_for("auth.login"))

    def forgot_password(self):
        if request.method == "POST":
            step = request.form.get("step", "email")

            if step == "email":
                email = request.form.get("email", "").strip().lower()
                user = get_user_by_email(email) if email else None
                if not user:
                    flash("No BookVerse account was found for that email.", "warning")
                    return render_template("forgot_password.html", step="email")

                session["reset_user_id"] = user["id"]
                session["reset_email"] = user["email"]
                session["demo_otp"] = "123456"
                flash("Demo OTP generated: 123456", "info")
                return render_template("forgot_password.html", step="otp", email=user["email"], demo_otp="123456")

            if step == "otp":
                otp = request.form.get("otp", "").strip()
                if otp != session.get("demo_otp"):
                    flash("Invalid OTP. Use the demo OTP 123456.", "danger")
                    return render_template(
                        "forgot_password.html",
                        step="otp",
                        email=session.get("reset_email"),
                        demo_otp="123456",
                    )
                session["otp_verified"] = True
                return render_template("forgot_password.html", step="password", email=session.get("reset_email"))

            if step == "password":
                if not session.get("otp_verified") or not session.get("reset_user_id"):
                    flash("Please verify your OTP first.", "warning")
                    return render_template("forgot_password.html", step="email")
                password = request.form.get("password", "")
                confirm_password = request.form.get("confirm_password", "")
                if len(password) < 8:
                    flash("Password must be at least 8 characters long.", "warning")
                    return render_template("forgot_password.html", step="password", email=session.get("reset_email"))
                if password != confirm_password:
                    flash("Passwords do not match.", "warning")
                    return render_template("forgot_password.html", step="password", email=session.get("reset_email"))

                update_user_password_hash(session["reset_user_id"], generate_password_hash(password))
                session.pop("reset_user_id", None)
                session.pop("reset_email", None)
                session.pop("demo_otp", None)
                session.pop("otp_verified", None)
                flash("Password reset successfully. Please sign in.", "success")
                return redirect(url_for("auth.login"))

        return render_template("forgot_password.html", step="email")

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

    def _send_return_reminder_email(self, email, reminder):
        if not config.SMTP_HOST:
            print(f"Return reminder for {email}: {reminder['message']}")
            return

        message = EmailMessage()
        message["Subject"] = "BookVerse return reminder"
        message["From"] = config.SMTP_FROM
        message["To"] = email
        due_date = reminder["due_date"].strftime("%b %d, %Y") if reminder.get("due_date") else "soon"
        message.set_content(
            f"{reminder['title']} is due on {due_date}.\n\n"
            f"Reminder: {reminder['reminder_type']}\n\n"
            "Please return or renew it from your BookVerse dashboard."
        )

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(message)

    def _send_email_verification_code(self, email, code):
        if not config.SMTP_HOST:
            print(f"BookVerse email verification code for {email}: {code}")
            return

        message = EmailMessage()
        message["Subject"] = "Verify your BookVerse email"
        message["From"] = config.SMTP_FROM
        message["To"] = email
        message.set_content(f"Your BookVerse demo verification code is: {code}")

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
        authors = sorted({book["author"] for book in books})
        languages = sorted({book["language"] or "English" for book in books})
        years = sorted({book["publication_year"] for book in books if book.get("publication_year")}, reverse=True)
        favourite_ids = get_favourite_book_ids(session["user_id"]) if session.get("user_id") else set()
        return render_template(
            "books.html",
            books=books,
            categories=categories,
            authors=authors,
            languages=languages,
            years=years,
            favourite_ids=favourite_ids,
        )

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
        notifications = list_user_notifications(session["user_id"], limit=5)
        profile_updates = list_user_profile_updates(session["user_id"])
        profile_picture = get_active_profile_picture(session["user_id"])
        picture_history = list_profile_picture_history(session["user_id"])
        return render_template(
            "profile.html",
            user=user,
            borrowed_books=borrowed_books,
            skills=skills,
            notifications=notifications,
            profile_updates=profile_updates,
            profile_picture=profile_picture,
            picture_history=picture_history,
        )

    @login_required
    def update_profile_picture(self):
        action = request.form.get("action", "upload")
        if action == "remove":
            if remove_profile_picture(session["user_id"], session["user_id"]):
                flash("Profile picture removed successfully.", "success")
            else:
                flash("No active profile picture was found.", "warning")
            return redirect(url_for("auth.profile"))

        uploaded_file = request.files.get("profile_picture")
        if not uploaded_file or not uploaded_file.filename:
            flash("Choose a profile picture to upload.", "warning")
            return redirect(url_for("auth.profile"))

        extension = uploaded_file.filename.rsplit(".", 1)[-1].lower() if "." in uploaded_file.filename else ""
        if extension not in ALLOWED_PROFILE_EXTENSIONS:
            flash("Profile picture must be PNG, JPG, JPEG, WEBP, or GIF.", "warning")
            return redirect(url_for("auth.profile"))

        os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
        safe_name = secure_filename(uploaded_file.filename)
        filename = f"user_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
        absolute_path = os.path.join(PROFILE_UPLOAD_FOLDER, filename)
        uploaded_file.save(absolute_path)
        save_profile_picture(session["user_id"], f"/static/uploads/profile_pictures/{filename}", session["user_id"])
        flash("Profile picture updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    @login_required
    def edit_profile(self):
        user = get_user_by_id(session["user_id"])
        pending = session.get("pending_profile_update")

        if request.method == "POST":
            step = request.form.get("step", "profile")
            if step == "verify_email":
                code = request.form.get("verification_code", "").strip()
                pending = session.get("pending_profile_update")
                if not pending:
                    flash("No pending profile update was found.", "warning")
                elif code != pending.get("verification_code", "123456"):
                    flash("Invalid verification code. Use demo code 123456.", "danger")
                    return render_template("edit_profile.html", user=user, pending=pending, demo_code="123456")
                else:
                    update_profile(
                        session["user_id"],
                        pending["username"],
                        pending["email"],
                        pending["phone"],
                        pending["address"],
                    )
                    session["username"] = pending["username"]
                    session.pop("pending_profile_update", None)
                    flash("Profile updated successfully.", "success")
                    return redirect(url_for("auth.profile"))

            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()

            existing = get_user_by_email(email) if email else None
            if not username or not email:
                flash("Name and email are required.", "warning")
            elif existing and existing["id"] != session["user_id"]:
                flash("That email address is already in use.", "danger")
            elif email != user["email"]:
                verification_code = "123456"
                session["pending_profile_update"] = {
                    "username": username,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "verification_code": verification_code,
                }
                try:
                    self._send_email_verification_code(email, verification_code)
                except (OSError, smtplib.SMTPException) as error:
                    print(f"Email verification failed for {email}: {error}")
                flash("Verification code sent. Demo code: 123456", "info")
                return render_template(
                    "edit_profile.html",
                    user=user,
                    pending=session["pending_profile_update"],
                    demo_code="123456",
                )
            else:
                update_profile(session["user_id"], username, email, phone, address)
                session["username"] = username
                flash("Profile updated successfully.", "success")
                return redirect(url_for("auth.profile"))

        return render_template("edit_profile.html", user=user, pending=pending)

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
                log_event(user["id"], "password_change", "user", user["id"], "Password changed")
                flash("Password updated successfully.", "success")
                return redirect(url_for("auth.profile"))

        return render_template("account_reset_password.html", user=user)

    def services(self):
        return render_template("services.html")

    @login_required
    def dashboard(self):
        reminders = generate_return_reminders(session["user_id"])
        for reminder in reminders:
            try:
                self._send_return_reminder_email(reminder["email"], reminder)
            except (OSError, smtplib.SMTPException) as error:
                print(f"Return reminder email failed for {reminder['email']}: {error}")
        refresh_fine_records(session["user_id"])
        stats = get_dashboard_stats()
        books = list_books()
        recent_activity = get_recent_activity()
        notifications = list_user_notifications(session["user_id"], limit=5)
        user = get_user_by_id(session["user_id"])
        profile_picture = get_active_profile_picture(session["user_id"])
        active_borrows = get_user_active_borrowed_books(session["user_id"])
        active_reservations = list_user_reservations(session["user_id"])
        outstanding_fines = [
            fine for fine in list_user_fines(session["user_id"])
            if fine.get("status") not in {"Paid", "Approved"}
        ]
        return render_template(
            "dashboard.html",
            stats=stats,
            books=books,
            recent_activity=recent_activity,
            notifications=notifications,
            user=user,
            profile_picture=profile_picture,
            active_borrow_count=len(active_borrows),
            active_reservation_count=len(active_reservations),
            outstanding_fine_total=sum(float(fine.get("total_fine") or 0) for fine in outstanding_fines),
        )

    @login_required
    def borrowed(self):
        borrowed_books = get_user_borrowed_books(session["user_id"])
        current_borrows = [
            loan for loan in borrowed_books if loan.get("status") in {"borrowed", "overdue"}
        ]
        returned_books = [
            loan for loan in borrowed_books if loan.get("status") == "returned"
        ]
        return render_template(
            "borrowedpage.html",
            borrowed_books=borrowed_books,
            current_borrows=current_borrows,
            returned_books=returned_books,
        )

    def login_enhanced(self):
        return self._login_template("index_enhanced.html")

    @login_required
    def borrow(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("That book could not be found.", "warning")
        elif borrow_book(session["user_id"], book_id):
            log_event(session["user_id"], "borrow_book", "book", book_id, "Book borrowed")
            flash(f"You borrowed {book['title']}.", "success")
        else:
            flash(f"{book['title']} is not available right now.", "warning")
        return redirect(url_for("auth.books"))

    @login_required
    def return_borrowed(self, borrowed_id):
        returned_book_id = return_book(session["user_id"], borrowed_id)
        if returned_book_id:
            flash("Book returned successfully.", "success")
            return redirect(url_for("auth.book_details", book_id=returned_book_id, returned=1))
        else:
            flash("That borrowed book could not be returned.", "warning")
        return redirect(url_for("auth.borrowed"))

    @login_required
    def reviews_ratings(self):
        reviews = list_user_reviews_and_ratings(session["user_id"])
        rated = [review for review in reviews if review.get("rating")]
        average = round(sum(review["rating"] for review in rated) / len(rated), 1) if rated else 0
        return render_template(
            "reviews_ratings.html",
            reviews=reviews,
            average_rating=average,
            total_reviews=len([review for review in reviews if review.get("review_text")]),
            total_ratings=len(rated),
            library_review=get_user_library_review(session["user_id"]),
            library_summary=get_library_review_summary(),
            book_statistics=get_book_review_statistics(),
        )

    @login_required
    def submit_library_review(self):
        rating = self._safe_int(request.form.get("rating"), 0)
        review_text = request.form.get("review_text", "").strip()
        if rating < 1 or rating > 5:
            flash("Choose a library rating from 1 to 5 stars.", "warning")
        elif len(review_text) < 5:
            flash("Library review must be at least 5 characters.", "warning")
        elif len(review_text) > 1200:
            flash("Library review is too long. Please keep it under 1200 characters.", "warning")
        else:
            upsert_library_review(session["user_id"], rating, review_text)
            flash("Library review saved successfully.", "success")
        return redirect(url_for("auth.reviews_ratings"))

    @login_required
    def remove_library_review(self):
        delete_library_review(session["user_id"])
        flash("Library review deleted successfully.", "success")
        return redirect(url_for("auth.reviews_ratings"))

    @login_required
    def favourites(self):
        return render_template("favourites.html", books=list_user_favourites(session["user_id"]))

    @login_required
    def add_to_favourites(self, book_id):
        if get_book(book_id):
            add_favourite(session["user_id"], book_id)
            flash("Book added to favourites.", "success")
        else:
            flash("Book not found.", "warning")
        return redirect(request.referrer or url_for("auth.books"))

    @login_required
    def remove_from_favourites(self, book_id):
        remove_favourite(session["user_id"], book_id)
        flash("Book removed from favourites.", "info")
        return redirect(request.referrer or url_for("auth.favourites"))

    @login_required
    def reservations(self):
        return render_template(
            "reservations.html",
            reservations=list_user_reservations(session["user_id"]),
        )

    @login_required
    def reserve_book(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
        else:
            reservation_id = create_reservation(session["user_id"], book_id)
            if reservation_id:
                log_event(session["user_id"], "reserve_book", "reservation", reservation_id, "Book reserved")
                flash("Reservation request submitted.", "success")
            else:
                flash("We could not reserve that book right now.", "warning")
        return redirect(request.referrer or url_for("auth.book_details", book_id=book_id))

    @login_required
    def cancel_user_reservation(self, reservation_id):
        cancel_reservation(session["user_id"], reservation_id)
        flash("Reservation cancelled.", "info")
        return redirect(url_for("auth.reservations"))

    @login_required
    def buy_book(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.books"))

        if request.method == "POST":
            quantity = max(self._safe_int(request.form.get("quantity"), 1), 1)
            order_id = create_order(session["user_id"], book_id, quantity)
            if order_id:
                flash("Order created successfully.", "success")
                log_event(session.get("user_id"), "order_created", "order", order_id, "Order created")
                return redirect(url_for("auth.pay_order", order_id=order_id))
            flash("This book is out of stock for purchase.", "warning")

        return render_template("buy_book.html", book=book)

    @login_required
    def orders(self):
        return render_template("orders.html", orders=list_user_orders(session["user_id"]))

    @login_required
    def order_details(self, order_id):
        order = get_order(order_id, session["user_id"])
        if not order:
            flash("Order not found.", "warning")
            return redirect(url_for("auth.orders"))
        return render_template("order_details.html", order=order)

    @login_required
    def pay_order(self, order_id):
        order = get_order(order_id, session["user_id"])
        if not order:
            flash("Order not found.", "warning")
            return redirect(url_for("auth.orders"))

        if request.method == "POST":
            payment_method = request.form.get("payment_method", "").strip()
            allowed_methods = {"Cash Payment", "QR Payment", "Card Payment"}
            if payment_method not in allowed_methods:
                flash("Choose a valid payment method.", "warning")
            else:
                payment_reference = request.form.get("payment_reference", "").strip()
                if payment_method == "Cash Payment":
                    payment_note = "Cash Payment Received Successfully. Please collect your book from the library counter."
                    payment_reference = payment_reference or f"CASH-{order_id}-{datetime.now().strftime('%H%M%S')}"
                    status = "Paid"
                elif payment_method == "QR Payment":
                    payment_note = "Payment Successful through QR Payment."
                    status = "Paid"
                    payment_reference = payment_reference or f"QR-{order_id}-{datetime.now().strftime('%H%M%S')}"
                else:
                    card_last4 = request.form.get("card_number", "").strip()[-4:]
                    payment_note = f"Card payment confirmed ending in {card_last4}" if card_last4 else "Card payment confirmed."
                    payment_reference = payment_reference or f"CARD-{order_id}-{datetime.now().strftime('%H%M%S')}"
                    status = "Paid"

                update_order_payment(
                    order_id,
                    session["user_id"],
                    payment_method,
                    payment_reference,
                    payment_note,
                    status,
                )
                log_event(session.get("user_id"), "order_payment_updated", "order", order_id, "Order payment updated")
                flash("Payment confirmation saved. Receipt is ready.", "success")
                return redirect(url_for("auth.order_receipt", order_id=order_id))

        return render_template("payment.html", order=order)

    @login_required
    def order_receipt(self, order_id):
        order = get_order(order_id, session["user_id"])
        if not order:
            flash("Order not found.", "warning")
            return redirect(url_for("auth.orders"))
        return render_template("receipt.html", order=order)

    @login_required
    def fine_payments(self):
        refresh_fine_records(session["user_id"])
        if request.method == "POST":
            fine_record_id = self._safe_int(request.form.get("fine_record_id"), 0)
            payment_method = request.form.get("payment_method", "").strip()
            transaction_id = request.form.get("transaction_id", "").strip()
            amount = self._safe_float(request.form.get("amount"), 0)
            proof = request.form.get("proof_of_payment", "").strip() or None

            if payment_method not in {"QR Payment", "Bank Transfer", "Cash Payment"}:
                flash("Choose a valid payment method.", "warning")
            elif not transaction_id:
                flash("Transaction ID is required.", "warning")
            elif amount <= 0:
                flash("Payment amount must be greater than zero.", "warning")
            elif create_fine_payment(
                session["user_id"], fine_record_id, payment_method, transaction_id, amount, proof
            ):
                log_event(session["user_id"], "fine_payment", "fine_record", fine_record_id, "Fine payment submitted")
                flash("Fine payment submitted for verification.", "success")
                return redirect(url_for("auth.fine_payments"))
            else:
                flash("That fine could not be paid.", "warning")

        return render_template(
            "fine_payments.html",
            fines=list_user_fines(session["user_id"]),
            fine_per_day=get_fine_per_day(),
        )

    @login_required
    def fine_payment_receipt(self, payment_id):
        payment = get_fine_payment(payment_id, session["user_id"])
        if not payment:
            flash("Payment receipt not found.", "warning")
            return redirect(url_for("auth.fine_payments"))
        return render_template("fine_payment_receipt.html", payment=payment)

    @login_required
    def add_review(self, book_id):
        review_text = request.form.get("review_text", "").strip()
        action_type = get_book_review_eligibility(session["user_id"], book_id)
        if not get_book(book_id):
            flash("Book not found.", "warning")
        elif not action_type:
            flash("You can review a book after borrowing, reserving, or purchasing it.", "warning")
        elif len(review_text) < 5:
            flash("Review must be at least 5 characters.", "warning")
        elif len(review_text) > 1200:
            flash("Review is too long. Please keep it under 1200 characters.", "warning")
        else:
            upsert_review(session["user_id"], book_id, review_text, action_type)
            log_event(session["user_id"], "review_submission", "book", book_id, "Book review submitted")
            flash("Review saved.", "success")
        return redirect(url_for("auth.book_details", book_id=book_id))

    @login_required
    def remove_review(self, review_id):
        delete_review(review_id, session["user_id"], is_admin=session.get("role") == "admin")
        flash("Review removed.", "info")
        return redirect(request.referrer or url_for("auth.books"))

    @login_required
    def rate_book(self, book_id):
        rating = self._safe_int(request.form.get("rating"), 0)
        action_type = get_book_review_eligibility(session["user_id"], book_id)
        if rating < 1 or rating > 5:
            flash("Choose a rating from 1 to 5 stars.", "warning")
        elif not get_book(book_id):
            flash("Book not found.", "warning")
        elif not action_type:
            flash("You can rate a book after borrowing, reserving, or purchasing it.", "warning")
        else:
            set_book_rating(session["user_id"], book_id, rating, action_type)
            log_event(session["user_id"], "rating_submission", "book", book_id, "Book rating submitted")
            flash("Rating saved.", "success")
        return redirect(url_for("auth.book_details", book_id=book_id))

    @admin_required
    def admin_users(self):
        return render_template("admin_users.html", users=list_users(), updates=list_profile_updates())

    @admin_required
    def add_user(self):
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()
            role = request.form.get("role", "user")
            status = request.form.get("status", "active")
            password = request.form.get("password", "BookVerse@123")

            if not username or not email:
                flash("User name and email are required.", "warning")
            elif role not in {"user", "admin"} or status not in {"active", "inactive", "suspended"}:
                flash("Invalid role or status selected.", "warning")
            elif get_user_by_email(email):
                flash("That email address is already in use.", "danger")
            else:
                user_id = create_user(
                    username,
                    email,
                    generate_password_hash(password),
                    phone_number=phone,
                    address=address,
                )
                update_user(user_id, username, email, role, status, phone, address)
                log_event(session.get("user_id"), "user_created", "user", user_id, "User created by admin")
                flash("User created successfully.", "success")
                return redirect(url_for("auth.admin_users"))

        return render_template("admin_user_form.html", user=None)

    @admin_required
    def edit_user(self, user_id):
        user = get_user_by_id(user_id)
        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("auth.admin_users"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()
            role = request.form.get("role", "user")
            status = request.form.get("status", "active")

            if not username or not email:
                flash("User name and email are required.", "warning")
            elif role not in {"user", "admin"} or status not in {"active", "inactive", "suspended"}:
                flash("Invalid role or status selected.", "warning")
            else:
                try:
                    update_user(user_id, username, email, role, status, phone, address)
                    if session.get("user_id") == user_id:
                        session["username"] = username
                        session["role"] = role
                    log_event(session.get("user_id"), "user_updated", "user", user_id, "User updated")
                    flash("User updated successfully.", "success")
                    return redirect(url_for("auth.admin_users"))
                except pymysql.err.IntegrityError:
                    flash("That email address is already in use.", "danger")

        return render_template("admin_user_form.html", user=user)

    @admin_required
    def update_user_status(self, user_id, status):
        user = get_user_by_id(user_id)
        if not user:
            flash("User not found.", "warning")
        elif status not in {"active", "inactive", "suspended"}:
            flash("Invalid user status.", "warning")
        else:
            update_user(
                user_id,
                user["username"],
                user["email"],
                user.get("role", "user"),
                status,
                user.get("phone_number") or user.get("phone"),
                user.get("address"),
            )
            log_event(session.get("user_id"), "user_updated", "user", user_id, f"User status changed to {status}")
            flash("User updated successfully.", "success")
        return redirect(url_for("auth.admin_users"))

    @admin_required
    def delete_user(self, user_id):
        if session.get("user_id") == user_id:
            flash("You cannot delete your own account while signed in.", "warning")
        else:
            log_event(session.get("user_id"), "user_deleted", "user", user_id, "User deleted")
            delete_user(user_id)
            flash("User deleted successfully.", "success")
        return redirect(url_for("auth.admin_users"))

    @admin_required
    def admin_books(self):
        return render_template("admin_books.html", books=list_books())

    @admin_required
    def admin_reservations(self):
        return render_template(
            "admin_reservations.html",
            reservations=list_admin_reservations(),
        )

    @admin_required
    def approve_reservation(self, reservation_id):
        if update_reservation_status(reservation_id, "Approved", "Approved by admin"):
            log_event(session.get("user_id"), "reservation_approved", "reservation", reservation_id, "Reservation approved")
            flash("Reservation approved.", "success")
        else:
            flash("Reservation not found.", "warning")
        return redirect(url_for("auth.admin_reservations"))

    @admin_required
    def reject_reservation(self, reservation_id):
        if update_reservation_status(reservation_id, "Cancelled", "Rejected by admin"):
            log_event(session.get("user_id"), "reservation_rejected", "reservation", reservation_id, "Reservation rejected")
            flash("Reservation rejected.", "info")
        else:
            flash("Reservation not found.", "warning")
        return redirect(url_for("auth.admin_reservations"))

    @admin_required
    def cancel_reservation_admin(self, reservation_id):
        if update_reservation_status(reservation_id, "Cancelled", "Cancelled by admin"):
            log_event(session.get("user_id"), "reservation_cancelled", "reservation", reservation_id, "Reservation cancelled")
            flash("Reservation cancelled.", "info")
        else:
            flash("Reservation not found.", "warning")
        return redirect(url_for("auth.admin_reservations"))

    @admin_required
    def edit_reservation_admin(self, reservation_id):
        reservation = get_reservation(reservation_id)
        if not reservation:
            flash("Reservation not found.", "warning")
            return redirect(url_for("auth.admin_reservations"))

        if request.method == "POST":
            expiry_date = request.form.get("expiry_date", "").strip()
            status = request.form.get("status", "Pending")
            note = request.form.get("admin_note", "").strip() or None
            if status not in {"Pending", "Approved", "Collected", "Cancelled", "Expired"}:
                flash("Invalid reservation status.", "warning")
            else:
                update_reservation_admin(reservation_id, expiry_date, status, note)
                log_event(session.get("user_id"), "reservation_updated", "reservation", reservation_id, "Reservation updated")
                flash("Reservation updated successfully.", "success")
                return redirect(url_for("auth.admin_reservations"))

        return render_template("admin_reservation_form.html", reservation=reservation)

    @admin_required
    def delete_reservation_admin(self, reservation_id):
        log_event(session.get("user_id"), "reservation_deleted", "reservation", reservation_id, "Reservation deleted")
        delete_reservation(reservation_id)
        flash("Reservation removed successfully.", "success")
        return redirect(url_for("auth.admin_reservations"))

    @admin_required
    def admin_orders(self):
        return render_template("admin_orders.html", orders=list_admin_orders())

    @admin_required
    def edit_order_admin(self, order_id):
        order = get_order(order_id)
        if not order:
            flash("Order not found.", "warning")
            return redirect(url_for("auth.admin_orders"))

        if request.method == "POST":
            quantity = self._safe_int(request.form.get("quantity"), 1)
            status = request.form.get("status", "Pending")
            if status not in {"Pending", "Paid", "Processing", "Completed", "Cancelled"}:
                flash("Invalid order status.", "warning")
            elif update_order_admin(order_id, quantity, status):
                log_event(session.get("user_id"), "order_updated", "order", order_id, "Order updated")
                flash("Order updated successfully.", "success")
                return redirect(url_for("auth.admin_orders"))
            else:
                flash("Order not found.", "warning")

        return render_template("admin_order_form.html", order=order)

    @admin_required
    def cancel_order_admin(self, order_id):
        update_order_status(order_id, "Cancelled")
        log_event(session.get("user_id"), "order_cancelled", "order", order_id, "Order cancelled")
        flash("Order cancelled successfully.", "success")
        return redirect(url_for("auth.admin_orders"))

    @admin_required
    def delete_order_admin(self, order_id):
        delete_order(order_id)
        log_event(session.get("user_id"), "order_deleted", "order", order_id, "Order deleted")
        flash("Order deleted successfully.", "success")
        return redirect(url_for("auth.admin_orders"))

    @admin_required
    def admin_fine_payments(self):
        refresh_fine_records()
        if request.method == "POST":
            fine_per_day = self._safe_float(request.form.get("fine_per_day"), 0)
            if fine_per_day <= 0:
                flash("Fine per day must be greater than zero.", "warning")
            else:
                update_fine_per_day(fine_per_day)
                refresh_fine_records()
                flash("Fine setting updated.", "success")
                return redirect(url_for("auth.admin_fine_payments"))

        return render_template(
            "admin_fine_payments.html",
            payments=list_admin_fine_payments(),
            fine_per_day=get_fine_per_day(),
        )

    @admin_required
    def approve_fine_payment(self, payment_id):
        if update_fine_payment_status(payment_id, "Approved"):
            log_event(session.get("user_id"), "payment_approved", "fine_payment", payment_id, "Fine payment approved")
            flash("Fine payment approved.", "success")
        else:
            flash("Payment not found.", "warning")
        return redirect(url_for("auth.admin_fine_payments"))

    @admin_required
    def reject_fine_payment(self, payment_id):
        if update_fine_payment_status(payment_id, "Rejected"):
            log_event(session.get("user_id"), "payment_rejected", "fine_payment", payment_id, "Fine payment rejected")
            flash("Fine payment rejected.", "info")
        else:
            flash("Payment not found.", "warning")
        return redirect(url_for("auth.admin_fine_payments"))

    @admin_required
    def edit_fine_payment(self, payment_id):
        payment = get_fine_payment(payment_id)
        if not payment:
            flash("Payment not found.", "warning")
            return redirect(url_for("auth.admin_fine_payments"))

        if request.method == "POST":
            payment_method = request.form.get("payment_method", "").strip()
            transaction_id = request.form.get("transaction_id", "").strip()
            amount = self._safe_float(request.form.get("amount"), 0)
            proof = request.form.get("proof_of_payment", "").strip() or None
            status = request.form.get("status", "Pending Verification")
            if status not in {"Pending Verification", "Approved", "Rejected"}:
                flash("Invalid payment status.", "warning")
            elif not payment_method or not transaction_id or amount <= 0:
                flash("Payment method, transaction ID, and amount are required.", "warning")
            else:
                update_fine_payment(payment_id, payment_method, transaction_id, amount, proof, status)
                log_event(session.get("user_id"), "payment_updated", "fine_payment", payment_id, "Fine payment updated")
                flash("Fine payment updated successfully.", "success")
                return redirect(url_for("auth.admin_fine_payments"))

        return render_template("admin_fine_payment_form.html", payment=payment)

    @admin_required
    def delete_fine_payment_admin(self, payment_id):
        delete_fine_payment(payment_id)
        log_event(session.get("user_id"), "payment_deleted", "fine_payment", payment_id, "Fine payment deleted")
        flash("Fine payment deleted successfully.", "success")
        return redirect(url_for("auth.admin_fine_payments"))

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _safe_float(self, value, default=0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _book_form_data(self):
        stock_quantity = max(self._safe_int(request.form.get("stock_quantity"), 0), 0)
        total_copies = max(self._safe_int(request.form.get("total_copies"), stock_quantity or 1), stock_quantity, 1)
        available_copies = stock_quantity
        status = "Available" if stock_quantity > 0 else "Out of Stock"
        book_status = request.form.get("book_status", "Available" if stock_quantity > 0 else "Purchased")
        if book_status not in {"Available", "Borrowed", "Reserved", "Purchased", "In Buy List"}:
            book_status = "Available" if stock_quantity > 0 else "Purchased"

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
            "book_status": book_status,
            "price": max(self._safe_float(request.form.get("price"), 0), 0),
            "stock_quantity": stock_quantity,
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
                book_id = create_book(data)
                log_event(session.get("user_id"), "book_added", "book", book_id, "Book added")
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
                log_event(session.get("user_id"), "book_updated", "book", book_id, "Book updated")
                flash("Book updated successfully.", "success")
                return redirect(url_for("auth.admin_books"))

        return render_template("admin_book_form.html", book=book)

    @admin_required
    def delete_book(self, book_id):
        log_event(session.get("user_id"), "book_deleted", "book", book_id, "Book deleted")
        delete_book(book_id)
        flash("Book deleted successfully.", "success")
        return redirect(url_for("auth.admin_books"))

    def book_details(self, book_id):
        book = get_book(book_id)
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for("auth.books"))
        user_id = session.get("user_id")
        return render_template(
            "book_details.html",
            book=book,
            is_favourite=is_book_favourite(user_id, book_id) if user_id else False,
            user_rating=get_user_book_rating(user_id, book_id) if user_id else 0,
            review_eligibility=get_book_review_eligibility(user_id, book_id) if user_id else None,
            reviews=list_book_reviews(book_id),
            library_rating=get_library_rating_summary(),
        )
