import pytest

import app as app_module
import app.controller.auth as auth_module
import app.database as database_module
from app import create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(app_module, "initialize_mysql_database", lambda: None)
    monkeypatch.setattr(auth_module, "render_template", lambda template, **context: f"rendered:{template}")

    flask_app = create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with flask_app.test_client() as test_client:
        yield test_client


def test_login_page_renders_without_database(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"rendered:login.html" in response.data


def test_index_route_uses_login_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"rendered:login.html" in response.data


def test_home_route_renders_with_mocked_books_and_stats(client, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "list_books",
        lambda: [
            {"title": "Clean Code", "author": "Robert C. Martin", "category": "Programming"},
            {"title": "Refactoring", "author": "Martin Fowler", "category": "Programming"},
            {"title": "The Pragmatic Programmer", "author": "Andrew Hunt", "category": "Programming"},
            {"title": "Extra Book", "author": "Someone", "category": "Reference"},
        ],
    )
    monkeypatch.setattr(auth_module, "get_dashboard_stats", lambda: {"books": 4, "users": 2})

    captured = {}

    def fake_render_template(template, **context):
        captured["template"] = template
        captured["context"] = context
        return "home-ok"

    monkeypatch.setattr(auth_module, "render_template", fake_render_template)

    response = client.get("/home")

    assert response.status_code == 200
    assert response.data == b"home-ok"
    assert captured["template"] == "home.html"
    assert len(captured["context"]["books"]) == 3
    assert captured["context"]["stats"] == {"books": 4, "users": 2}


def test_protected_route_redirects_anonymous_user_to_login(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "next=/dashboard" in response.headers["Location"]


def test_database_connection_returns_false_when_mysql_fails(monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise AssertionError("cursor should not be reached")

    def raise_mysql_error():
        raise database_module.pymysql.MySQLError("database unavailable")

    monkeypatch.setattr(database_module, "get_connection", raise_mysql_error)

    assert database_module.test_database_connection() is False
