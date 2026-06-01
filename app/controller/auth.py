from functools import wraps
import secrets
from datetime import datetime, timedelta

import pymysql
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import (
    add_book,
    add_book_rating,
    add_to_favorites,
    borrow_book,
    clear_password_reset_token,
    create_password_reset_request,
    create_user,
    delete_book,
    delete_user,
    fetch_all,
    get_admin_dashboard_stats,
    get_all_books,
    get_all_users,
    get_average_book_rating,
    get_book,
    get_books_by_category,
    get_category_statistics,
    get_dashboard_stats,
    get_library_statistics,
    get_popular_books,
    get_recommended_books,
    get_recent_activity,
    get_reading_statistics,
    get_recently_added_books,
    get_trending_books,
    get_user_by_email,
    get_user_by_id,
    get_user_by_reset_token,
    get_user_by_verification_token,
    get_user_borrowed_books,
    get_user_favorites,
    get_user_notifications,
    get_user_reading_history,
    get_user_skills,
    is_favorite,
    list_books,
    log_user_activity,
    mark_email_verified,
    mark_notification_as_read,
    remove_from_favorites,
    return_book,
    search_advanced,
    search_books,
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
        flash("User deleted successfully.", "success")
        return redirect(url_for("auth.admin_users"))

    def search_books(self):
        """Handle book search with advanced filtering."""
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        available_only = request.args.get("available_only") == "on"
        
        if not query and not category:
            flash("Please enter a search query or select a category.", "info")
            return render_template("books.html", books=[])
        
        if query and category:
            books = search_books(query, category, available_only)
        elif query:
            books = search_books(query, available_only=available_only)
        else:
            books = get_books_by_category(category)
        
        return render_template("books.html", books=books, search_query=query)

    def add_book_rating(self, book_id):
        """Add or update a book rating and review."""
        if "user_id" not in session:
            flash("Please log in to rate books.", "warning")
            return redirect(url_for("auth.login"))
        
        if request.method == "POST":
            rating = request.form.get("rating", type=int)
            review = request.form.get("review", "").strip()
            
            if not rating or rating < 1 or rating > 5:
                flash("Rating must be between 1 and 5 stars.", "danger")
                return redirect(url_for("auth.view_book", book_id=book_id))
            
            user_id = session["user_id"]
            add_book_rating(user_id, book_id, rating, review)
            flash("Rating submitted successfully!", "success")
            log_user_activity(user_id, "review", f"Rated book {book_id}", book_id)
            
            return redirect(url_for("auth.view_book", book_id=book_id))

    def add_favorite(self, book_id):
        """Add book to user favorites."""
        if "user_id" not in session:
            flash("Please log in to add favorites.", "warning")
            return redirect(url_for("auth.login"))
        
        user_id = session["user_id"]
        add_to_favorites(user_id, book_id)
        flash("Book added to favorites!", "success")
        log_user_activity(user_id, "favorite", f"Added book to favorites", book_id)
        
        return redirect(request.referrer or url_for("auth.books"))

    def remove_favorite(self, book_id):
        """Remove book from user favorites."""
        if "user_id" not in session:
            flash("Please log in.", "warning")
            return redirect(url_for("auth.login"))
        
        user_id = session["user_id"]
        remove_from_favorites(user_id, book_id)
        flash("Book removed from favorites.", "success")
        
        return redirect(request.referrer or url_for("auth.books"))

    def my_favorites(self):
        """Display user's favorite books."""
        if "user_id" not in session:
            flash("Please log in to view favorites.", "warning")
            return redirect(url_for("auth.login"))
        
        user_id = session["user_id"]
        favorites = get_user_favorites(user_id)
        
        return render_template("my_favorites.html", books=favorites)

    def reading_history(self):
        """Display user's reading history."""
        if "user_id" not in session:
            flash("Please log in to view reading history.", "warning")
            return redirect(url_for("auth.login"))
        
        user_id = session["user_id"]
        history = get_user_reading_history(user_id, limit=50)
        
        return render_template("reading_history.html", reading_history=history)

    def recommendations(self):
        """Get book recommendations for user."""
        if "user_id" not in session:
            flash("Please log in for recommendations.", "warning")
            return redirect(url_for("auth.login"))
        
        user_id = session["user_id"]
        recommendations = get_recommended_books(user_id, limit=20)
        
        return render_template("recommendations.html", books=recommendations)

    def trending_books(self):
        """Display trending books."""
        trending = get_trending_books(days=30, limit=20)
        return render_template("trending.html", books=trending)

    def library_stats(self):
        """Display library statistics."""
        stats = get_library_statistics()
        categories = get_category_statistics()
        popular = get_popular_books(limit=10)
        
        return render_template("library_stats.html", 
                             stats=stats, 
                             categories=categories,
                             popular_books=popular)

    @login_required
    def my_stats(self):
        """Display user's personal statistics."""
        user_id = session["user_id"]
        stats = get_reading_statistics(user_id)
        overdue = get_overdue_books(user_id)
        
        return render_template("my_stats.html", stats=stats, overdue_books=overdue)

    @login_required
    def my_notifications(self):
        """Display user's notifications."""
        user_id = session["user_id"]
        notifications = get_user_notifications(user_id)
        
        return render_template("notifications.html", notifications=notifications)

    def mark_notification_read(self, notification_id):
        """Mark notification as read."""
        if "user_id" not in session:
            return {"error": "Unauthorized"}, 401
        
        mark_notification_as_read(notification_id)
        return {"success": True}

    @admin_required
    def admin_dashboard(self):
        """Admin dashboard with comprehensive statistics."""
        stats = get_admin_dashboard_stats()
        recent_books = get_recently_added_books(limit=10)
        trending = get_trending_books(limit=10)
        category_stats = get_category_statistics()
        
        return render_template("admin_dashboard.html",
                             stats=stats,
                             recent_books=recent_books,
                             trending_books=trending,
                             category_stats=category_stats)

    @admin_required
    def admin_reports(self):
        """Generate admin reports."""
        if request.method == "POST":
            report_type = request.form.get("report_type")
            
            if report_type == "overdue":
                # Get all overdue books across all users
                overdue_stats = fetch_all(
                    """
                    SELECT u.username, b.title, br.due_date, 
                           DATEDIFF(NOW(), br.due_date) as days_overdue
                    FROM borrowed_books br
                    JOIN users u ON br.user_id = u.id
                    JOIN books b ON br.book_id = b.id
                    WHERE br.status = 'borrowed' AND br.due_date < NOW()
                    ORDER BY br.due_date ASC
                    """
                )
                return render_template("admin_reports.html", 
                                     report_type="overdue",
                                     data=overdue_stats)
            
            elif report_type == "popularity":
                popularity = get_popular_books(limit=50)
                return render_template("admin_reports.html",
                                     report_type="popularity",
                                     data=popularity)
        
        return render_template("admin_reports.html")

    def advanced_search(self):
        """Advanced search with multiple filters."""
        if request.method == "GET":
            search_params = {
                "title": request.args.get("title", "").strip(),
                "author": request.args.get("author", "").strip(),
                "category": request.args.get("category", "").strip(),
                "rating_min": request.args.get("rating_min", type=int),
                "available_only": request.args.get("available_only") == "on"
            }
            
            # Remove empty parameters
            search_params = {k: v for k, v in search_params.items() if v}
            
            if search_params:
                results = search_advanced(search_params)
            else:
                results = []
            
            return render_template("advanced_search.html", 
                                 results=results,
                                 search_params=search_params)
        
        return render_template("advanced_search.html")
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
