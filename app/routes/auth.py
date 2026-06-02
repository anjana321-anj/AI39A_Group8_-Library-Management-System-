"""
BookVerse – Route Registrations
=================================
Maps URL patterns to AuthController methods.
All new routes (forgot-password, reset, admin CRUD, book detail, etc.)
are registered here so the controller file stays clean.
"""

from flask import Blueprint

from app.controller.auth import AuthController


class AuthRoutes:
    """Encapsulates blueprint creation and URL binding."""

    def __init__(self):
        self.bp         = Blueprint("auth", __name__)
        self.controller = AuthController()

    def register_routes(self):
        c = self.controller

        # ---- root / login ------------------------------------------------
        self.bp.add_url_rule(
            "/", endpoint="index",
            view_func=c.login, methods=["GET"],
        )
        self.bp.route("/login",          methods=["GET", "POST"])(c.login)
        self.bp.route("/login-enhanced", methods=["GET", "POST"])(c.login_enhanced)
        self.bp.route("/logout",         methods=["POST"])(c.logout)
        self.bp.route("/register",       methods=["GET", "POST"])(c.register)

        # ---- forgot / reset password ------------------------------------
        self.bp.route("/forgot-password", methods=["GET", "POST"])(c.forgot_password)
        self.bp.route("/reset-password/<token>", methods=["GET", "POST"])(c.reset_password)

        # ---- public pages -----------------------------------------------
        self.bp.route("/home",    methods=["GET"])(c.home)
        self.bp.route("/about",   methods=["GET"])(c.about)
        self.bp.route("/services", methods=["GET"])(c.services)
        self.bp.route("/contact", methods=["GET", "POST"])(c.contact)

        # ---- books catalog ----------------------------------------------
        self.bp.route("/books", methods=["GET"])(c.books)
        self.bp.route("/books/<int:book_id>", methods=["GET"])(c.book_detail)
        self.bp.route("/books/<int:book_id>/borrow", methods=["POST"])(c.borrow)

        # ---- borrowed / return ------------------------------------------
        self.bp.route("/borrowed", methods=["GET"])(c.borrowed)
        self.bp.route(
            "/borrowed/<int:borrowed_id>/return", methods=["POST"]
        )(c.return_borrowed)

        # ---- user dashboard & profile -----------------------------------
        self.bp.route("/dashboard", methods=["GET"])(c.dashboard)
        self.bp.route("/profile",   methods=["GET"])(c.profile)
        self.bp.route("/profile/edit", methods=["GET", "POST"])(c.edit_profile)
        self.bp.route("/profile/change-password", methods=["GET", "POST"])(c.change_password)

        # ---- admin: books -----------------------------------------------
        self.bp.route("/admin/books/add",              methods=["GET", "POST"])(c.admin_add_book)
        self.bp.route("/admin/books/<int:book_id>/edit",   methods=["GET", "POST"])(c.admin_edit_book)
        self.bp.route("/admin/books/<int:book_id>/delete", methods=["POST"])(c.admin_delete_book)

        # ---- admin: users -----------------------------------------------
        self.bp.route("/admin/users/<int:user_id>/edit",   methods=["GET", "POST"])(c.admin_edit_user)
        self.bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])(c.admin_delete_user)

        return self.bp
