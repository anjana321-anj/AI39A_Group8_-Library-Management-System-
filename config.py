"""
BookVerse – Application Configuration
======================================
Reads all sensitive values from environment variables so the app can be deployed
to any environment without touching source code.  Sane defaults are provided for
local development only.
"""

import os
from datetime import timedelta

import pymysql

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "bookverse-super-secret-key-2025")

# ---------------------------------------------------------------------------
# Session behaviour
# ---------------------------------------------------------------------------
PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# MySQL / MariaDB connection parameters
# ---------------------------------------------------------------------------
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Anjana@2064")
MYSQL_DB = os.getenv("MYSQL_DB", os.getenv("MYSQL_DATABASE", "class_db"))
MYSQL_DATABASE = MYSQL_DB
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

DATABASE_CONFIG = {
    "host": MYSQL_HOST,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "database": MYSQL_DATABASE,
    "port": MYSQL_PORT,
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

# ---------------------------------------------------------------------------
# E-mail (SMTP) – used for forgot-password tokens
# ---------------------------------------------------------------------------
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "bookverse.noreply@gmail.com")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "BookVerse <bookverse.noreply@gmail.com>")

# ---------------------------------------------------------------------------
# Application-level settings
# ---------------------------------------------------------------------------
BOOKS_PER_PAGE = 12
ACTIVITY_FEED_LIMIT = 8
MAX_BORROW_DAYS = 21
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "admin@bookverse.local").split(",")


def get_database_connection():
    """Return a live pymysql connection using the BookVerse DATABASE_CONFIG."""
    return pymysql.connect(**DATABASE_CONFIG)
