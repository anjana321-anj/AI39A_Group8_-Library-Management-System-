"""
BookVerse – Database Layer
===========================
All MySQL interactions live here.  Controllers and routes never build SQL
directly – they call these helper functions instead.

Table responsibilities
-----------------------
users             : registered readers and admins
books             : library catalog
borrowed_books    : checkout / return ledger
skills            : reader skill tags shown on the profile page
password_resets   : one-time tokens for the forgot-password flow
"""

import secrets
from datetime import datetime, timedelta

import pymysql
from werkzeug.security import generate_password_hash

import config

# ---------------------------------------------------------------------------
# Low-level connection helpers
# ---------------------------------------------------------------------------

def _server_connection():
    """Connect to MySQL server *without* selecting a database (used during init)."""
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_connection():
    """Return a connection to the BookVerse database."""
    return pymysql.connect(**config.DATABASE_CONFIG)


def fetch_one(query, params=None):
    """Execute *query* and return the first row as a dict, or None."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    finally:
        connection.close()


def fetch_all(query, params=None):
    """Execute *query* and return all rows as a list of dicts."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    finally:
        connection.close()


def execute(query, params=None):
    """Execute a DML statement and return lastrowid."""
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


# ---------------------------------------------------------------------------
# Schema helpers (used only during initialize_mysql_database)
# ---------------------------------------------------------------------------

def _table_columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    return {row["Field"] for row in cursor.fetchall()}


def _table_exists(cursor, table_name):
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _ensure_users_table(cursor):
    """Create users table and migrate older schemas that may lack columns."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            username      VARCHAR(100) NOT NULL,
            email         VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20)  NOT NULL DEFAULT 'user',
            linkedin_url  VARCHAR(300) DEFAULT NULL,
            github_url    VARCHAR(300) DEFAULT NULL,
            instagram_url VARCHAR(300) DEFAULT NULL,
            contact_email VARCHAR(255) DEFAULT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    columns = _table_columns(cursor, "users")

    # Migrate older schemas that might be missing newer columns
    migrations = [
        ("username",      "VARCHAR(100) NULL AFTER id"),
        ("password_hash", "VARCHAR(255) NULL AFTER email"),
        ("role",          "VARCHAR(20) NOT NULL DEFAULT 'user'"),
        ("linkedin_url",  "VARCHAR(300) DEFAULT NULL"),
        ("github_url",    "VARCHAR(300) DEFAULT NULL"),
        ("instagram_url", "VARCHAR(300) DEFAULT NULL"),
        ("contact_email", "VARCHAR(255) DEFAULT NULL"),
        ("created_at",    "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]
    for col, definition in migrations:
        if col not in columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN `{col}` {definition}")
            columns.add(col)

    # Copy legacy 'name' -> username if needed
    if "name" in columns:
        cursor.execute(
            """
            UPDATE users
               SET username = COALESCE(NULLIF(username,''), NULLIF(name,''),
                                       SUBSTRING_INDEX(email,'@',1))
             WHERE username IS NULL OR username = ''
            """
        )
    else:
        cursor.execute(
            """
            UPDATE users
               SET username = COALESCE(NULLIF(username,''), SUBSTRING_INDEX(email,'@',1))
             WHERE username IS NULL OR username = ''
            """
        )

    # Copy legacy plain-text password -> hash
    if "password" in columns:
        cursor.execute(
            """
            UPDATE users
               SET password_hash = COALESCE(NULLIF(password_hash,''), NULLIF(password,''))
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


def _seed_books(cursor):
    """Insert starter books only when the table is empty."""
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
        (
            "Sapiens",
            "Yuval Noah Harari",
            "History",
            "A sweeping narrative about the rise of humanity from ancient foragers to modern civilisation.",
            "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?q=80&w=900&auto=format&fit=crop",
            0,
        ),
        (
            "The Psychology of Money",
            "Morgan Housel",
            "Finance",
            "Timeless lessons on wealth, greed, and happiness told through short stories.",
            "https://images.unsplash.com/photo-1554224155-6726b3ff858f?q=80&w=900&auto=format&fit=crop",
            0,
        ),
    ]
    cursor.executemany(
        """
        INSERT INTO books (title, author, category, description, image, available)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        books,
    )


# ---------------------------------------------------------------------------
# Public initialisation
# ---------------------------------------------------------------------------

def initialize_mysql_database():
    """
    Create the application database, run schema migrations, and seed initial data.

    This function is idempotent – running it multiple times will not destroy
    existing data.
    """
    connection = None
    cursor = None
    database_name = config.MYSQL_DATABASE or "class_db"

    try:
        if not config.MYSQL_HOST or not config.MYSQL_USER or config.MYSQL_PASSWORD is None:
            raise ValueError("MYSQL_HOST, MYSQL_USER, and MYSQL_PASSWORD must be set.")

        connection = _server_connection()
        cursor = connection.cursor()

        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{database_name}`")

        # --- users ---
        _ensure_users_table(cursor)

        # --- books ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                title       VARCHAR(150) NOT NULL,
                author      VARCHAR(120) NOT NULL,
                category    VARCHAR(80)  NOT NULL,
                description TEXT,
                image       VARCHAR(500),
                isbn        VARCHAR(20)  DEFAULT NULL,
                publisher   VARCHAR(120) DEFAULT NULL,
                year        SMALLINT     DEFAULT NULL,
                pages       SMALLINT     DEFAULT NULL,
                language    VARCHAR(50)  DEFAULT 'English',
                available   TINYINT(1)   NOT NULL DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # migrate older books table that may be missing newer columns
        if _table_exists(cursor, "books"):
            book_cols = _table_columns(cursor, "books")
            book_migrations = [
                ("isbn",      "VARCHAR(20) DEFAULT NULL"),
                ("publisher", "VARCHAR(120) DEFAULT NULL"),
                ("year",      "SMALLINT DEFAULT NULL"),
                ("pages",     "SMALLINT DEFAULT NULL"),
                ("language",  "VARCHAR(50) DEFAULT 'English'"),
            ]
            for col, defn in book_migrations:
                if col not in book_cols:
                    cursor.execute(f"ALTER TABLE books ADD COLUMN `{col}` {defn}")

        # --- borrowed_books ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS borrowed_books (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                user_id     INT NOT NULL,
                book_id     INT NOT NULL,
                borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                return_date TIMESTAMP NULL,
                status      VARCHAR(30) NOT NULL DEFAULT 'borrowed',
                CONSTRAINT fk_borrowed_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_borrowed_book FOREIGN KEY (book_id)
                    REFERENCES books(id) ON DELETE CASCADE
            )
            """
        )

        # --- skills ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                user_id           INT NOT NULL,
                skill_name        VARCHAR(100) NOT NULL,
                proficiency_level VARCHAR(50)  NOT NULL,
                CONSTRAINT fk_skills_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # --- password_resets ---
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                user_id    INT          NOT NULL,
                token      VARCHAR(128) NOT NULL UNIQUE,
                expires_at DATETIME     NOT NULL,
                used       TINYINT(1)   NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_reset_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        _seed_books(cursor)
        connection.commit()
        print(f"[BookVerse] MySQL database '{database_name}' is ready.")
        return True

    except (pymysql.MySQLError, ValueError) as error:
        if connection:
            connection.rollback()
        print(f"[BookVerse] MySQL initialisation error: {error}")
        return False

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def get_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(%s)", (email,))


def get_user_by_id(user_id):
    return fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))


def create_user(username, email, password_hash):
    """Insert a new user row and return the new id."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            columns = _table_columns(cursor, "users")
            insert_cols = ["username", "email", "password_hash"]
            values = [username, email, password_hash]

            # Legacy schemas may still have name / password columns
            if "name" in columns:
                insert_cols.append("name")
                values.append(username)
            if "password" in columns:
                insert_cols.append("password")
                values.append(password_hash)

            col_sql = ", ".join(f"`{c}`" for c in insert_cols)
            placeholders = ", ".join(["%s"] * len(insert_cols))
            cursor.execute(
                f"INSERT INTO users ({col_sql}) VALUES ({placeholders})",
                tuple(values),
            )
            connection.commit()
            return cursor.lastrowid
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_user_password_hash(user_id, password_hash):
    """Update a user's stored password hash (and legacy plain column if present)."""
    columns_rows = fetch_all("SHOW COLUMNS FROM users")
    cols = {r["Field"] for r in columns_rows}
    if "password" in cols:
        execute(
            "UPDATE users SET password_hash=%s, password=%s WHERE id=%s",
            (password_hash, password_hash, user_id),
        )
    else:
        execute(
            "UPDATE users SET password_hash=%s WHERE id=%s",
            (password_hash, user_id),
        )


def update_user_profile(user_id, username, email, linkedin_url, github_url, instagram_url, contact_email):
    """Update editable profile fields for a given user."""
    execute(
        """
        UPDATE users
           SET username      = %s,
               email         = %s,
               linkedin_url  = %s,
               github_url    = %s,
               instagram_url = %s,
               contact_email = %s
         WHERE id = %s
        """,
        (username, email, linkedin_url, github_url, instagram_url, contact_email, user_id),
    )


def delete_user(user_id):
    """Permanently remove a user (admin action)."""
    execute("DELETE FROM users WHERE id = %s", (user_id,))


def list_users():
    """Return all registered users ordered by creation date."""
    return fetch_all("SELECT * FROM users ORDER BY created_at DESC")


# ---------------------------------------------------------------------------
# Password-reset helpers
# ---------------------------------------------------------------------------

def create_password_reset_token(user_id):
    """Generate a secure token, persist it, and return the token string."""
    token = secrets.token_urlsafe(64)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    execute(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)",
        (user_id, token, expires_at),
    )
    return token


def get_valid_reset_token(token):
    """Return the reset row if the token exists, is unused, and has not expired."""
    return fetch_one(
        """
        SELECT * FROM password_resets
         WHERE token = %s
           AND used = 0
           AND expires_at > UTC_TIMESTAMP()
        """,
        (token,),
    )


def mark_reset_token_used(token):
    execute("UPDATE password_resets SET used=1 WHERE token=%s", (token,))


# ---------------------------------------------------------------------------
# Book helpers
# ---------------------------------------------------------------------------

def list_books():
    """Return all books, available ones first, then by title."""
    return fetch_all("SELECT * FROM books ORDER BY available DESC, title ASC")


def get_book(book_id):
    return fetch_one("SELECT * FROM books WHERE id = %s", (book_id,))


def add_book(title, author, category, description, image, isbn, publisher, year, pages, language, available):
    """Insert a new book into the catalog and return the new id."""
    return execute(
        """
        INSERT INTO books
            (title, author, category, description, image, isbn, publisher, year, pages, language, available)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (title, author, category, description, image, isbn, publisher, year, pages, language, available),
    )


def update_book(book_id, title, author, category, description, image, isbn, publisher, year, pages, language, available):
    """Update all editable fields on a catalog book."""
    execute(
        """
        UPDATE books
           SET title       = %s,
               author      = %s,
               category    = %s,
               description = %s,
               image       = %s,
               isbn        = %s,
               publisher   = %s,
               year        = %s,
               pages       = %s,
               language    = %s,
               available   = %s
         WHERE id = %s
        """,
        (title, author, category, description, image, isbn, publisher, year, pages, language, available, book_id),
    )


def delete_book(book_id):
    """Remove a book from the catalog (admin only)."""
    execute("DELETE FROM books WHERE id = %s", (book_id,))


# ---------------------------------------------------------------------------
# Borrow / return helpers
# ---------------------------------------------------------------------------

def borrow_book(user_id, book_id):
    """Mark a book as borrowed.  Returns True on success, False if unavailable."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT available FROM books WHERE id=%s FOR UPDATE", (book_id,)
            )
            book = cursor.fetchone()
            if not book or not book["available"]:
                return False
            cursor.execute(
                "INSERT INTO borrowed_books (user_id, book_id, status) VALUES (%s,%s,'borrowed')",
                (user_id, book_id),
            )
            cursor.execute("UPDATE books SET available=0 WHERE id=%s", (book_id,))
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def return_book(user_id, borrowed_id):
    """Return a borrowed book.  Returns True on success."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT book_id FROM borrowed_books
                 WHERE id=%s AND user_id=%s AND status='borrowed'
                """,
                (borrowed_id, user_id),
            )
            loan = cursor.fetchone()
            if not loan:
                return False
            cursor.execute(
                """
                UPDATE borrowed_books
                   SET status='returned', return_date=CURRENT_TIMESTAMP
                 WHERE id=%s
                """,
                (borrowed_id,),
            )
            cursor.execute(
                "UPDATE books SET available=1 WHERE id=%s", (loan["book_id"],)
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
            bb.id,
            bb.borrow_date,
            bb.return_date,
            bb.status,
            b.title,
            b.author,
            b.category,
            b.image,
            DATE_ADD(bb.borrow_date, INTERVAL 21 DAY) AS due_date
          FROM borrowed_books bb
          JOIN books b ON bb.book_id = b.id
         WHERE bb.user_id = %s
         ORDER BY bb.borrow_date DESC
        """,
        (user_id,),
    )


# ---------------------------------------------------------------------------
# Dashboard / analytics helpers
# ---------------------------------------------------------------------------

def get_dashboard_stats():
    """Return aggregate counts used on the dashboard overview."""
    return {
        "books":     fetch_one("SELECT COUNT(*) AS total FROM books")["total"],
        "members":   fetch_one("SELECT COUNT(*) AS total FROM users")["total"],
        "borrowed":  fetch_one(
            "SELECT COUNT(*) AS total FROM borrowed_books WHERE status='borrowed'"
        )["total"],
        "available": fetch_one(
            "SELECT COUNT(*) AS total FROM books WHERE available=1"
        )["total"],
        "unavailable": fetch_one(
            "SELECT COUNT(*) AS total FROM books WHERE available=0"
        )["total"],
    }


def get_recent_activity(limit=8):
    return fetch_all(
        """
        SELECT u.username, b.title, bb.status, bb.borrow_date
          FROM borrowed_books bb
          JOIN users u ON bb.user_id  = u.id
          JOIN books b ON bb.book_id  = b.id
         ORDER BY bb.borrow_date DESC
         LIMIT %s
        """,
        (limit,),
    )


# ---------------------------------------------------------------------------
# Skills helpers
# ---------------------------------------------------------------------------

def get_user_skills(user_id):
    return fetch_all(
        "SELECT * FROM skills WHERE user_id=%s ORDER BY skill_name ASC",
        (user_id,),
    )


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

def test_database_connection():
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db")
            result = cursor.fetchone()
            print(f"[BookVerse] Connected to database: {result['db']}")
            return True
    except pymysql.MySQLError as error:
        print(f"[BookVerse] Connection test failed: {error}")
        return False
    finally:
        if connection:
            connection.close()
