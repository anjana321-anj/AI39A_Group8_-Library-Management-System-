import os
from datetime import timedelta

import pymysql


SECRET_KEY = os.getenv("SECRET_KEY", "random-secret-key")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "AnimShr@11softw@ricA")
MYSQL_DB = os.getenv("MYSQL_DB", os.getenv("MYSQL_DATABASE", "class_db"))
MYSQL_DATABASE = MYSQL_DB
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "support@bookverse.com")


DATABASE_CONFIG = {
    "host": MYSQL_HOST,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "database": MYSQL_DATABASE,
    "port": MYSQL_PORT,
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def get_database_connection():
    """Create a MySQL connection using the BookVerse configuration."""
    return pymysql.connect(**DATABASE_CONFIG)
