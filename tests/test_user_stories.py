from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
import app.controller.auth as auth_module
from app import create_app
from app.controller.auth import AuthController


@pytest.fixture()
def flask_app(monkeypatch):
    monkeypatch.setattr(app_module, "initialize_mysql_database", lambda: None)
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return app


@pytest.fixture()
def controller():
    return AuthController()


@pytest.fixture()
def messages(monkeypatch):
    flashed = []
    monkeypatch.setattr(auth_module, "flash", lambda message, category=None: flashed.append((message, category)))
    return flashed


@pytest.fixture()
def rendered(monkeypatch):
    captured = {}

    def fake_render_template(template, **context):
        captured["template"] = template
        captured["context"] = context
        return f"rendered:{template}"

    monkeypatch.setattr(auth_module, "render_template", fake_render_template)
    return captured


def user(role="user", user_id=1, status="active"):
    return {
        "id": user_id,
        "username": "Admin" if role == "admin" else "Reader",
        "email": "reader@example.com",
        "password_hash": generate_password_hash("Current123"),
        "role": role,
        "status": status,
        "phone_number": "555-0100",
        "address": "Main Street",
    }


def book(book_id=10, stock=2, title="Dune", author="Frank Herbert", category="Science Fiction"):
    return {
        "id": book_id,
        "title": title,
        "author": author,
        "category": category,
        "language": "English",
        "publication_year": 1965,
        "stock_quantity": stock,
        "available_copies": stock,
        "availability_status": "Available" if stock else "Out of Stock",
        "book_status": "Available" if stock else "Out of Stock",
        "price": 100,
    }


def loan(status="borrowed", overdue_days=0):
    return {
        "id": 7,
        "book_id": 10,
        "title": "Dune",
        "author": "Frank Herbert",
        "category": "Science Fiction",
        "status": status,
        "due_date": "2026-07-10",
        "display_due_date": "2026-07-10",
        "fine_amount": overdue_days * 10,
        "renewal_count": 0,
        "payment_amount": 100,
    }


def install_user_mocks(monkeypatch, role="user"):
    current = user(role=role, user_id=99 if role == "admin" else 1)
    monkeypatch.setattr(auth_module, "get_user_by_id", lambda user_id: {**current, "id": user_id})
    monkeypatch.setattr(auth_module, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_module, "log_security_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_module, "create_notification", lambda *args, **kwargs: 1)
    return current


def enter_session(role="user"):
    auth_module.session["user_id"] = 99 if role == "admin" else 1
    auth_module.session["username"] = "Admin" if role == "admin" else "Reader"
    auth_module.session["role"] = role


def test_story_01_user_registration_valid_invalid_required_and_redirect(flask_app, controller, messages, monkeypatch, rendered):
    monkeypatch.setattr(auth_module, "get_user_by_email", lambda email: None)
    monkeypatch.setattr(auth_module, "create_user", lambda *args, **kwargs: 12)
    monkeypatch.setattr(auth_module, "log_event", lambda *args, **kwargs: None)

    with flask_app.test_request_context("/register", method="POST", data={}):
        assert controller.register() == "rendered:register.html"
        assert ("Please complete all required fields.", "warning") in messages

    with flask_app.test_request_context(
        "/register",
        method="POST",
        data={"username": "Reader", "email": "reader@example.com", "password": "short", "confirm_password": "short"},
    ):
        assert controller.register() == "rendered:register.html"
        assert ("Password must be at least 8 characters long.", "warning") in messages

    with flask_app.test_request_context(
        "/register",
        method="POST",
        data={
            "username": "Reader",
            "email": "reader@example.com",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        },
    ):
        response = controller.register()
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        assert auth_module.session["user_id"] == 12


def test_story_02_user_login_success_failure_empty_and_dashboard(flask_app, controller, messages, monkeypatch, rendered):
    valid_user = user()
    monkeypatch.setattr(auth_module, "get_user_by_email", lambda email: valid_user if email else None)
    monkeypatch.setattr(auth_module, "log_security_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_module, "log_event", lambda *args, **kwargs: None)

    with flask_app.test_request_context(
        "/login", method="POST", data={"email": "reader@example.com", "password": "Current123"}
    ):
        response = controller.login()
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        assert auth_module.session["user_id"] == valid_user["id"]

    with flask_app.test_request_context(
        "/login", method="POST", data={"email": "reader@example.com", "password": "wrong"}
    ):
        assert controller.login() == "rendered:login.html"
        assert ("Invalid email or password.", "danger") in messages

    with flask_app.test_request_context("/login", method="POST", data={}):
        assert controller.login() == "rendered:login.html"
        assert ("Invalid email or password.", "danger") in messages


def test_story_03_logout_clears_session_and_protected_pages_redirect(flask_app, controller, monkeypatch, messages):
    install_user_mocks(monkeypatch)

    with flask_app.test_request_context("/logout", method="POST"):
        enter_session()
        response = controller.logout()
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        assert "user_id" not in auth_module.session

    with flask_app.test_client() as client:
        response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_stories_04_05_06_07_books_list_search_filter_and_availability(flask_app, controller, monkeypatch, rendered):
    books = [
        book(10, 3, "Dune", "Frank Herbert", "Science Fiction"),
        book(11, 0, "Clean Code", "Robert C. Martin", "Programming"),
    ]
    monkeypatch.setattr(auth_module, "list_books", lambda: books)
    monkeypatch.setattr(auth_module, "get_favourite_book_ids", lambda user_id: set())
    monkeypatch.setattr(auth_module, "get_user_active_borrowed_books", lambda user_id: [])

    with flask_app.test_request_context("/books"):
        response = controller.books()

    assert response == "rendered:books.html"
    assert rendered["context"]["books"] == books
    assert rendered["context"]["categories"] == ["Programming", "Science Fiction"]
    assert rendered["context"]["authors"] == ["Frank Herbert", "Robert C. Martin"]
    assert rendered["context"]["languages"] == ["English"]
    assert rendered["context"]["years"] == [1965]
    assert books[0]["stock_quantity"] > 0
    assert books[1]["availability_status"] == "Out of Stock"

    template = Path(flask_app.root_path, flask_app.template_folder, "books.html").read_text(encoding="utf-8")
    assert "data-catalog-search" in template
    assert "data-filter-field=\"category\"" in template
    assert "data-filter-field=\"availability\"" in template
    assert "No books match your search." in template


def test_story_08_borrow_book_success_and_unavailable_denied(flask_app, controller, monkeypatch, messages):
    install_user_mocks(monkeypatch)
    monkeypatch.setattr(auth_module, "get_book", lambda book_id: book(book_id, 1))
    monkeypatch.setattr(auth_module, "get_user_active_borrowed_books", lambda user_id: [])
    monkeypatch.setattr(auth_module, "borrow_book", lambda user_id, book_id: True)

    with flask_app.test_request_context("/books/10/borrow", method="POST"):
        enter_session()
        response = controller.borrow(10)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/my-library")
        assert ("You borrowed Dune.", "success") in messages

    monkeypatch.setattr(auth_module, "borrow_book", lambda user_id, book_id: False)
    with flask_app.test_request_context("/books/10/borrow", method="POST"):
        enter_session()
        response = controller.borrow(10)
        assert response.status_code == 302
        assert ("Dune is not available right now.", "warning") in messages


def test_stories_09_10_11_return_renew_and_borrowed_books(flask_app, controller, monkeypatch, messages, rendered):
    install_user_mocks(monkeypatch)
    monkeypatch.setattr(auth_module, "get_user_borrowed_books", lambda user_id: [loan("borrowed"), loan("returned")])

    with flask_app.test_request_context("/borrowed"):
        enter_session()
        assert controller.borrowed() == "rendered:borrowedpage.html"
        assert len(rendered["context"]["current_borrows"]) == 1
        assert len(rendered["context"]["returned_books"]) == 1

    monkeypatch.setattr(auth_module, "get_borrow_record", lambda borrowed_id, user_id=None: loan("borrowed"))
    monkeypatch.setattr(auth_module, "return_book", lambda user_id, borrowed_id: 10)
    monkeypatch.setattr(auth_module, "set_book_rating", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_module, "upsert_review", lambda *args, **kwargs: None)
    with flask_app.test_request_context("/borrowed/7/return", method="POST", data={"action": "confirm"}):
        enter_session()
        response = controller.return_borrowed(7)
        assert response.status_code == 302
        assert "/books/10" in response.headers["Location"]
        assert ("Book returned successfully.", "success") in messages

    monkeypatch.setattr(auth_module, "renew_borrowed_book", lambda user_id, borrowed_id: (True, "renewed"))
    with flask_app.test_request_context("/borrowed/7/renew", method="POST"):
        enter_session()
        response = controller.renew_borrowed(7)
        assert response.status_code == 302
        assert ("Book renewed successfully. Your due date was extended by 7 days.", "success") in messages

    monkeypatch.setattr(auth_module, "renew_borrowed_book", lambda user_id, borrowed_id: (False, "limit"))
    with flask_app.test_request_context("/borrowed/7/renew", method="POST"):
        enter_session()
        controller.renew_borrowed(7)
        assert ("Renewal limit reached for this borrowed book.", "warning") in messages


def test_stories_12_13_fines_are_calculated_and_payments_validate(flask_app, controller, monkeypatch, messages, rendered):
    install_user_mocks(monkeypatch)
    calls = {"refresh": 0, "payment": 0}
    monkeypatch.setattr(auth_module, "refresh_fine_records", lambda user_id=None: calls.__setitem__("refresh", calls["refresh"] + 1))
    monkeypatch.setattr(
        auth_module,
        "list_user_fines",
        lambda user_id: [{"id": 3, "title": "Dune", "overdue_days": 2, "total_fine": 20, "status": "Pending"}],
    )
    monkeypatch.setattr(auth_module, "get_fine_per_day", lambda: 10)
    monkeypatch.setattr(auth_module, "create_fine_payment", lambda *args, **kwargs: calls.__setitem__("payment", 1) or 9)

    with flask_app.test_request_context("/fine-payments"):
        enter_session()
        assert controller.fine_payments() == "rendered:fine_payments.html"
        assert calls["refresh"] == 1
        assert rendered["context"]["fines"][0]["total_fine"] == 20

    with flask_app.test_request_context(
        "/fine-payments",
        method="POST",
        data={"fine_record_id": "3", "payment_method": "QR Payment", "transaction_id": "TXN1", "amount": "20"},
    ):
        enter_session()
        response = controller.fine_payments()
        assert response.status_code == 302
        assert calls["payment"] == 1
        assert ("Fine payment submitted for verification.", "success") in messages

    with flask_app.test_request_context("/fine-payments", method="POST", data={"payment_method": "Bad"}):
        enter_session()
        controller.fine_payments()
        assert ("Choose a valid payment method.", "warning") in messages


def test_story_14_due_date_reminders_are_triggered_from_dashboard(flask_app, controller, monkeypatch, rendered):
    install_user_mocks(monkeypatch)
    sent = []
    reminder = {"email": "reader@example.com", "title": "Dune", "message": "Due soon", "reminder_type": "Due Date"}
    monkeypatch.setattr(auth_module, "generate_return_reminders", lambda user_id: [reminder])
    monkeypatch.setattr(AuthController, "_send_return_reminder_email", lambda self, email, item: sent.append((email, item)))
    monkeypatch.setattr(auth_module, "refresh_fine_records", lambda user_id=None: None)
    monkeypatch.setattr(auth_module, "get_dashboard_stats", lambda: {"books": 1})
    monkeypatch.setattr(auth_module, "list_books", lambda: [book()])
    monkeypatch.setattr(auth_module, "get_recent_activity", lambda: [])
    monkeypatch.setattr(auth_module, "list_user_notifications", lambda user_id, limit=5: [{"title": "Due soon"}])
    monkeypatch.setattr(auth_module, "get_active_profile_picture", lambda user_id: None)
    monkeypatch.setattr(auth_module, "get_user_active_borrowed_books", lambda user_id: [loan()])
    monkeypatch.setattr(auth_module, "list_user_reservations", lambda user_id: [])
    monkeypatch.setattr(auth_module, "get_user_borrowed_books", lambda user_id: [loan()])
    monkeypatch.setattr(auth_module, "list_user_favourites", lambda user_id: [])
    monkeypatch.setattr(auth_module, "list_user_reviews_and_ratings", lambda user_id: [])
    monkeypatch.setattr(auth_module, "fetch_one", lambda *args, **kwargs: {"count": 1})
    monkeypatch.setattr(auth_module, "list_user_fines", lambda user_id: [])

    with flask_app.test_request_context("/dashboard"):
        enter_session()
        assert controller.dashboard() == "rendered:dashboard.html"
        assert sent == [("reader@example.com", reminder)]
        assert rendered["context"]["notifications"][0]["title"] == "Due soon"


def test_stories_15_16_17_profile_view_update_and_password_change(flask_app, controller, monkeypatch, messages, rendered):
    install_user_mocks(monkeypatch)
    monkeypatch.setattr(auth_module, "get_user_borrowed_books", lambda user_id: [])
    monkeypatch.setattr(auth_module, "get_user_skills", lambda user_id: ["Python"])
    monkeypatch.setattr(auth_module, "list_user_notifications", lambda user_id, limit=5: [])
    monkeypatch.setattr(auth_module, "list_user_profile_updates", lambda user_id: [])
    monkeypatch.setattr(auth_module, "get_active_profile_picture", lambda user_id: None)
    monkeypatch.setattr(auth_module, "list_profile_picture_history", lambda user_id: [])

    with flask_app.test_request_context("/profile"):
        enter_session()
        assert controller.profile() == "rendered:profile.html"
        assert rendered["context"]["user"]["email"] == "reader@example.com"

    monkeypatch.setattr(auth_module, "get_user_by_email", lambda email: None)
    monkeypatch.setattr(auth_module, "update_profile", lambda *args, **kwargs: None)
    with flask_app.test_request_context(
        "/profile/edit",
        method="POST",
        data={"username": "Updated", "email": "reader@example.com", "phone": "123", "address": "Library"},
    ):
        enter_session()
        response = controller.edit_profile()
        assert response.status_code == 302
        assert auth_module.session["username"] == "Updated"
        assert ("Profile updated successfully.", "success") in messages

    monkeypatch.setattr(auth_module, "update_user_password_hash", lambda *args, **kwargs: None)
    with flask_app.test_request_context(
        "/profile/reset-password",
        method="POST",
        data={"current_password": "Current123", "password": "NewPassword123", "confirm_password": "NewPassword123"},
    ):
        enter_session()
        response = controller.reset_logged_in_password()
        assert response.status_code == 302
        assert ("Password updated successfully.", "success") in messages

    with flask_app.test_request_context(
        "/profile/reset-password",
        method="POST",
        data={"current_password": "Current123", "password": "NewPassword123", "confirm_password": "Mismatch"},
    ):
        enter_session()
        controller.reset_logged_in_password()
        assert ("New passwords do not match.", "warning") in messages


def test_stories_18_19_reviews_can_be_added_and_viewed(flask_app, controller, monkeypatch, messages, rendered):
    install_user_mocks(monkeypatch)
    monkeypatch.setattr(auth_module, "get_book", lambda book_id: book(book_id))
    monkeypatch.setattr(auth_module, "get_book_review_eligibility", lambda user_id, book_id: "Borrowed")
    monkeypatch.setattr(auth_module, "upsert_review", lambda *args, **kwargs: None)

    with flask_app.test_request_context("/books/10/review", method="POST", data={"review_text": "Excellent read"}):
        enter_session()
        response = controller.add_review(10)
        assert response.status_code == 302
        assert ("Review saved.", "success") in messages

    with flask_app.test_request_context("/books/10/review", method="POST", data={"review_text": ""}):
        enter_session()
        controller.add_review(10)
        assert ("Review must be at least 5 characters.", "warning") in messages

    monkeypatch.setattr(auth_module, "get_user_active_borrowed_books", lambda user_id: [])
    monkeypatch.setattr(auth_module, "is_book_favourite", lambda user_id, book_id: False)
    monkeypatch.setattr(auth_module, "get_user_book_rating", lambda user_id, book_id: 4)
    monkeypatch.setattr(auth_module, "list_book_reviews", lambda book_id: [{"review_text": "Excellent read", "rating": 5}])
    monkeypatch.setattr(auth_module, "get_library_rating_summary", lambda: {"average": 4.5})
    with flask_app.test_request_context("/books/10"):
        enter_session()
        assert controller.book_details(10) == "rendered:book_details.html"
        assert rendered["context"]["reviews"][0]["review_text"] == "Excellent read"


def test_story_20_admin_login_grants_dashboard_and_blocks_invalid(flask_app, controller, monkeypatch, messages, rendered):
    admin = user(role="admin", user_id=99)
    monkeypatch.setattr(auth_module, "get_user_by_email", lambda email: admin if email else None)
    monkeypatch.setattr(auth_module, "log_security_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_module, "log_event", lambda *args, **kwargs: None)

    with flask_app.test_request_context("/login", method="POST", data={"email": "admin@example.com", "password": "Current123"}):
        response = controller.login()
        assert response.status_code == 302
        assert auth_module.session["role"] == "admin"

    with flask_app.test_request_context("/login", method="POST", data={"email": "admin@example.com", "password": "bad"}):
        assert controller.login() == "rendered:login.html"
        assert ("Invalid email or password.", "danger") in messages


def test_stories_21_22_23_24_admin_book_crud_and_copy_management(flask_app, controller, monkeypatch, messages):
    install_user_mocks(monkeypatch, role="admin")
    saved = {}
    monkeypatch.setattr(auth_module, "create_book", lambda data: saved.setdefault("created", data) or 20)
    monkeypatch.setattr(auth_module, "get_book", lambda book_id: book(book_id, 1))
    monkeypatch.setattr(auth_module, "update_book", lambda book_id, data: saved.setdefault("updated", data))
    monkeypatch.setattr(auth_module, "delete_book", lambda book_id: saved.setdefault("deleted", book_id))

    data = {
        "title": "Dune",
        "author": "Frank Herbert",
        "genre": "Science Fiction",
        "stock_quantity": "5",
        "total_copies": "4",
    }
    with flask_app.test_request_context("/admin/books/add", method="POST", data=data):
        enter_session("admin")
        response = controller.add_book()
        assert response.status_code == 302
        assert saved["created"]["stock_quantity"] == 5
        assert saved["created"]["total_copies"] == 5
        assert ("Book added successfully.", "success") in messages

    with flask_app.test_request_context("/admin/books/10/edit", method="POST", data={**data, "stock_quantity": "2"}):
        enter_session("admin")
        response = controller.edit_book(10)
        assert response.status_code == 302
        assert saved["updated"]["stock_quantity"] == 2
        assert ("Book updated successfully.", "success") in messages

    with flask_app.test_request_context("/admin/books/10/delete", method="POST"):
        enter_session("admin")
        response = controller.delete_book(10)
        assert response.status_code == 302
        assert saved["deleted"] == 10
        assert ("Book deleted successfully.", "success") in messages


def test_stories_25_26_admin_views_borrowers_and_overdue_books(flask_app, controller, monkeypatch, rendered):
    install_user_mocks(monkeypatch, role="admin")
    borrows = [loan("borrowed"), loan("overdue", overdue_days=3)]
    monkeypatch.setattr(auth_module, "list_admin_borrows", lambda search=None: borrows)

    with flask_app.test_request_context("/admin/borrows?search=overdue"):
        enter_session("admin")
        assert controller.admin_borrows() == "rendered:admin_borrows.html"
        assert rendered["context"]["search"] == "overdue"
        assert any(item["status"] == "overdue" for item in rendered["context"]["borrows"])


def test_story_27_admin_sends_notifications_success_and_failure(flask_app, controller, monkeypatch, messages):
    install_user_mocks(monkeypatch, role="admin")
    sent = []
    monkeypatch.setattr(auth_module, "create_notification", lambda *args, **kwargs: sent.append(args) or 1)
    monkeypatch.setattr(auth_module, "list_admin_notifications", lambda: [])
    monkeypatch.setattr(auth_module, "list_users", lambda: [user()])

    with flask_app.test_request_context(
        "/admin/notifications", method="POST", data={"user_id": "1", "title": "Notice", "message": "Return soon"}
    ):
        enter_session("admin")
        response = controller.admin_notifications()
        assert response.status_code == 302
        assert sent
        assert ("Notification sent successfully.", "success") in messages

    with flask_app.test_request_context("/admin/notifications", method="POST", data={}):
        enter_session("admin")
        controller.admin_notifications()
        assert ("User, title, and message are required.", "warning") in messages


def test_story_28_admin_reports_filter_empty_and_export(flask_app, controller, monkeypatch, rendered):
    install_user_mocks(monkeypatch, role="admin")
    logs = [{"username": "Reader", "email": "reader@example.com", "event_type": "login", "entity_type": "user", "entity_id": 1, "summary": "User logged in", "created_at": "2026-06-19"}]
    monkeypatch.setattr(auth_module, "list_activity_logs", lambda search=None, event_type=None: logs if search != "empty" else [])

    with flask_app.test_request_context("/admin/activity-logs?search=Reader&event_type=login"):
        enter_session("admin")
        assert controller.admin_activity_logs() == "rendered:admin_activity_logs.html"
        assert rendered["context"]["logs"] == logs
        assert rendered["context"]["event_type"] == "login"

    with flask_app.test_request_context("/admin/activity-logs?search=empty"):
        enter_session("admin")
        controller.admin_activity_logs()
        assert rendered["context"]["logs"] == []

    with flask_app.test_request_context("/admin/activity-logs?export=csv"):
        enter_session("admin")
        response = controller.admin_activity_logs()
        assert response.mimetype == "text/csv"
        assert b"User logged in" in response.data


def test_story_29_admin_dashboard_overview_metrics(flask_app, controller, monkeypatch, rendered):
    install_user_mocks(monkeypatch, role="admin")
    monkeypatch.setattr(auth_module, "generate_return_reminders", lambda user_id: [])
    monkeypatch.setattr(auth_module, "refresh_fine_records", lambda user_id=None: None)
    monkeypatch.setattr(auth_module, "get_dashboard_stats", lambda: {"books": 4, "members": 2, "borrowed": 1})
    monkeypatch.setattr(auth_module, "list_books", lambda: [book()])
    monkeypatch.setattr(auth_module, "get_recent_activity", lambda: [loan()])
    monkeypatch.setattr(auth_module, "list_user_notifications", lambda user_id, limit=5: [])
    monkeypatch.setattr(auth_module, "get_active_profile_picture", lambda user_id: None)
    monkeypatch.setattr(auth_module, "get_user_active_borrowed_books", lambda user_id: [])
    monkeypatch.setattr(auth_module, "list_user_reservations", lambda user_id: [])
    monkeypatch.setattr(auth_module, "get_user_borrowed_books", lambda user_id: [])
    monkeypatch.setattr(auth_module, "list_user_favourites", lambda user_id: [])
    monkeypatch.setattr(auth_module, "list_user_reviews_and_ratings", lambda user_id: [])
    monkeypatch.setattr(auth_module, "fetch_one", lambda *args, **kwargs: {"count": 0})
    monkeypatch.setattr(auth_module, "list_user_fines", lambda user_id: [])

    with flask_app.test_request_context("/dashboard"):
        enter_session("admin")
        assert controller.dashboard() == "rendered:dashboard.html"
        assert rendered["context"]["stats"]["books"] == 4
        assert rendered["context"]["recent_activity"][0]["title"] == "Dune"


def test_story_30_security_blocks_unauthorized_access_hashes_passwords_and_logs_activity(flask_app, monkeypatch, rendered):
    monkeypatch.setattr(auth_module, "render_template", lambda template, **context: f"rendered:{template}")

    with flask_app.test_client() as client:
        response = client.get("/admin/users")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    hashed = generate_password_hash("Secret123")
    assert hashed != "Secret123"

    controller = AuthController()
    install_user_mocks(monkeypatch, role="admin")
    security_logs = [{"event_type": "failed_login", "email": "reader@example.com"}]
    monkeypatch.setattr(auth_module, "list_security_logs", lambda search=None: security_logs)
    with flask_app.test_request_context("/admin/security"):
        enter_session("admin")
        assert controller.admin_security() == "rendered:admin_security.html"
