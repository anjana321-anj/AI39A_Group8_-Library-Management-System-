import os

import pymysql
from flask import Flask, request, session, url_for

from app.database import (
    fetch_one,
    get_active_profile_picture,
    get_user_by_id,
    initialize_mysql_database,
    list_user_notifications,
)
from app.routes.auth import AuthRoutes

def create_app():
    # Configure Flask to serve both static and image folders
    app = Flask(__name__,
                static_url_path='/static',
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    app.config.from_object("config")
    app.secret_key = app.config["SECRET_KEY"]
    initialize_mysql_database()
    
    # Add image folder as an additional static folder
    @app.route('/image/<filename>')
    def serve_image(filename):
        from flask import send_from_directory
        return send_from_directory(os.path.join(os.path.dirname(__file__), 'image'), filename)

    auth_routes = AuthRoutes()
    app.register_blueprint(auth_routes.register_routes())

    @app.context_processor
    def inject_nav_context():
        if not session.get("user_id"):
            return {
                "nav_user": None,
                "nav_profile_picture": None,
                "nav_notifications": [],
                "nav_unread_notifications": 0,
            }
        try:
            user_id = session["user_id"]
            unread_row = fetch_one(
                "SELECT COUNT(*) AS total FROM notifications WHERE user_id = %s AND is_read = 0",
                (user_id,),
            )
            return {
                "nav_user": get_user_by_id(user_id),
                "nav_profile_picture": get_active_profile_picture(user_id),
                "nav_notifications": list_user_notifications(user_id, limit=5),
                "nav_unread_notifications": unread_row["total"] if unread_row else 0,
            }
        except pymysql.MySQLError:
            return {
                "nav_user": None,
                "nav_profile_picture": None,
                "nav_notifications": [],
                "nav_unread_notifications": 0,
            }

    @app.context_processor
    def inject_breadcrumbs():
        endpoint = request.endpoint or ""
        if endpoint in {"auth.index", "auth.login", "auth.register", "auth.forgot_password", "auth.reset_password", "serve_image", "static"}:
            return {"breadcrumbs": []}

        crumbs = [{"label": "Home", "url": url_for("auth.home")}]
        simple_pages = {
            "auth.books": "Books",
            "auth.services": "Services",
            "auth.contact": "Contact",
            "auth.profile": "Profile",
            "auth.borrowed": "Borrowed",
            "auth.favourites": "Favourites",
            "auth.reservations": "Reservations",
            "auth.orders": "Orders",
            "auth.reviews_ratings": "Reviews & Ratings",
            "auth.fine_payments": "Fine Payments",
            "auth.dashboard": "Dashboard",
            "auth.admin_users": "User Management",
            "auth.admin_books": "Book Management",
            "auth.admin_orders": "Order Management",
            "auth.admin_reservations": "Reservations",
            "auth.admin_fine_payments": "Fine Payments",
        }

        dashboard_children = {
            "auth.profile",
            "auth.borrowed",
            "auth.favourites",
            "auth.reservations",
            "auth.orders",
            "auth.reviews_ratings",
            "auth.fine_payments",
            "auth.admin_users",
            "auth.admin_books",
            "auth.admin_orders",
            "auth.admin_reservations",
            "auth.admin_fine_payments",
        }
        if endpoint in dashboard_children:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})

        if endpoint == "auth.book_details":
            crumbs.append({"label": "Books", "url": url_for("auth.books")})
            crumbs.append({"label": "Book Details", "url": None})
        elif endpoint == "auth.buy_book":
            crumbs.append({"label": "Books", "url": url_for("auth.books")})
            crumbs.append({"label": "Buy Book", "url": None})
        elif endpoint == "auth.order_details":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Orders", "url": url_for("auth.orders")})
            crumbs.append({"label": "Order Details", "url": None})
        elif endpoint == "auth.order_receipt":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Orders", "url": url_for("auth.orders")})
            crumbs.append({"label": "Receipt", "url": None})
        elif endpoint == "auth.pay_order":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Orders", "url": url_for("auth.orders")})
            crumbs.append({"label": "Proceed To Pay", "url": None})
        elif endpoint in {"auth.add_book", "auth.edit_book"}:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Book Management", "url": url_for("auth.admin_books")})
            crumbs.append({"label": "Book Form", "url": None})
        elif endpoint in {"auth.add_user", "auth.edit_user"}:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "User Management", "url": url_for("auth.admin_users")})
            crumbs.append({"label": "User Form", "url": None})
        elif endpoint in {"auth.edit_order_admin"}:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Order Management", "url": url_for("auth.admin_orders")})
            crumbs.append({"label": "Edit Order", "url": None})
        elif endpoint in {"auth.edit_reservation_admin"}:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Reservations", "url": url_for("auth.admin_reservations")})
            crumbs.append({"label": "Edit Reservation", "url": None})
        elif endpoint in {"auth.edit_fine_payment"}:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Fine Payments", "url": url_for("auth.admin_fine_payments")})
            crumbs.append({"label": "Edit Payment", "url": None})
        elif endpoint == "auth.edit_profile":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Profile", "url": url_for("auth.profile")})
            crumbs.append({"label": "Edit Profile", "url": None})
        elif endpoint in simple_pages:
            crumbs.append({"label": simple_pages[endpoint], "url": None})
        elif endpoint == "auth.reset_logged_in_password":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Profile", "url": url_for("auth.profile")})
            crumbs.append({"label": "Reset Password", "url": None})

        return {"breadcrumbs": crumbs if len(crumbs) > 1 else []}

    return app
