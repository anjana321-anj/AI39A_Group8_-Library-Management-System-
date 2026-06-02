"""
BookVerse – Auth Data Models
==============================
Lightweight validation helpers that keep validation logic out of controllers.
These are plain Python classes – no ORM dependency.
"""

import re

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
URL_RE   = re.compile(r"^https?://\S+$")


class RegisterForm:
    """Validate and normalise a user-registration payload."""

    def __init__(self, form_data):
        self.username         = (form_data.get("username", "") or "").strip()
        self.email            = (form_data.get("email", "") or "").strip().lower()
        self.password         = form_data.get("password", "") or ""
        self.confirm_password = form_data.get("confirm_password", "") or ""
        self.errors = []

    def validate(self):
        if not self.username:
            self.errors.append("Username is required.")
        elif len(self.username) < 2:
            self.errors.append("Username must be at least 2 characters.")

        if not self.email or not EMAIL_RE.match(self.email):
            self.errors.append("A valid email address is required.")

        if len(self.password) < 8:
            self.errors.append("Password must be at least 8 characters.")

        if self.password != self.confirm_password:
            self.errors.append("Passwords do not match.")

        return not bool(self.errors)


class LoginForm:
    """Validate a login payload."""

    def __init__(self, form_data):
        self.email    = (form_data.get("email", "") or "").strip().lower()
        self.password = form_data.get("password", "") or ""
        self.remember = form_data.get("remember") == "on"
        self.errors   = []

    def validate(self):
        if not self.email or not EMAIL_RE.match(self.email):
            self.errors.append("Enter a valid email address.")
        if not self.password:
            self.errors.append("Password is required.")
        return not bool(self.errors)


class ProfileForm:
    """Validate a profile-update payload."""

    def __init__(self, form_data):
        self.username      = (form_data.get("username", "") or "").strip()
        self.email         = (form_data.get("email", "") or "").strip().lower()
        self.linkedin_url  = (form_data.get("linkedin_url", "") or "").strip()
        self.github_url    = (form_data.get("github_url", "") or "").strip()
        self.instagram_url = (form_data.get("instagram_url", "") or "").strip()
        self.contact_email = (form_data.get("contact_email", "") or "").strip().lower()
        self.errors = []

    def validate(self):
        if not self.username or len(self.username) < 2:
            self.errors.append("Username must be at least 2 characters.")
        if not self.email or not EMAIL_RE.match(self.email):
            self.errors.append("A valid email address is required.")
        for url_field, label in [
            (self.linkedin_url, "LinkedIn"),
            (self.github_url, "GitHub"),
            (self.instagram_url, "Instagram"),
        ]:
            if url_field and not URL_RE.match(url_field):
                self.errors.append(f"{label} URL must start with http:// or https://.")
        if self.contact_email and not EMAIL_RE.match(self.contact_email):
            self.errors.append("Contact email is not valid.")
        return not bool(self.errors)


class BookForm:
    """Validate an add / edit book payload."""

    def __init__(self, form_data):
        self.title       = (form_data.get("title", "") or "").strip()
        self.author      = (form_data.get("author", "") or "").strip()
        self.category    = (form_data.get("category", "") or "").strip()
        self.description = (form_data.get("description", "") or "").strip()
        self.image       = (form_data.get("image", "") or "").strip()
        self.isbn        = (form_data.get("isbn", "") or "").strip()
        self.publisher   = (form_data.get("publisher", "") or "").strip()
        self.year        = form_data.get("year", "") or ""
        self.pages       = form_data.get("pages", "") or ""
        self.language    = (form_data.get("language", "English") or "English").strip()
        self.available   = form_data.get("available", "1") == "1"
        self.errors      = []

    def validate(self):
        if not self.title:
            self.errors.append("Book title is required.")
        if not self.author:
            self.errors.append("Author name is required.")
        if not self.category:
            self.errors.append("Category is required.")
        return not bool(self.errors)

    @property
    def year_int(self):
        try:
            return int(self.year)
        except (ValueError, TypeError):
            return None

    @property
    def pages_int(self):
        try:
            return int(self.pages)
        except (ValueError, TypeError):
            return None

    @property
    def available_int(self):
        return 1 if self.available else 0


class ForgotPasswordForm:
    """Validate a forgot-password request."""

    def __init__(self, form_data):
        self.email  = (form_data.get("email", "") or "").strip().lower()
        self.errors = []

    def validate(self):
        if not self.email or not EMAIL_RE.match(self.email):
            self.errors.append("Enter a valid email address.")
        return not bool(self.errors)


class ResetPasswordForm:
    """Validate a password-reset form submission."""

    def __init__(self, form_data):
        self.password         = form_data.get("password", "") or ""
        self.confirm_password = form_data.get("confirm_password", "") or ""
        self.errors           = []

    def validate(self):
        if len(self.password) < 8:
            self.errors.append("New password must be at least 8 characters.")
        if self.password != self.confirm_password:
            self.errors.append("Passwords do not match.")
        return not bool(self.errors)
