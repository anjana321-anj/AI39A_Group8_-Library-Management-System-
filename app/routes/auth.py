from flask import Blueprint

from app.controller.auth import AuthController


class AuthRoutes:
    def __init__(self):
        self.bp = Blueprint("auth", __name__)
        self.controller = AuthController()

    def register_routes(self):
        self.bp.route("/login", methods=["GET", "POST"])(self.controller.login)
        self.bp.add_url_rule("/", endpoint="index", view_func=self.controller.login, methods=["GET"])
        self.bp.route("/login-enhanced", methods=["GET", "POST"])(self.controller.login_enhanced)
        self.bp.route("/logout", methods=["POST"])(self.controller.logout)
        self.bp.route("/register", methods=["GET", "POST"])(self.controller.register)
        self.bp.route("/verify-email", methods=["GET", "POST"])(self.controller.verify_email)
        self.bp.route("/verify-email/<token>", methods=["GET"])(self.controller.verify_email_token)
        self.bp.route("/forgot-password", methods=["GET", "POST"])(self.controller.forgot_password)
        self.bp.route("/reset-password/<token>", methods=["GET", "POST"])(self.controller.reset_password)
        self.bp.route("/home", methods=["GET"])(self.controller.home)
        self.bp.route("/about", methods=["GET"])(self.controller.about)
        self.bp.route("/books", methods=["GET"])(self.controller.books)
        self.bp.route("/books/<int:book_id>", methods=["GET"])(self.controller.view_book)
        self.bp.route("/books/<int:book_id>/borrowed", methods=["POST"])(self.controller.borrowed)
        self.bp.route("/contact", methods=["GET", "POST"])(self.controller.contact)
        self.bp.route("/profile", methods=["GET", "POST"])(self.controller.profile)
        self.bp.route("/services", methods=["GET"])(self.controller.services)
        self.bp.route("/dashboard", methods=["GET"])(self.controller.dashboard)
        self.bp.route("/borrowed", methods=["GET"])(self.controller.borrowed)
        self.bp.route("/admin/users", methods=["GET"])(self.controller.admin_users)
        self.bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])(self.controller.edit_user)
        self.bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])(self.controller.delete_user)
        self.bp.route("/admin/books", methods=["GET"])(self.controller.admin_books)
        self.bp.route("/admin/books/add", methods=["GET", "POST"])(self.controller.add_book)
        self.bp.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])(self.controller.edit_book)
        self.bp.route("/admin/books/<int:book_id>/delete", methods=["POST"])(self.controller.delete_book)
        return self.bp
