from flask import Blueprint
<<<<<<< HEAD
from app.controller.auth import AuthController

class AuthRoutes:
    def __init__(self):
        self.bp = Blueprint('auth', __name__)
        self.controller = AuthController()

    def register_routes(self):
        self.bp.route("/")(
            self.controller.login
        )
        self.bp.route("/login")(
            self.controller.login
        )
        self.bp.route("/register")(
            self.controller.register
        )
        self.bp.route("/home")(
            self.controller.home
        )
        self.bp.route("/about")(
            self.controller.about
        )
        self.bp.route("/books")(
            self.controller.books
        )
        self.bp.route("/contact")(
            self.controller.contact
        )
        self.bp.route("/profile")(
            self.controller.profile
        )
        self.bp.route("/services")(
            self.controller.services
        )
        self.bp.route("/dashboard")(
            self.controller.dashboard
        )
        self.bp.route("/borrowed")(
            self.controller.borrowed
        )
        self.bp.route("/login-enhanced")(
            self.controller.login_enhanced
        )
        return self.bp
    
=======

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
        self.bp.route("/home", methods=["GET"])(self.controller.home)
        self.bp.route("/about", methods=["GET"])(self.controller.about)
        self.bp.route("/books", methods=["GET"])(self.controller.books)
        self.bp.route("/books/<int:book_id>/borrow", methods=["POST"])(self.controller.borrow)
        self.bp.route("/contact", methods=["GET", "POST"])(self.controller.contact)
        self.bp.route("/profile", methods=["GET"])(self.controller.profile)
        self.bp.route("/services", methods=["GET"])(self.controller.services)
        self.bp.route("/dashboard", methods=["GET"])(self.controller.dashboard)
        self.bp.route("/borrowed", methods=["GET"])(self.controller.borrowed)
        self.bp.route("/borrowed/<int:borrowed_id>/return", methods=["POST"])(
            self.controller.return_borrowed
        )
        return self.bp
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
