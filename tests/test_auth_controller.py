from werkzeug.security import check_password_hash, generate_password_hash

import pytest

import app as app_module
import app.controller.auth as auth_module
from app.controller.auth import AuthController
from app import create_app


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(app_module, "initialize_mysql_database", lambda: None)
    flask_app = create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return flask_app


def test_safe_int_returns_default_for_invalid_values():
    controller = AuthController()

    assert controller._safe_int("12") == 12
    assert controller._safe_int("not-a-number", default=7) == 7
    assert controller._safe_int(None, default=3) == 3


def test_safe_float_returns_default_for_invalid_values():
    controller = AuthController()

    assert controller._safe_float("12.5") == 12.5
    assert controller._safe_float("not-a-number", default=4.5) == 4.5
    assert controller._safe_float(None, default=2.25) == 2.25


def test_password_is_valid_accepts_existing_password_hash():
    controller = AuthController()
    user = {"id": 1, "password_hash": generate_password_hash("secret123")}

    assert controller._password_is_valid(user, "secret123") is True
    assert controller._password_is_valid(user, "wrong-password") is False


def test_password_is_valid_migrates_legacy_plain_password(monkeypatch):
    controller = AuthController()
    user = {"id": 5, "password_hash": "legacy-value", "password": "plain-secret"}
    updates = {}

    def fake_update_password_hash(user_id, password_hash):
        updates["user_id"] = user_id
        updates["password_hash"] = password_hash

    monkeypatch.setattr(auth_module, "update_user_password_hash", fake_update_password_hash)

    assert controller._password_is_valid(user, "plain-secret") is True
    assert updates["user_id"] == 5
    assert check_password_hash(updates["password_hash"], "plain-secret")


def test_book_form_data_normalizes_stock_and_book_status(app):
    controller = AuthController()

    with app.test_request_context(
        "/admin/books/add",
        method="POST",
        data={
            "title": "Dune",
            "author": "Frank Herbert",
            "genre": "Science Fiction",
            "stock_quantity": "4",
            "total_copies": "2",
            "book_status": "Unknown",
            "price": "-10",
            "book_type": "Audio",
            "publication_year": "1965",
        },
    ):
        data = controller._book_form_data()

    assert data["title"] == "Dune"
    assert data["category"] == "Science Fiction"
    assert data["stock_quantity"] == 4
    assert data["total_copies"] == 4
    assert data["available_copies"] == 4
    assert data["availability_status"] == "Available"
    assert data["book_status"] == "Available"
    assert data["price"] == 0
    assert data["book_type"] == "Physical"
    assert data["publication_year"] == 1965


def test_book_data_is_valid_requires_title_author_and_category():
    controller = AuthController()

    assert controller._book_data_is_valid({"title": "A", "author": "B", "category": "C"})
    assert not controller._book_data_is_valid({"title": "", "author": "B", "category": "C"})
    assert not controller._book_data_is_valid({"title": "A", "author": "", "category": "C"})
    assert not controller._book_data_is_valid({"title": "A", "author": "B", "category": ""})


def test_register_rejects_short_password(app, monkeypatch):
    controller = AuthController()
    messages = []

    monkeypatch.setattr(auth_module, "flash", lambda message, category=None: messages.append((message, category)))
    monkeypatch.setattr(auth_module, "render_template", lambda template, **context: f"rendered:{template}")
    monkeypatch.setattr(auth_module, "get_user_by_email", lambda email: None)

    with app.test_request_context(
        "/register",
        method="POST",
        data={
            "username": "Reader",
            "email": "reader@example.com",
            "password": "short",
            "confirm_password": "short",
        },
    ):
        response = controller.register()

    assert response == "rendered:register.html"
    assert ("Password must be at least 8 characters long.", "warning") in messages


def test_register_creates_user_and_starts_session(app, monkeypatch):
    controller = AuthController()

    monkeypatch.setattr(auth_module, "get_user_by_email", lambda email: None)
    monkeypatch.setattr(auth_module, "create_user", lambda *args, **kwargs: 42)
    monkeypatch.setattr(auth_module, "log_event", lambda *args, **kwargs: None)

    with app.test_request_context(
        "/register",
        method="POST",
        data={
            "username": "Reader",
            "email": "reader@example.com",
            "phone_number": "555-0100",
            "password": "long-enough",
            "confirm_password": "long-enough",
        },
    ):
        response = controller.register()

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        assert auth_module.session["user_id"] == 42
        assert auth_module.session["username"] == "Reader"
        assert auth_module.session["role"] == "user"
