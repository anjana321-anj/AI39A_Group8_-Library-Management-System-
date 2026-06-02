"""
BookVerse – Dashboard / Admin Controller Helpers
==================================================
Utility functions used by the admin sections of AuthController.
Keeping these separate makes the main controller file more readable
and allows future extraction into a dedicated admin blueprint.
"""

from app.database import (
    add_book,
    delete_book,
    delete_user,
    get_book,
    get_dashboard_stats,
    get_recent_activity,
    list_books,
    list_users,
    update_book,
    update_user_profile,
)
from app.modal.auth import BookForm


def build_dashboard_context(session_user_id):
    """
    Assemble all data needed to render the dashboard page.

    Parameters
    ----------
    session_user_id : int
        ID of the currently logged-in user (used for future per-user filtering).

    Returns
    -------
    dict
        Template context dictionary with keys: stats, books, recent_activity, users.
    """
    stats           = get_dashboard_stats()
    books           = list_books()
    recent_activity = get_recent_activity()
    users           = list_users()

    return {
        "stats":           stats,
        "books":           books,
        "recent_activity": recent_activity,
        "users":           users,
    }


def handle_add_book(form_data):
    """
    Validate and persist a new book from an admin form submission.

    Returns
    -------
    tuple[bool, list[str]]
        (success, list_of_error_messages)
    """
    form = BookForm(form_data)
    if not form.validate():
        return False, form.errors

    add_book(
        title       = form.title,
        author      = form.author,
        category    = form.category,
        description = form.description,
        image       = form.image,
        isbn        = form.isbn or None,
        publisher   = form.publisher or None,
        year        = form.year_int,
        pages       = form.pages_int,
        language    = form.language,
        available   = form.available_int,
    )
    return True, []


def handle_edit_book(book_id, form_data):
    """
    Validate and apply an edit to an existing book.

    Returns
    -------
    tuple[bool, list[str]]
        (success, list_of_error_messages)
    """
    form = BookForm(form_data)
    if not form.validate():
        return False, form.errors

    update_book(
        book_id     = book_id,
        title       = form.title,
        author      = form.author,
        category    = form.category,
        description = form.description,
        image       = form.image,
        isbn        = form.isbn or None,
        publisher   = form.publisher or None,
        year        = form.year_int,
        pages       = form.pages_int,
        language    = form.language,
        available   = form.available_int,
    )
    return True, []


def handle_delete_book(book_id):
    """Delete a book by id.  No return value needed."""
    delete_book(book_id)


def handle_edit_user(user_id, form_data):
    """
    Validate and apply a profile update for any user (admin action).

    Returns
    -------
    tuple[bool, list[str]]
    """
    from app.modal.auth import ProfileForm
    form = ProfileForm(form_data)
    if not form.validate():
        return False, form.errors

    update_user_profile(
        user_id        = user_id,
        username       = form.username,
        email          = form.email,
        linkedin_url   = form.linkedin_url or None,
        github_url     = form.github_url or None,
        instagram_url  = form.instagram_url or None,
        contact_email  = form.contact_email or None,
    )
    return True, []


def handle_delete_user(user_id):
    """Permanently remove a user account (admin action)."""
    delete_user(user_id)
