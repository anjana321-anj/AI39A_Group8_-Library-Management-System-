<<<<<<< HEAD
=======
﻿import datetime
import secrets
>>>>>>> origin/main
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
<<<<<<< HEAD
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    return {row["Field"] for row in cursor.fetchall()}


def _table_exists(cursor, table_name):
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _ensure_users_table(cursor):
    cursor.execute(
        """
=======
    cursor.execute("SHOW COLUMNS FROM `" + table_name + "`")
    return {row["Field"] for row in cursor.fetchall()}


def _ensure_users_table(cursor):
    cursor.execute(
        '''
>>>>>>> origin/main
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
<<<<<<< HEAD
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
=======
            email_verified TINYINT(1) NOT NULL DEFAULT 0,
            is_admin TINYINT(1) NOT NULL DEFAULT 0,
            verification_token VARCHAR(255),
            reset_token VARCHAR(255),
            reset_expires DATETIME NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
>>>>>>> origin/main
    )

    columns = _table_columns(cursor, "users")

    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL AFTER id")
        columns.add("username")

    if "password_hash" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL AFTER email")
        columns.add("password_hash")

<<<<<<< HEAD
=======
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

>>>>>>> origin/main
    if "created_at" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    if "name" in columns:
        cursor.execute(
<<<<<<< HEAD
            """
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), NULLIF(name, ''), SUBSTRING_INDEX(email, '@', 1))
            WHERE username IS NULL OR username = ''
            """
        )
    else:
        cursor.execute(
            """
            UPDATE users
            SET username = COALESCE(NULLIF(username, ''), SUBSTRING_INDEX(email, '@', 1))
            WHERE username IS NULL OR username = ''
            """
=======
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
>>>>>>> origin/main
        )

    if "password" in columns:
        cursor.execute(
<<<<<<< HEAD
            """
            UPDATE users
            SET password_hash = COALESCE(NULLIF(password_hash, ''), NULLIF(password, ''))
            WHERE password_hash IS NULL OR password_hash = ''
            """
=======
            '''
            UPDATE users
            SET password_hash = COALESCE(NULLIF(password_hash, ''), NULLIF(password, ''))
            WHERE password_hash IS NULL OR password_hash = ''
            '''
>>>>>>> origin/main
        )

    fallback_hash = generate_password_hash("bookverse123")
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE password_hash IS NULL OR password_hash = ''",
        (fallback_hash,),
    )
    cursor.execute("ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL")
    cursor.execute("ALTER TABLE users MODIFY password_hash VARCHAR(255) NOT NULL")

<<<<<<< HEAD
=======
    cursor.execute("SELECT COUNT(*) AS total_admins FROM users WHERE is_admin = 1")
    if cursor.fetchone()["total_admins"] == 0:
        cursor.execute("SELECT id FROM users ORDER BY id LIMIT 1")
        first_user = cursor.fetchone()
        if first_user:
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = %s", (first_user["id"],))

>>>>>>> origin/main

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
<<<<<<< HEAD
            "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?q=80&w=900&auto=format&fit=crop",
=======
            "https://images.unsplash.com/photo-1497633762263-d550eacf6090?q=80&w=900&auto=format&fit=crop",
>>>>>>> origin/main
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
<<<<<<< HEAD
            1,
        ),
    ]
    cursor.executemany(
        """
        INSERT INTO books (title, author, category, description, image, available)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
=======
            0,
        ),
    ]
    cursor.executemany(
        '''
        INSERT INTO books (title, author, category, description, image, available)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
>>>>>>> origin/main
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
<<<<<<< HEAD
            """
=======
            '''
>>>>>>> origin/main
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
<<<<<<< HEAD
            """
        )
        cursor.execute(
            """
=======
            '''
        )
        cursor.execute(
            '''
>>>>>>> origin/main
            CREATE TABLE IF NOT EXISTS borrowed_books (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                book_id INT NOT NULL,
                borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
<<<<<<< HEAD
=======
                due_date TIMESTAMP NULL,
>>>>>>> origin/main
                return_date TIMESTAMP NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'borrowed',
                CONSTRAINT fk_borrowed_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_borrowed_book
                    FOREIGN KEY (book_id) REFERENCES books(id)
                    ON DELETE CASCADE
            )
<<<<<<< HEAD
            """
        )
        cursor.execute(
            """
=======
            '''
        )
        cursor.execute(
            '''
>>>>>>> origin/main
            CREATE TABLE IF NOT EXISTS skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                skill_name VARCHAR(100) NOT NULL,
                proficiency_level VARCHAR(50) NOT NULL,
                CONSTRAINT fk_skills_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
<<<<<<< HEAD
            """
=======
            '''
>>>>>>> origin/main
        )
        _seed_books(cursor)
        connection.commit()
        print(f"MySQL database '{database_name}' is ready.")
        return True
<<<<<<< HEAD
    except (pymysql.MySQLError, ValueError) as error:
        if connection:
            connection.rollback()
        print(f"MySQL initialization error: {error}")
        return False
=======
    except pymysql.MySQLError:
        if connection:
            connection.rollback()
        raise
>>>>>>> origin/main
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


<<<<<<< HEAD
def get_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
=======
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
>>>>>>> origin/main


def get_user_by_id(user_id):
    return fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))


<<<<<<< HEAD
def update_user_password_hash(user_id, password_hash):
    columns = fetch_all("SHOW COLUMNS FROM users")
    column_names = {row["Field"] for row in columns}

    if "password" in column_names:
        execute(
            "UPDATE users SET password_hash = %s, password = %s WHERE id = %s",
            (password_hash, password_hash, user_id),
        )
    else:
        execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))


def create_user(username, email, password_hash):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            columns = _table_columns(cursor, "users")
            insert_columns = ["username", "email", "password_hash"]
            values = [username, email, password_hash]

            if "name" in columns:
                insert_columns.append("name")
                values.append(username)
            if "password" in columns:
                insert_columns.append("password")
                values.append(password_hash)
            if "role" in columns:
                insert_columns.append("role")
                values.append("user")

            placeholders = ", ".join(["%s"] * len(insert_columns))
            column_sql = ", ".join(f"`{column}`" for column in insert_columns)
            cursor.execute(
                f"INSERT INTO users ({column_sql}) VALUES ({placeholders})",
                tuple(values),
            )
            connection.commit()
            return cursor.lastrowid
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_books():
    return fetch_all("SELECT * FROM books ORDER BY available DESC, title ASC")
=======
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
>>>>>>> origin/main


def get_book(book_id):
    return fetch_one("SELECT * FROM books WHERE id = %s", (book_id,))


<<<<<<< HEAD
=======
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


def search_books(query, category=None, available_only=False):
    """
    Advanced search for books by title, author, or description.
    Supports filtering by category and availability.
    """
    sql = "SELECT * FROM books WHERE (title LIKE %s OR author LIKE %s OR description LIKE %s)"
    params = [f"%{query}%", f"%{query}%", f"%{query}%"]
    
    if category:
        sql += " AND category = %s"
        params.append(category)
    
    if available_only:
        sql += " AND available = 1"
    
    sql += " ORDER BY title ASC"
    return fetch_all(sql, params)


def get_books_by_category(category):
    """Retrieve all books in a specific category with availability status."""
    return fetch_all(
        "SELECT * FROM books WHERE category = %s ORDER BY title ASC",
        (category,)
    )


def get_available_books_count():
    """Get total count of available books."""
    result = fetch_one("SELECT COUNT(*) as count FROM books WHERE available = 1")
    return result["count"] if result else 0


def get_popular_books(limit=10):
    """Get most borrowed books (popular books)."""
    return fetch_all(
        """
        SELECT b.*, COUNT(br.id) as borrow_count
        FROM books b
        LEFT JOIN borrowed_books br ON b.id = br.book_id
        GROUP BY b.id
        ORDER BY borrow_count DESC
        LIMIT %s
        """,
        (limit,)
    )


def add_book_rating(user_id, book_id, rating, review_text=None):
    """
    Add or update a book rating and review.
    Rating should be 1-5 stars.
    """
    if not 1 <= rating <= 5:
        return False
    
    return execute(
        """
        INSERT INTO book_ratings (user_id, book_id, rating, review, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
        rating = VALUES(rating),
        review = VALUES(review),
        created_at = NOW()
        """,
        (user_id, book_id, rating, review_text)
    )


def get_book_ratings(book_id):
    """Get all ratings and reviews for a book."""
    return fetch_all(
        """
        SELECT br.*, u.username
        FROM book_ratings br
        JOIN users u ON br.user_id = u.id
        WHERE br.book_id = %s
        ORDER BY br.created_at DESC
        """,
        (book_id,)
    )


def get_average_book_rating(book_id):
    """Get average rating for a book."""
    result = fetch_one(
        "SELECT AVG(rating) as avg_rating FROM book_ratings WHERE book_id = %s",
        (book_id,)
    )
    return result["avg_rating"] if result and result["avg_rating"] else 0


def add_to_favorites(user_id, book_id):
    """Add a book to user's favorites/wishlist."""
    return execute(
        """
        INSERT INTO user_favorites (user_id, book_id, added_at)
        VALUES (%s, %s, NOW())
        ON DUPLICATE KEY UPDATE added_at = NOW()
        """,
        (user_id, book_id)
    )


def remove_from_favorites(user_id, book_id):
    """Remove a book from user's favorites."""
    return execute(
        "DELETE FROM user_favorites WHERE user_id = %s AND book_id = %s",
        (user_id, book_id)
    )


def get_user_favorites(user_id):
    """Get all favorite books for a user."""
    return fetch_all(
        """
        SELECT b.* FROM books b
        JOIN user_favorites uf ON b.id = uf.book_id
        WHERE uf.user_id = %s
        ORDER BY uf.added_at DESC
        """,
        (user_id,)
    )


def is_favorite(user_id, book_id):
    """Check if a book is in user's favorites."""
    result = fetch_one(
        "SELECT id FROM user_favorites WHERE user_id = %s AND book_id = %s",
        (user_id, book_id)
    )
    return result is not None


def get_user_reading_history(user_id, limit=10):
    """Get user's reading history (borrowed books)."""
    return fetch_all(
        """
        SELECT b.*, br.borrow_date, br.due_date, br.return_date, br.status
        FROM borrowed_books br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s
        ORDER BY br.borrow_date DESC
        LIMIT %s
        """,
        (user_id, limit)
    )


def get_overdue_books(user_id):
    """Get books that are overdue for a user."""
    return fetch_all(
        """
        SELECT b.*, br.due_date, DATEDIFF(NOW(), br.due_date) as days_overdue
        FROM borrowed_books br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s AND br.status = 'borrowed' AND br.due_date < NOW()
        ORDER BY br.due_date ASC
        """,
        (user_id,)
    )


def get_library_statistics():
    """Get overall library statistics."""
    stats = {}
    
    total_books = fetch_one("SELECT COUNT(*) as count FROM books")
    stats["total_books"] = total_books["count"] if total_books else 0
    
    available_books = fetch_one("SELECT COUNT(*) as count FROM books WHERE available = 1")
    stats["available_books"] = available_books["count"] if available_books else 0
    
    borrowed_books = fetch_one("SELECT COUNT(*) as count FROM borrowed_books WHERE status = 'borrowed'")
    stats["borrowed_books"] = borrowed_books["count"] if borrowed_books else 0
    
    total_users = fetch_one("SELECT COUNT(*) as count FROM users")
    stats["total_users"] = total_users["count"] if total_users else 0
    
    return stats


>>>>>>> origin/main
def borrow_book(user_id, book_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT available FROM books WHERE id = %s FOR UPDATE", (book_id,))
            book = cursor.fetchone()
            if not book or not book["available"]:
<<<<<<< HEAD
                return False
            cursor.execute(
                """
                INSERT INTO borrowed_books (user_id, book_id, status)
                VALUES (%s, %s, 'borrowed')
                """,
                (user_id, book_id),
            )
            cursor.execute("UPDATE books SET available = 0 WHERE id = %s", (book_id,))
=======
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
>>>>>>> origin/main
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
<<<<<<< HEAD
                """
                SELECT book_id FROM borrowed_books
                WHERE id = %s AND user_id = %s AND status = 'borrowed'
                """,
                (borrowed_id, user_id),
            )
            loan = cursor.fetchone()
            if not loan:
                return False
            cursor.execute(
                """
                UPDATE borrowed_books
                SET status = 'returned', return_date = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (borrowed_id,),
            )
            cursor.execute("UPDATE books SET available = 1 WHERE id = %s", (loan["book_id"],))
=======
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
>>>>>>> origin/main
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_user_borrowed_books(user_id):
    return fetch_all(
<<<<<<< HEAD
        """
        SELECT
            borrowed_books.id,
            borrowed_books.borrow_date,
            borrowed_books.return_date,
            borrowed_books.status,
            books.title,
            books.author,
            books.category,
            books.image,
            DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY) AS due_date
        FROM borrowed_books
        INNER JOIN books ON borrowed_books.book_id = books.id
        WHERE borrowed_books.user_id = %s
        ORDER BY borrowed_books.borrow_date DESC
        """,
=======
        '''
        SELECT bb.id, bb.borrow_date, bb.due_date, bb.return_date, bb.status,
               b.title, b.author, b.category, b.image
        FROM borrowed_books bb
        JOIN books b ON bb.book_id = b.id
        WHERE bb.user_id = %s
        ORDER BY bb.borrow_date DESC
        ''',
>>>>>>> origin/main
        (user_id,),
    )


<<<<<<< HEAD
def get_dashboard_stats():
    return {
        "books": fetch_one("SELECT COUNT(*) AS total FROM books")["total"],
        "members": fetch_one("SELECT COUNT(*) AS total FROM users")["total"],
        "borrowed": fetch_one(
            "SELECT COUNT(*) AS total FROM borrowed_books WHERE status = 'borrowed'"
        )["total"],
        "available": fetch_one("SELECT COUNT(*) AS total FROM books WHERE available = 1")["total"],
    }


def get_recent_activity(limit=6):
    return fetch_all(
        """
        SELECT users.username, books.title, borrowed_books.status, borrowed_books.borrow_date
        FROM borrowed_books
        INNER JOIN users ON borrowed_books.user_id = users.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        ORDER BY borrowed_books.borrow_date DESC
        LIMIT %s
        """,
        (limit,),
    )
=======
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
>>>>>>> origin/main


def get_user_skills(user_id):
    return fetch_all(
<<<<<<< HEAD
        "SELECT * FROM skills WHERE user_id = %s ORDER BY skill_name ASC",
=======
        "SELECT skill_name, proficiency_level FROM skills WHERE user_id = %s ORDER BY id DESC",
>>>>>>> origin/main
        (user_id,),
    )


<<<<<<< HEAD
def test_database_connection():
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS database_name")
            result = cursor.fetchone()
            print(f"Connected to database: {result['database_name']}")
            return True
    except pymysql.MySQLError as error:
        print(f"MySQL connection test failed: {error}")
        return False
    finally:
        if connection:
            connection.close()

def update_user(user_id, username, email):
    execute(
        """
        UPDATE users
        SET username=%s,email=%s
        WHERE id=%s
        """,
        (username, email, user_id),
    )
=======
def log_user_activity(user_id, activity_type, activity_description, book_id=None):
    """
    Log user activities for tracking and analytics.
    Activity types: login, borrow, return, review, search, etc.
    """
    return execute(
        """
        INSERT INTO user_activity_log (user_id, activity_type, activity_description, book_id, timestamp)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (user_id, activity_type, activity_description, book_id)
    )


def get_user_activity_log(user_id, limit=50):
    """Get activity log for a specific user."""
    return fetch_all(
        """
        SELECT activity_type, activity_description, book_id, timestamp
        FROM user_activity_log
        WHERE user_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (user_id, limit)
    )


def get_reading_statistics(user_id):
    """Get comprehensive reading statistics for a user."""
    stats = {}
    
    # Total books borrowed
    total_borrowed = fetch_one(
        "SELECT COUNT(*) as count FROM borrowed_books WHERE user_id = %s",
        (user_id,)
    )
    stats["total_borrowed"] = total_borrowed["count"] if total_borrowed else 0
    
    # Currently borrowed
    currently_borrowed = fetch_one(
        "SELECT COUNT(*) as count FROM borrowed_books WHERE user_id = %s AND status = 'borrowed'",
        (user_id,)
    )
    stats["currently_borrowed"] = currently_borrowed["count"] if currently_borrowed else 0
    
    # Books returned
    returned = fetch_one(
        "SELECT COUNT(*) as count FROM borrowed_books WHERE user_id = %s AND status = 'returned'",
        (user_id,)
    )
    stats["books_returned"] = returned["count"] if returned else 0
    
    # Favorite books count
    favorites = fetch_one(
        "SELECT COUNT(*) as count FROM user_favorites WHERE user_id = %s",
        (user_id,)
    )
    stats["favorite_books"] = favorites["count"] if favorites else 0
    
    # Average books per month
    monthly = fetch_one(
        """
        SELECT COUNT(*) as count FROM borrowed_books
        WHERE user_id = %s AND borrow_date > DATE_SUB(NOW(), INTERVAL 1 MONTH)
        """,
        (user_id,)
    )
    stats["books_this_month"] = monthly["count"] if monthly else 0
    
    return stats


def get_recommended_books(user_id, limit=10):
    """
    Get book recommendations based on user's reading history and ratings.
    Recommends books in same categories as highly-rated books.
    """
    return fetch_all(
        """
        SELECT DISTINCT b.*, AVG(br.rating) as avg_rating
        FROM books b
        JOIN book_ratings br ON b.id = br.book_id
        WHERE b.category IN (
            SELECT DISTINCT b2.category
            FROM borrowed_books bb
            JOIN books b2 ON bb.book_id = b2.id
            WHERE bb.user_id = %s
        )
        AND b.id NOT IN (
            SELECT book_id FROM borrowed_books WHERE user_id = %s
        )
        AND b.id NOT IN (
            SELECT book_id FROM user_favorites WHERE user_id = %s
        )
        GROUP BY b.id
        ORDER BY avg_rating DESC
        LIMIT %s
        """,
        (user_id, user_id, user_id, limit)
    )


def get_trending_books(days=30, limit=10):
    """Get trending books based on recent borrow activity."""
    return fetch_all(
        """
        SELECT b.*, COUNT(br.id) as borrow_count
        FROM books b
        JOIN borrowed_books br ON b.id = br.book_id
        WHERE br.borrow_date > DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY b.id
        ORDER BY borrow_count DESC
        LIMIT %s
        """,
        (days, limit)
    )


def get_category_statistics():
    """Get statistics for each book category."""
    return fetch_all(
        """
        SELECT 
            category,
            COUNT(*) as total_books,
            SUM(available) as available_books,
            ROUND(SUM(available) / COUNT(*) * 100, 2) as availability_rate
        FROM books
        GROUP BY category
        ORDER BY total_books DESC
        """
    )


def send_notification(user_id, notification_type, title, message):
    """
    Send notification to user.
    Types: due_date_reminder, book_available, return_confirmation, etc.
    """
    return execute(
        """
        INSERT INTO notifications (user_id, notification_type, title, message, is_read, created_at)
        VALUES (%s, %s, %s, %s, 0, NOW())
        """,
        (user_id, notification_type, title, message)
    )


def get_user_notifications(user_id, unread_only=False):
    """Get notifications for a user."""
    query = "SELECT * FROM notifications WHERE user_id = %s"
    params = [user_id]
    
    if unread_only:
        query += " AND is_read = 0"
    
    query += " ORDER BY created_at DESC"
    return fetch_all(query, params)


def mark_notification_as_read(notification_id):
    """Mark a notification as read."""
    return execute(
        "UPDATE notifications SET is_read = 1 WHERE id = %s",
        (notification_id,)
    )


def get_admin_dashboard_stats():
    """Get comprehensive dashboard statistics for admin."""
    stats = {}
    
    # User statistics
    total_users = fetch_one("SELECT COUNT(*) as count FROM users")
    stats["total_users"] = total_users["count"] if total_users else 0
    
    verified_users = fetch_one("SELECT COUNT(*) as count FROM users WHERE email_verified = 1")
    stats["verified_users"] = verified_users["count"] if verified_users else 0
    
    admin_users = fetch_one("SELECT COUNT(*) as count FROM users WHERE is_admin = 1")
    stats["admin_users"] = admin_users["count"] if admin_users else 0
    
    # Book statistics
    total_books = fetch_one("SELECT COUNT(*) as count FROM books")
    stats["total_books"] = total_books["count"] if total_books else 0
    
    available_books = fetch_one("SELECT COUNT(*) as count FROM books WHERE available = 1")
    stats["available_books"] = available_books["count"] if available_books else 0
    
    # Borrowing statistics
    active_borrows = fetch_one("SELECT COUNT(*) as count FROM borrowed_books WHERE status = 'borrowed'")
    stats["active_borrows"] = active_borrows["count"] if active_borrows else 0
    
    overdue_count = fetch_one(
        "SELECT COUNT(*) as count FROM borrowed_books WHERE status = 'borrowed' AND due_date < NOW()"
    )
    stats["overdue_count"] = overdue_count["count"] if overdue_count else 0
    
    # Engagement statistics
    total_ratings = fetch_one("SELECT COUNT(*) as count FROM book_ratings")
    stats["total_ratings"] = total_ratings["count"] if total_ratings else 0
    
    total_favorites = fetch_one("SELECT COUNT(*) as count FROM user_favorites")
    stats["total_favorites"] = total_favorites["count"] if total_favorites else 0
    
    return stats


def get_recently_added_books(limit=20):
    """Get recently added books."""
    return fetch_all(
        "SELECT * FROM books ORDER BY id DESC LIMIT %s",
        (limit,)
    )


def search_advanced(search_params):
    """
    Advanced search with multiple filter options.
    Supports: title, author, category, rating_min, available_only
    """
    query = "SELECT b.* FROM books b LEFT JOIN book_ratings br ON b.id = br.book_id WHERE 1=1"
    params = []
    
    if search_params.get("title"):
        query += " AND b.title LIKE %s"
        params.append(f"%{search_params['title']}%")
    
    if search_params.get("author"):
        query += " AND b.author LIKE %s"
        params.append(f"%{search_params['author']}%")
    
    if search_params.get("category"):
        query += " AND b.category = %s"
        params.append(search_params["category"])
    
    if search_params.get("rating_min"):
        query += " AND br.rating >= %s"
        params.append(search_params["rating_min"])
    
    if search_params.get("available_only"):
        query += " AND b.available = 1"
    
    query += " GROUP BY b.id ORDER BY b.title ASC"
    return fetch_all(query, params)


def update_user_last_login(user_id):
    """Update user's last login timestamp."""
    return execute(
        "UPDATE users SET last_login = NOW() WHERE id = %s",
        (user_id,)
    )


def get_user_statistics_summary(user_id):
    """Get a comprehensive summary of user statistics."""
    user = get_user_by_id(user_id)
    if not user:
        return None
    
    stats = {
        "username": user["username"],
        "email": user["email"],
        "email_verified": user["email_verified"],
        "is_admin": user["is_admin"],
        "created_at": str(user["created_at"]) if user["created_at"] else None,
    }
    
    # Add reading statistics
    reading_stats = get_reading_statistics(user_id)
    stats.update(reading_stats)
    
    return stats
>>>>>>> origin/main
