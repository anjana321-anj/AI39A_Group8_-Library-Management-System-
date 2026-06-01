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
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    return {row["Field"] for row in cursor.fetchall()}


def _table_exists(cursor, table_name):
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _ensure_users_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    columns = _table_columns(cursor, "users")

    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL AFTER id")
        columns.add("username")

    if "password_hash" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL AFTER email")
        columns.add("password_hash")

    if "created_at" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        columns.add("created_at")

    if "role" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
        columns.add("role")

    if "status" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
        columns.add("status")

    if "name" in columns:
        cursor.execute(
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
        )

    if "password" in columns:
        cursor.execute(
            """
            UPDATE users
            SET password_hash = COALESCE(NULLIF(password_hash, ''), NULLIF(password, ''))
            WHERE password_hash IS NULL OR password_hash = ''
            """
        )

    fallback_hash = generate_password_hash("bookverse123")
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE password_hash IS NULL OR password_hash = ''",
        (fallback_hash,),
    )
    cursor.execute("ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL")
    cursor.execute("ALTER TABLE users MODIFY password_hash VARCHAR(255) NOT NULL")

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
    if cursor.fetchone()["total"] == 0:
        admin_hash = generate_password_hash("Admin@12345")
        insert_columns = ["username", "email", "password_hash", "role", "status"]
        values = ["Admin", "admin@admin.com", admin_hash, "admin", "active"]
        if "name" in columns:
            insert_columns.append("name")
            values.append("Admin")
        if "password" in columns:
            insert_columns.append("password")
            values.append(admin_hash)
        placeholders = ", ".join(["%s"] * len(insert_columns))
        column_sql = ", ".join(f"`{column}`" for column in insert_columns)
        cursor.execute(f"INSERT INTO users ({column_sql}) VALUES ({placeholders})", values)


def _ensure_books_table(cursor):
    cursor.execute(
        """
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
        """
    )

    columns = _table_columns(cursor, "books")
    additions = {
        "isbn": "ALTER TABLE books ADD COLUMN isbn VARCHAR(40) NULL AFTER category",
        "publication_year": "ALTER TABLE books ADD COLUMN publication_year INT NULL AFTER isbn",
        "publisher": "ALTER TABLE books ADD COLUMN publisher VARCHAR(150) NULL AFTER publication_year",
        "language": "ALTER TABLE books ADD COLUMN language VARCHAR(80) NOT NULL DEFAULT 'English' AFTER publisher",
        "total_copies": "ALTER TABLE books ADD COLUMN total_copies INT NOT NULL DEFAULT 1 AFTER image",
        "available_copies": "ALTER TABLE books ADD COLUMN available_copies INT NOT NULL DEFAULT 1 AFTER total_copies",
        "availability_status": (
            "ALTER TABLE books ADD COLUMN availability_status VARCHAR(20) "
            "NOT NULL DEFAULT 'Available' AFTER available_copies"
        ),
    }
    for column, sql in additions.items():
        if column not in columns:
            cursor.execute(sql)
            columns.add(column)

    cursor.execute("UPDATE books SET total_copies = 1 WHERE total_copies IS NULL OR total_copies < 1")
    cursor.execute(
        """
        UPDATE books
        SET available_copies = CASE
            WHEN available = 1 AND (available_copies IS NULL OR available_copies < 1) THEN total_copies
            WHEN available = 0 THEN 0
            ELSE available_copies
        END
        """
    )
    cursor.execute(
        """
        UPDATE books
        SET availability_status = CASE
            WHEN available = 1 AND available_copies > 0 THEN 'Available'
            ELSE 'Unavailable'
        END
        """
    )


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
            "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?q=80&w=900&auto=format&fit=crop",
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
            1,
        ),
    ]
    cursor.executemany(
        """
        INSERT INTO books (
            title, author, category, description, image, available,
            total_copies, available_copies, availability_status, language
        )
        VALUES (%s, %s, %s, %s, %s, %s, 3, 3, 'Available', 'English')
        """,
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
        _ensure_books_table(cursor)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS borrowed_books (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                book_id INT NOT NULL,
                borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                return_date TIMESTAMP NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'borrowed',
                CONSTRAINT fk_borrowed_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_borrowed_book
                    FOREIGN KEY (book_id) REFERENCES books(id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                skill_name VARCHAR(100) NOT NULL,
                proficiency_level VARCHAR(50) NOT NULL,
                CONSTRAINT fk_skills_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_hash VARCHAR(128) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_password_reset_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )
        _seed_books(cursor)
        connection.commit()
        print(f"MySQL database '{database_name}' is ready.")
        return True
    except (pymysql.MySQLError, ValueError) as error:
        if connection:
            connection.rollback()
        print(f"MySQL initialization error: {error}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(%s)", (email,))


def get_user_by_id(user_id):
    return fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))


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
            if "status" in columns:
                insert_columns.append("status")
                values.append("active")

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


def get_book(book_id):
    return fetch_one("SELECT * FROM books WHERE id = %s", (book_id,))


def create_book(data):
    return execute(
        """
        INSERT INTO books (
            title, author, category, isbn, publication_year, publisher, language,
            description, image, total_copies, available_copies, availability_status, available
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data["title"],
            data["author"],
            data["category"],
            data.get("isbn"),
            data.get("publication_year"),
            data.get("publisher"),
            data.get("language"),
            data.get("description"),
            data.get("image"),
            data["total_copies"],
            data["available_copies"],
            data["availability_status"],
            1 if data["availability_status"] == "Available" and data["available_copies"] > 0 else 0,
        ),
    )


def update_book(book_id, data):
    execute(
        """
        UPDATE books
        SET title = %s,
            author = %s,
            category = %s,
            isbn = %s,
            publication_year = %s,
            publisher = %s,
            language = %s,
            description = %s,
            image = %s,
            total_copies = %s,
            available_copies = %s,
            availability_status = %s,
            available = %s
        WHERE id = %s
        """,
        (
            data["title"],
            data["author"],
            data["category"],
            data.get("isbn"),
            data.get("publication_year"),
            data.get("publisher"),
            data.get("language"),
            data.get("description"),
            data.get("image"),
            data["total_copies"],
            data["available_copies"],
            data["availability_status"],
            1 if data["availability_status"] == "Available" and data["available_copies"] > 0 else 0,
            book_id,
        ),
    )


def delete_book(book_id):
    execute("DELETE FROM books WHERE id = %s", (book_id,))


def borrow_book(user_id, book_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT available, available_copies, availability_status
                FROM books
                WHERE id = %s
                FOR UPDATE
                """,
                (book_id,),
            )
            book = cursor.fetchone()
            if (
                not book
                or not book["available"]
                or book["availability_status"] != "Available"
                or book["available_copies"] < 1
            ):
                return False
            new_available_copies = max(book["available_copies"] - 1, 0)
            new_available = 1 if new_available_copies > 0 else 0
            new_status = "Available" if new_available else "Unavailable"
            cursor.execute(
                """
                INSERT INTO borrowed_books (user_id, book_id, status)
                VALUES (%s, %s, 'borrowed')
                """,
                (user_id, book_id),
            )
            cursor.execute(
                """
                UPDATE books
                SET available_copies = %s,
                    available = %s,
                    availability_status = %s
                WHERE id = %s
                """,
                (new_available_copies, new_available, new_status, book_id),
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
            cursor.execute(
                """
                UPDATE books
                SET available_copies = LEAST(available_copies + 1, total_copies),
                    available = 1,
                    availability_status = 'Available'
                WHERE id = %s
                """,
                (loan["book_id"],),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_user_borrowed_books(user_id):
    return fetch_all(
        """
        SELECT
            borrowed_books.id,
            borrowed_books.borrow_date,
            borrowed_books.return_date,
            borrowed_books.status,
            books.title,
            books.author,
            books.category,
            books.isbn,
            books.publisher,
            books.publication_year,
            books.language,
            books.total_copies,
            books.available_copies,
            books.availability_status,
            books.image,
            DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY) AS due_date
        FROM borrowed_books
        INNER JOIN books ON borrowed_books.book_id = books.id
        WHERE borrowed_books.user_id = %s
        ORDER BY borrowed_books.borrow_date DESC
        """,
        (user_id,),
    )


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


def get_user_skills(user_id):
    return fetch_all(
        "SELECT * FROM skills WHERE user_id = %s ORDER BY skill_name ASC",
        (user_id,),
    )


def list_users():
    return fetch_all(
        "SELECT id, username, email, role, status, created_at FROM users ORDER BY id ASC"
    )


def update_user(user_id, username, email, role, status):
    execute(
        """
        UPDATE users
        SET username = %s, email = %s, role = %s, status = %s
        WHERE id = %s
        """,
        (username, email, role, status, user_id),
    )


def delete_user(user_id):
    execute("DELETE FROM users WHERE id = %s", (user_id,))


def create_password_reset_token(user_id, token_hash, expires_at):
    return execute(
        """
        INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (user_id, token_hash, expires_at),
    )


def get_valid_password_reset_token(token_hash):
    return fetch_one(
        """
        SELECT password_reset_tokens.*, users.email, users.username
        FROM password_reset_tokens
        INNER JOIN users ON password_reset_tokens.user_id = users.id
        WHERE password_reset_tokens.token_hash = %s
          AND password_reset_tokens.used_at IS NULL
          AND password_reset_tokens.expires_at > NOW()
        """,
        (token_hash,),
    )


def mark_password_reset_token_used(token_id):
    execute("UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s", (token_id,))


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
