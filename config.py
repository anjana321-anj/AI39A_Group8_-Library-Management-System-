import os

import pymysql


SECRET_KEY = os.getenv("SECRET_KEY", "random-secret-key")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "AnimShr@11softw@ricA")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "class_db")
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


def get_database_connection():
    """Create a MySQL connection using the BookVerse configuration."""
    return pymysql.connect(**DATABASE_CONFIG)
