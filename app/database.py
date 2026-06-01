import pymysql
<<<<<<< HEAD
=======
from werkzeug.security import generate_password_hash
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94

import config


<<<<<<< HEAD
def initialize_mysql_database():
    """
    Initialize the configured MySQL database and required tables for the project.
=======
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
        INSERT INTO books (title, author, category, description, image, available)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        books,
    )


def initialize_mysql_database():
    """
    Create class_db, migrate older user schemas, and initialize BookVerse tables.
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
    """
    connection = None
    cursor = None
    database_name = config.MYSQL_DATABASE or "class_db"

<<<<<<< HEAD
    users_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """

    skills_table_query = """
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

    try:
        if not config.MYSQL_HOST or not config.MYSQL_USER or config.MYSQL_PASSWORD is None:
            raise ValueError(
                "Missing required MySQL configuration values: "
                "MYSQL_HOST, MYSQL_USER, and MYSQL_PASSWORD must be set."
            )

        # Connect to the MySQL server without selecting a database first.
        connection = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            autocommit=False,
        )
        cursor = connection.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")

        cursor.execute(f"USE `{database_name}`")

        cursor.execute(users_table_query)
        cursor.execute(skills_table_query)

        connection.commit()
        print(f"MySQL database '{database_name}' is ready.")
        return True

    except pymysql.MySQLError as error:
        if connection:
            try:
                connection.rollback()
            except pymysql.MySQLError:
                pass
        print(f"MySQL initialization error: {error}")
        return False

    except Exception as error:
        if connection:
            try:
                connection.rollback()
            except pymysql.MySQLError:
                pass
        print(f"Unexpected initialization error: {error}")
        return False

    finally:
        if cursor:
            try:
                cursor.close()
            except pymysql.MySQLError:
                pass
        if connection:
            try:
                connection.close()
            except pymysql.MySQLError:
                pass


def test_database_connection():
    """Open a real connection to the configured project database."""
    connection = None
    cursor = None

    try:
        connection = pymysql.connect(**config.DATABASE_CONFIG)
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE() AS database_name")
        result = cursor.fetchone()
        print(f"Connected to database: {result['database_name']}")
        return True
=======
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


def borrow_book(user_id, book_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT available FROM books WHERE id = %s FOR UPDATE", (book_id,))
            book = cursor.fetchone()
            if not book or not book["available"]:
                return False
            cursor.execute(
                """
                INSERT INTO borrowed_books (user_id, book_id, status)
                VALUES (%s, %s, 'borrowed')
                """,
                (user_id, book_id),
            )
            cursor.execute("UPDATE books SET available = 0 WHERE id = %s", (book_id,))
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
            cursor.execute("UPDATE books SET available = 1 WHERE id = %s", (loan["book_id"],))
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


def test_database_connection():
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS database_name")
            result = cursor.fetchone()
            print(f"Connected to database: {result['database_name']}")
            return True
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
    except pymysql.MySQLError as error:
        print(f"MySQL connection test failed: {error}")
        return False
    finally:
<<<<<<< HEAD
        if cursor:
            try:
                cursor.close()
            except pymysql.MySQLError:
                pass
        if connection:
            try:
                connection.close()
            except pymysql.MySQLError:
                pass
=======
        if connection:
            connection.close()
>>>>>>> 62c4c41348aeef323b4e994be30d06c5cd94bd94
