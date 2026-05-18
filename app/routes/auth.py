from flask import Blueprint
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
        return self.bp
