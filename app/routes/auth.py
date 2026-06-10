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
        self.bp.route("/forgot-password", methods=["GET", "POST"])(self.controller.forgot_password)
        self.bp.route("/reset-password/<token>", methods=["GET", "POST"])(
            self.controller.reset_password
        )
        self.bp.route("/register", methods=["GET", "POST"])(self.controller.register)
        self.bp.route("/home", methods=["GET"])(self.controller.home)
        self.bp.route("/about", methods=["GET"])(self.controller.about)
        self.bp.route("/books", methods=["GET"])(self.controller.books)
        self.bp.route("/books/<int:book_id>", methods=["GET"])(self.controller.book_details)
        self.bp.route("/books/<int:book_id>/borrow", methods=["POST"])(self.controller.borrow)
        self.bp.route("/books/<int:book_id>/favourite", methods=["POST"])(
            self.controller.add_to_favourites
        )
        self.bp.route("/books/<int:book_id>/unfavourite", methods=["POST"])(
            self.controller.remove_from_favourites
        )
        self.bp.route("/books/<int:book_id>/reserve", methods=["POST"])(
            self.controller.reserve_book
        )
        self.bp.route("/books/<int:book_id>/buy", methods=["GET", "POST"])(
            self.controller.buy_book
        )
        self.bp.route("/books/<int:book_id>/review", methods=["POST"])(
            self.controller.add_review
        )
        self.bp.route("/books/<int:book_id>/rating", methods=["POST"])(
            self.controller.rate_book
        )
        self.bp.route("/reviews/<int:review_id>/delete", methods=["POST"])(
            self.controller.remove_review
        )
        self.bp.route("/contact", methods=["GET", "POST"])(self.controller.contact)
        self.bp.route("/profile", methods=["GET"])(self.controller.profile)
        self.bp.route("/profile/edit", methods=["GET", "POST"])(self.controller.edit_profile)
        self.bp.route("/profile/reset-password", methods=["GET", "POST"])(
            self.controller.reset_logged_in_password
        )
        self.bp.route("/services", methods=["GET"])(self.controller.services)
        self.bp.route("/dashboard", methods=["GET"])(self.controller.dashboard)
        self.bp.route("/borrowed", methods=["GET"])(self.controller.borrowed)
        self.bp.route("/borrowed/<int:borrowed_id>/return", methods=["POST"])(
            self.controller.return_borrowed
        )
        self.bp.route("/reviews-ratings", methods=["GET"])(self.controller.reviews_ratings)
        self.bp.route("/favourites", methods=["GET"])(self.controller.favourites)
        self.bp.route("/reservations", methods=["GET"])(self.controller.reservations)
        self.bp.route("/reservations/<int:reservation_id>/cancel", methods=["POST"])(
            self.controller.cancel_user_reservation
        )
        self.bp.route("/orders", methods=["GET"])(self.controller.orders)
        self.bp.route("/orders/<int:order_id>", methods=["GET"])(self.controller.order_details)
        self.bp.route("/orders/<int:order_id>/pay", methods=["GET", "POST"])(
            self.controller.pay_order
        )
        self.bp.route("/orders/<int:order_id>/receipt", methods=["GET"])(
            self.controller.order_receipt
        )
        self.bp.route("/fine-payments", methods=["GET", "POST"])(self.controller.fine_payments)
        self.bp.route("/fine-payments/<int:payment_id>/receipt", methods=["GET"])(
            self.controller.fine_payment_receipt
        )
        self.bp.route("/admin/users", methods=["GET"])(self.controller.admin_users)
        self.bp.route("/admin/users/add", methods=["GET", "POST"])(self.controller.add_user)
        self.bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])(
            self.controller.edit_user
        )
        self.bp.route("/admin/users/<int:user_id>/status/<status>", methods=["POST"])(
            self.controller.update_user_status
        )
        self.bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])(
            self.controller.delete_user
        )
        self.bp.route("/admin/books", methods=["GET"])(self.controller.admin_books)
        self.bp.route("/admin/books/add", methods=["GET", "POST"])(self.controller.add_book)
        self.bp.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])(
            self.controller.edit_book
        )
        self.bp.route("/admin/books/<int:book_id>/delete", methods=["POST"])(
            self.controller.delete_book
        )
        self.bp.route("/admin/reservations", methods=["GET"])(
            self.controller.admin_reservations
        )
        self.bp.route("/admin/reservations/<int:reservation_id>/approve", methods=["POST"])(
            self.controller.approve_reservation
        )
        self.bp.route("/admin/reservations/<int:reservation_id>/reject", methods=["POST"])(
            self.controller.reject_reservation
        )
        self.bp.route("/admin/reservations/<int:reservation_id>/cancel", methods=["POST"])(
            self.controller.cancel_reservation_admin
        )
        self.bp.route("/admin/reservations/<int:reservation_id>/edit", methods=["GET", "POST"])(
            self.controller.edit_reservation_admin
        )
        self.bp.route("/admin/reservations/<int:reservation_id>/delete", methods=["POST"])(
            self.controller.delete_reservation_admin
        )
        self.bp.route("/admin/orders", methods=["GET"])(self.controller.admin_orders)
        self.bp.route("/admin/orders/<int:order_id>/edit", methods=["GET", "POST"])(
            self.controller.edit_order_admin
        )
        self.bp.route("/admin/orders/<int:order_id>/cancel", methods=["POST"])(
            self.controller.cancel_order_admin
        )
        self.bp.route("/admin/orders/<int:order_id>/delete", methods=["POST"])(
            self.controller.delete_order_admin
        )
        self.bp.route("/admin/fine-payments", methods=["GET", "POST"])(
            self.controller.admin_fine_payments
        )
        self.bp.route("/admin/fine-payments/<int:payment_id>/edit", methods=["GET", "POST"])(
            self.controller.edit_fine_payment
        )
        self.bp.route("/admin/fine-payments/<int:payment_id>/approve", methods=["POST"])(
            self.controller.approve_fine_payment
        )
        self.bp.route("/admin/fine-payments/<int:payment_id>/reject", methods=["POST"])(
            self.controller.reject_fine_payment
        )
        self.bp.route("/admin/fine-payments/<int:payment_id>/delete", methods=["POST"])(
            self.controller.delete_fine_payment_admin
        )
        return self.bp
