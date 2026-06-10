import os

from flask import Flask, request, url_for

from app.database import initialize_mysql_database
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
            "auth.fine_payments": "Fine Payments",
            "auth.dashboard": "Dashboard",
            "auth.admin_users": "User Management",
            "auth.admin_books": "Book Management",
            "auth.admin_reservations": "Reservations",
            "auth.admin_fine_payments": "Fine Payments",
        }

        dashboard_children = {
            "auth.profile",
            "auth.borrowed",
            "auth.favourites",
            "auth.reservations",
            "auth.orders",
            "auth.fine_payments",
            "auth.admin_users",
            "auth.admin_books",
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
        elif endpoint in {"auth.add_book", "auth.edit_book"}:
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Book Management", "url": url_for("auth.admin_books")})
            crumbs.append({"label": "Book Form", "url": None})
        elif endpoint == "auth.edit_user":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "User Management", "url": url_for("auth.admin_users")})
            crumbs.append({"label": "Edit User", "url": None})
        elif endpoint in simple_pages:
            crumbs.append({"label": simple_pages[endpoint], "url": None})
        elif endpoint == "auth.reset_logged_in_password":
            crumbs.append({"label": "Dashboard", "url": url_for("auth.dashboard")})
            crumbs.append({"label": "Profile", "url": url_for("auth.profile")})
            crumbs.append({"label": "Reset Password", "url": None})

        return {"breadcrumbs": crumbs if len(crumbs) > 1 else []}

    return app
