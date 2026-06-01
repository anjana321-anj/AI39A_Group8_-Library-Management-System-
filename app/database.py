import datetime
import secrets
import pymysql
from werkzeug.security import generate_password_hash

import config


def _server_connection():
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_connection():
    return pymysql.connect(**config.DATABASE_CONFIG)


def fetch_one(query, params=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    finally:
        connection.close()


def fetch_all(query, params=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    finally:
        connection.close()


def execute(query, params=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            connection.commit()
            return cursor.lastrowid
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def _table_columns(cursor, table_name):
    cursor.execute("SHOW COLUMNS FROM `" + table_name + "`")
    return {row["Field"] for row in cursor.fetchall()}


def _ensure_users_table(cursor):
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            email_verified TINYINT(1) NOT NULL DEFAULT 0,
            is_admin TINYINT(1) NOT NULL DEFAULT 0,
            verification_token VARCHAR(255),
            reset_token VARCHAR(255),
            reset_expires DATETIME NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )

    columns = _table_columns(cursor, "users")

    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL AFTER id")
        columns.add("username")

    if "password_hash" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL AFTER email")
        columns.add("password_hash")

    if "email_verified" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0 AFTER password_hash")
        columns.add("email_verified")

    if "is_admin" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0 AFTER email_verified")
        columns.add("is_admin")

    if "verification_token" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN verification_token VARCHAR(255) NULL AFTER is_admin")
        columns.add("verification_token")

    if "reset_token" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255) NULL AFTER verification_token")
        columns.add("reset_token")

    if "reset_expires" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_expires DATETIME NULL AFTER reset_token")
        columns.add("reset_expires")

    if "created_at" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    if "name" in columns:
        cursor.execute(
            '''
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), NULLIF(name, ''), SUBSTRING_INDEX(email, '@', 1))
            WHERE username IS NULL OR username = ''
            '''
        )
    else:
        cursor.execute(
            '''
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), SUBSTRING_INDEX(email, '@', 1))
            WHERE username IS NULL OR username = ''
            '''
        )

    if "password" in columns:
        cursor.execute(
            '''
            UPDATE users
            SET password_hash = COALESCE(NULLIF(password_hash, ''), NULLIF(password, ''))
            WHERE password_hash IS NULL OR password_hash = ''
            '''
        )

    fallback_hash = generate_password_hash("bookverse123")
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE password_hash IS NULL OR password_hash = ''",
        (fallback_hash,),
    )
    cursor.execute("ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL")
    cursor.execute("ALTER TABLE users MODIFY password_hash VARCHAR(255) NOT NULL")

    cursor.execute("SELECT COUNT(*) AS total_admins FROM users WHERE is_admin = 1")
    if cursor.fetchone()["total_admins"] == 0:
        cursor.execute("SELECT id FROM users ORDER BY id LIMIT 1")
        first_user = cursor.fetchone()
        if first_user:
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = %s", (first_user["id"],))


def _seed_books(cursor):
    cursor.execute("SELECT COUNT(*) AS total FROM books")
    if cursor.fetchone()["total"]:
        return

    books = [
        (
            "The Alchemist",
            "Paulo Coelho",
            "Fiction",
            "A reflective journey about dreams, purpose, and listening to your personal legend.",
            "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=900&auto=format&fit=crop",
            1,
        ),
        (
            "Atomic Habits",
            "James Clear",
            "Self Help",
            "A practical guide to building systems, improving routines, and creating lasting change.",
            "https://images.unsplash.com/photo-1532012197267-da84d127e765?q=80&w=900&auto=format&fit=crop",
            1,
        ),
        (
            "Educated",
            "Tara Westover",
            "Biography",
            "A memoir about self-education, resilience, and building a life through learning.",
            "https://images.unsplash.com/photo-1497633762263-d550eacf6090?q=80&w=900&auto=format&fit=crop",
            1,
        ),
        (
            "Deep Work",
            "Cal Newport",
            "Productivity",
            "A focused playbook for concentration, meaningful output, and distraction-free study.",
            "https://images.unsplash.com/photo-1516979187457-637abb4f9353?q=80&w=900&auto=format&fit=crop",
            1,
        ),
        (
            "Think Like a Monk",
            "Jay Shetty",
            "Mindset",
            "A calm, practical book about purpose, perspective, and daily clarity.",
            "https://images.unsplash.com/photo-1524578271613-d550eacf6090?q=80&w=900&auto=format&fit=crop",
            1,
        ),
        (
            "The Silent Library",
            "John Carter",
            "Mystery",
            "A quiet campus mystery built around hidden notes, old shelves, and one missing manuscript.",
            "https://images.unsplash.com/photo-1512820790803-83ca734da794?q=80&w=900&auto=format&fit=crop",
            0,
        ),
    ]
    cursor.executemany(
        '''
        INSERT INTO books (title, author, category, description, image, available)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        books,
    )


def initialize_mysql_database():
    """
    Create class_db, migrate older user schemas, and initialize BookVerse tables.
    """
    connection = None
    cursor = None
    database_name = config.MYSQL_DATABASE or "class_db"

    try:
        if not config.MYSQL_HOST or not config.MYSQL_USER or config.MYSQL_PASSWORD is None:
            raise ValueError("MYSQL_HOST, MYSQL_USER, and MYSQL_PASSWORD must be configured.")

        connection = _server_connection()
        cursor = connection.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{database_name}`")

        _ensure_users_table(cursor)
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS books (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(150) NOT NULL,
                author VARCHAR(120) NOT NULL,
                category VARCHAR(80) NOT NULL,
                description TEXT,
                image VARCHAR(500),
                available TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS borrowed_books (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                book_id INT NOT NULL,
                borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                due_date TIMESTAMP NULL,
                return_date TIMESTAMP NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'borrowed',
                CONSTRAINT fk_borrowed_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_borrowed_book
                    FOREIGN KEY (book_id) REFERENCES books(id)
                    ON DELETE CASCADE
            )
            '''
        )
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                skill_name VARCHAR(100) NOT NULL,
                proficiency_level VARCHAR(50) NOT NULL,
                CONSTRAINT fk_skills_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            '''
        )
        _seed_books(cursor)
        connection.commit()
        print(f"MySQL database '{database_name}' is ready.")
        return True
    except pymysql.MySQLError:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def create_user(username, email, password_hash, is_admin=False, verification_token=None):
    return execute(
        '''
        INSERT INTO users (username, email, password_hash, email_verified, is_admin, verification_token)
        VALUES (%s, %s, %s, 0, %s, %s)
        ''',
        (username, email, password_hash, 1 if is_admin else 0, verification_token),
    )


def get_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE email = %s", (email,))


def get_user_by_id(user_id):
    return fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))


def get_user_by_verification_token(token):
    return fetch_one("SELECT * FROM users WHERE verification_token = %s", (token,))


def get_user_by_reset_token(token):
    return fetch_one(
        "SELECT * FROM users WHERE reset_token = %s AND reset_expires > NOW()", (token,)
    )


def set_email_verification_token(user_id, token):
    return execute(
        "UPDATE users SET verification_token = %s, email_verified = 0 WHERE id = %s", (token, user_id)
    )


def create_password_reset_request(user_id, token, expires_at):
    return execute(
        "UPDATE users SET reset_token = %s, reset_expires = %s WHERE id = %s",
        (token, expires_at, user_id),
    )


def clear_password_reset_token(user_id):
    return execute(
        "UPDATE users SET reset_token = NULL, reset_expires = NULL WHERE id = %s",
        (user_id,),
    )


def mark_email_verified(user_id):
    return execute(
        "UPDATE users SET email_verified = 1, verification_token = NULL WHERE id = %s",
        (user_id,),
    )


def update_user_email_username(user_id, username, email):
    return execute(
        "UPDATE users SET username = %s, email = %s WHERE id = %s",
        (username, email, user_id),
    )


def update_user_password_hash(user_id, password_hash):
    return execute(
        "UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id)
    )


def get_all_users():
    return fetch_all(
        "SELECT id, username, email, email_verified, is_admin, created_at FROM users ORDER BY created_at DESC"
    )


def delete_user(user_id):
    return execute("DELETE FROM users WHERE id = %s", (user_id,))


def update_user_role(user_id, is_admin):
    return execute(
        "UPDATE users SET is_admin = %s WHERE id = %s", (1 if is_admin else 0, user_id)
    )


def list_books(only_available=False):
    if only_available:
        return fetch_all("SELECT * FROM books WHERE available = 1 ORDER BY created_at DESC")
    return fetch_all("SELECT * FROM books ORDER BY created_at DESC")


def get_all_books():
    return list_books()


def get_book(book_id):
    return fetch_one("SELECT * FROM books WHERE id = %s", (book_id,))


def add_book(title, author, category, description, image, available=True):
    return execute(
        '''
        INSERT INTO books (title, author, category, description, image, available)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (title, author, category, description, image, 1 if available else 0),
    )


def update_book(book_id, title, author, category, description, image, available):
    return execute(
        '''
        UPDATE books
        SET title = %s, author = %s, category = %s, description = %s, image = %s, available = %s
        WHERE id = %s
        ''',
        (title, author, category, description, image, 1 if available else 0, book_id),
    )


def delete_book(book_id):
    return execute("DELETE FROM books WHERE id = %s", (book_id,))


def borrow_book(user_id, book_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT available FROM books WHERE id = %s FOR UPDATE", (book_id,))
            book = cursor.fetchone()
            if not book or not book["available"]:
                connection.rollback()
                return False

            cursor.execute("UPDATE books SET available = 0 WHERE id = %s", (book_id,))
            cursor.execute(
                '''
                INSERT INTO borrowed_books (user_id, book_id, borrow_date, due_date, status)
                VALUES (%s, %s, NOW(), DATE_ADD(NOW(), INTERVAL 14 DAY), 'borrowed')
                ''',
                (user_id, book_id),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def return_book(user_id, borrowed_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT book_id, status FROM borrowed_books WHERE id = %s AND user_id = %s FOR UPDATE",
                (borrowed_id, user_id),
            )
            borrowed = cursor.fetchone()
            if not borrowed or borrowed["status"] != "borrowed":
                connection.rollback()
                return False

            cursor.execute(
                "UPDATE borrowed_books SET status = 'returned', return_date = NOW() WHERE id = %s",
                (borrowed_id,),
            )
            cursor.execute("UPDATE books SET available = 1 WHERE id = %s", (borrowed["book_id"],))
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_user_borrowed_books(user_id):
    return fetch_all(
        '''
        SELECT bb.id, bb.borrow_date, bb.due_date, bb.return_date, bb.status,
               b.title, b.author, b.category, b.image
        FROM borrowed_books bb
        JOIN books b ON bb.book_id = b.id
        WHERE bb.user_id = %s
        ORDER BY bb.borrow_date DESC
        ''',
        (user_id,),
    )


def get_recent_activity():
    return fetch_all(
        '''
        SELECT u.username, b.title, b.author, bb.borrow_date, bb.status
        FROM borrowed_books bb
        JOIN users u ON bb.user_id = u.id
        JOIN books b ON bb.book_id = b.id
        ORDER BY bb.borrow_date DESC
        LIMIT 8
        ''',
    )


def get_dashboard_stats():
    stats = fetch_one(
        '''
        SELECT
            COUNT(*) AS books,
            COALESCE(SUM(available), 0) AS available,
            (SELECT COUNT(*) FROM users) AS members,
            (SELECT COUNT(*) FROM borrowed_books WHERE status = 'borrowed') AS borrowed
        FROM books
        '''
    )
    return {
        "books": stats["books"] or 0,
        "available": stats["available"] or 0,
        "members": stats["members"] or 0,
        "borrowed": stats["borrowed"] or 0,
    }


def get_user_skills(user_id):
    return fetch_all(
        "SELECT skill_name, proficiency_level FROM skills WHERE user_id = %s ORDER BY id DESC",
        (user_id,),
    )
