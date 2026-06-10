from datetime import datetime, timedelta

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


def log_event(actor_user_id, event_type, entity_type, entity_id, summary):
    try:
        for table_name in ("activity_events", "activity_logs"):
            execute(
                f"""
                INSERT INTO {table_name} (actor_user_id, event_type, entity_type, entity_id, summary)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (actor_user_id, event_type, entity_type, entity_id, summary[:255]),
            )
    except pymysql.MySQLError:
        # Activity hooks are future-facing and should never block primary workflows.
        pass


def _table_columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    return {row["Field"] for row in cursor.fetchall()}


def _table_exists(cursor, table_name):
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _ensure_column(cursor, table_name, column_name, alter_sql):
    columns = _table_columns(cursor, table_name)
    if column_name not in columns:
        cursor.execute(alter_sql)
        return True
    return False


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

    if "phone" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(30) NULL AFTER email")
        columns.add("phone")

    if "phone_number" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone_number VARCHAR(30) NULL AFTER phone")
        columns.add("phone_number")

    if "address" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN address VARCHAR(255) NULL AFTER phone_number")
        columns.add("address")

    cursor.execute(
        """
        UPDATE users
        SET phone_number = COALESCE(NULLIF(phone_number, ''), NULLIF(phone, ''))
        WHERE phone_number IS NULL OR phone_number = ''
        """
    )

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
        "price": "ALTER TABLE books ADD COLUMN price DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER availability_status",
        "stock_quantity": "ALTER TABLE books ADD COLUMN stock_quantity INT NOT NULL DEFAULT 0 AFTER price",
        "book_status": "ALTER TABLE books ADD COLUMN book_status VARCHAR(30) NOT NULL DEFAULT 'Available' AFTER stock_quantity",
    }
    for column, sql in additions.items():
        if column not in columns:
            cursor.execute(sql)
            columns.add(column)
            if column == "stock_quantity":
                cursor.execute("UPDATE books SET stock_quantity = total_copies WHERE stock_quantity = 0")

    cursor.execute("UPDATE books SET stock_quantity = 0 WHERE stock_quantity IS NULL OR stock_quantity < 0")
    cursor.execute("UPDATE books SET total_copies = GREATEST(COALESCE(total_copies, 0), stock_quantity, 1)")
    cursor.execute(
        """
        UPDATE books
        SET available_copies = stock_quantity,
            available = CASE WHEN stock_quantity > 0 THEN 1 ELSE 0 END,
            availability_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Out of Stock' END
        """
    )
    cursor.execute(
        """
        UPDATE books
        SET book_status = CASE
            WHEN stock_quantity > 0 AND (book_status IS NULL OR book_status = '' OR book_status = 'Out of Stock') THEN 'Available'
            WHEN stock_quantity = 0 AND (book_status IS NULL OR book_status = '' OR book_status = 'Available') THEN 'Purchased'
            ELSE book_status
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
            total_copies, available_copies, availability_status, language, price, stock_quantity
        )
        VALUES (%s, %s, %s, %s, %s, %s, 3, 3, 'Available', 'English', 499.00, 5)
        """,
        books,
    )


def _refresh_sample_books(cursor):
    samples = [
        {
            "title": "The Alchemist",
            "author": "Paulo Coelho",
            "category": "Fiction",
            "isbn": "9780061122415",
            "publication_year": 1988,
            "publisher": "HarperOne",
            "description": "A timeless novel about dreams, destiny, and following a personal legend.",
            "image": "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=900&auto=format&fit=crop",
            "price": 650,
            "stock_quantity": 8,
        },
        {
            "title": "Atomic Habits",
            "author": "James Clear",
            "category": "Self Help",
            "isbn": "9780735211292",
            "publication_year": 2018,
            "publisher": "Avery",
            "description": "A practical guide to building better habits through small, consistent improvements.",
            "image": "https://images.unsplash.com/photo-1532012197267-da84d127e765?q=80&w=900&auto=format&fit=crop",
            "price": 1200,
            "stock_quantity": 10,
        },
        {
            "title": "Educated",
            "author": "Tara Westover",
            "category": "Biography",
            "isbn": "9780399590504",
            "publication_year": 2018,
            "publisher": "Random House",
            "description": "A powerful memoir about education, resilience, family, and self-discovery.",
            "image": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?q=80&w=900&auto=format&fit=crop",
            "price": 980,
            "stock_quantity": 6,
        },
        {
            "title": "Deep Work",
            "author": "Cal Newport",
            "category": "Productivity",
            "isbn": "9781455586691",
            "publication_year": 2016,
            "publisher": "Grand Central Publishing",
            "description": "A focused framework for concentration, distraction control, and meaningful work.",
            "image": "https://images.unsplash.com/photo-1516979187457-637abb4f9353?q=80&w=900&auto=format&fit=crop",
            "price": 1050,
            "stock_quantity": 7,
        },
        {
            "title": "The Psychology of Money",
            "author": "Morgan Housel",
            "category": "Finance",
            "isbn": "9780857197689",
            "publication_year": 2020,
            "publisher": "Harriman House",
            "description": "Short lessons on wealth, behavior, risk, patience, and financial decision-making.",
            "image": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?q=80&w=900&auto=format&fit=crop",
            "price": 1450,
            "stock_quantity": 5,
        },
        {
            "title": "The Midnight Library",
            "author": "Matt Haig",
            "category": "Fiction",
            "isbn": "9780525559474",
            "publication_year": 2020,
            "publisher": "Viking",
            "description": "A thoughtful story about regret, possibility, and the lives we imagine for ourselves.",
            "image": "https://images.unsplash.com/photo-1512820790803-83ca734da794?q=80&w=900&auto=format&fit=crop",
            "price": 850,
            "stock_quantity": 9,
        },
    ]

    cursor.execute(
        """
        UPDATE books
        SET title = 'The Midnight Library',
            author = 'Matt Haig',
            category = 'Fiction',
            isbn = '9780525559474',
            publication_year = 2020,
            publisher = 'Viking',
            description = 'A thoughtful story about regret, possibility, and the lives we imagine for ourselves.',
            price = 850.00,
            stock_quantity = CASE WHEN stock_quantity <= 0 THEN 9 ELSE stock_quantity END
            , book_status = 'Available'
        WHERE title = 'The Silent Library'
        """
    )

    for sample in samples:
        cursor.execute("SELECT id FROM books WHERE isbn = %s OR title = %s LIMIT 1", (sample["isbn"], sample["title"]))
        existing = cursor.fetchone()
        params = (
            sample["title"],
            sample["author"],
            sample["category"],
            sample["isbn"],
            sample["publication_year"],
            sample["publisher"],
            "English",
            sample["description"],
            sample["image"],
            max(sample["stock_quantity"], 1),
            sample["stock_quantity"],
            "Available" if sample["stock_quantity"] > 0 else "Out of Stock",
            1 if sample["stock_quantity"] > 0 else 0,
            sample["price"],
            sample["stock_quantity"],
            "Available",
        )
        if existing:
            cursor.execute(
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
                    total_copies = GREATEST(total_copies, %s),
                    available_copies = %s,
                    availability_status = %s,
                    available = %s,
                    price = %s,
                    stock_quantity = %s,
                    book_status = %s
                WHERE id = %s
                """,
                (*params, existing["id"]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO books (
                    title, author, category, isbn, publication_year, publisher, language,
                    description, image, total_copies, available_copies, availability_status,
                    available, price, stock_quantity
                    , book_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                params,
            )


def _ensure_feature_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS favourites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_favourite_user_book (user_id, book_id),
            CONSTRAINT fk_favourites_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_favourites_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            reservation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date DATETIME NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'Pending',
            admin_note VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_reservations_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_reservations_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            quantity INT NOT NULL DEFAULT 1,
            unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            status VARCHAR(30) NOT NULL DEFAULT 'Pending',
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_orders_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_orders_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    _ensure_column(
        cursor,
        "orders",
        "payment_method",
        "ALTER TABLE orders ADD COLUMN payment_method VARCHAR(40) NULL AFTER status",
    )
    _ensure_column(
        cursor,
        "orders",
        "payment_reference",
        "ALTER TABLE orders ADD COLUMN payment_reference VARCHAR(120) NULL AFTER payment_method",
    )
    _ensure_column(
        cursor,
        "orders",
        "payment_note",
        "ALTER TABLE orders ADD COLUMN payment_note VARCHAR(255) NULL AFTER payment_reference",
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            review_text TEXT NOT NULL,
            review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL,
            UNIQUE KEY uq_review_user_book (user_id, book_id),
            CONSTRAINT fk_reviews_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_reviews_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            actor_user_id INT NULL,
            event_type VARCHAR(80) NOT NULL,
            entity_type VARCHAR(80) NOT NULL,
            entity_id INT NULL,
            summary VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_activity_actor
                FOREIGN KEY (actor_user_id) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            actor_user_id INT NULL,
            event_type VARCHAR(80) NOT NULL,
            entity_type VARCHAR(80) NOT NULL,
            entity_id INT NULL,
            summary VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_activity_logs_actor
                FOREIGN KEY (actor_user_id) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS phone_numbers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            phone_number VARCHAR(30) NOT NULL,
            is_primary TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_phone_user_number (user_id, phone_number),
            CONSTRAINT fk_phone_numbers_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_updates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            field_name VARCHAR(80) NOT NULL,
            old_value VARCHAR(255) NULL,
            new_value VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_profile_updates_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS book_purchases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL UNIQUE,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            quantity INT NOT NULL DEFAULT 1,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            payment_method VARCHAR(40) NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_book_purchases_order
                FOREIGN KEY (order_id) REFERENCES orders(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_book_purchases_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_book_purchases_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_receipts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL UNIQUE,
            receipt_number VARCHAR(60) NOT NULL UNIQUE,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            payment_method VARCHAR(40) NULL,
            payment_status VARCHAR(30) NOT NULL,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_purchase_receipts_order
                FOREIGN KEY (order_id) REFERENCES orders(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS book_reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            rating INT NULL,
            review_text TEXT NULL,
            review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL,
            UNIQUE KEY uq_book_reviews_user_book (user_id, book_id),
            CONSTRAINT fk_book_reviews_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_book_reviews_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ratings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            rating INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL,
            UNIQUE KEY uq_rating_user_book (user_id, book_id),
            CONSTRAINT fk_ratings_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_ratings_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE,
            CONSTRAINT chk_rating_range CHECK (rating BETWEEN 1 AND 5)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(150) NOT NULL,
            message TEXT NOT NULL,
            notification_type VARCHAR(40) NOT NULL,
            related_id INT NULL,
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_notifications_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS return_reminders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            borrowed_id INT NOT NULL,
            user_id INT NOT NULL,
            reminder_type VARCHAR(40) NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_return_reminder (borrowed_id, reminder_type),
            CONSTRAINT fk_return_reminders_borrowed
                FOREIGN KEY (borrowed_id) REFERENCES borrowed_books(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_return_reminders_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fine_settings (
            id INT PRIMARY KEY,
            fine_per_day DECIMAL(10,2) NOT NULL DEFAULT 10.00,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        INSERT IGNORE INTO fine_settings (id, fine_per_day)
        VALUES (1, 10.00)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fine_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            borrowed_id INT NOT NULL UNIQUE,
            user_id INT NOT NULL,
            overdue_days INT NOT NULL DEFAULT 0,
            fine_per_day DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            total_fine DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            status VARCHAR(40) NOT NULL DEFAULT 'Pending',
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_fine_records_borrowed
                FOREIGN KEY (borrowed_id) REFERENCES borrowed_books(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_fine_records_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fine_payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fine_record_id INT NOT NULL,
            user_id INT NOT NULL,
            payment_method VARCHAR(40) NOT NULL,
            transaction_id VARCHAR(120) NOT NULL,
            payment_date DATETIME NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            proof_of_payment VARCHAR(500) NULL,
            status VARCHAR(40) NOT NULL DEFAULT 'Pending Verification',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified_at DATETIME NULL,
            CONSTRAINT fk_fine_payments_fine
                FOREIGN KEY (fine_record_id) REFERENCES fine_records(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_fine_payments_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_receipts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            payment_id INT NOT NULL UNIQUE,
            receipt_number VARCHAR(60) NOT NULL UNIQUE,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            payment_method VARCHAR(40) NOT NULL,
            payment_status VARCHAR(40) NOT NULL,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_payment_receipts_payment
                FOREIGN KEY (payment_id) REFERENCES fine_payments(id)
                ON DELETE CASCADE
        )
        """
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
        _ensure_feature_tables(cursor)
        _seed_books(cursor)
        _refresh_sample_books(cursor)
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


def create_user(username, email, password_hash, phone_number=None, address=None):
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
            if "phone" in columns:
                insert_columns.append("phone")
                values.append(phone_number)
            if "phone_number" in columns:
                insert_columns.append("phone_number")
                values.append(phone_number)
            if "address" in columns:
                insert_columns.append("address")
                values.append(address)

            placeholders = ", ".join(["%s"] * len(insert_columns))
            column_sql = ", ".join(f"`{column}`" for column in insert_columns)
            cursor.execute(
                f"INSERT INTO users ({column_sql}) VALUES ({placeholders})",
                tuple(values),
            )
            user_id = cursor.lastrowid
            if phone_number:
                cursor.execute(
                    """
                    INSERT IGNORE INTO phone_numbers (user_id, phone_number, is_primary)
                    VALUES (%s, %s, 1)
                    """,
                    (user_id, phone_number),
                )
            connection.commit()
            return user_id
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


BOOK_SELECT_WITH_METRICS = """
    SELECT
        books.*,
        COALESCE(book_rating.average_rating, 0) AS average_rating,
        COALESCE(book_rating.total_ratings, 0) AS total_ratings,
        COALESCE(book_reviews.review_count, 0) AS review_count,
        reserved_user.username AS reserved_by,
        borrowed_user.username AS borrowed_by
    FROM books
    LEFT JOIN (
        SELECT book_id, ROUND(AVG(rating), 1) AS average_rating, COUNT(*) AS total_ratings
        FROM ratings
        GROUP BY book_id
    ) AS book_rating ON book_rating.book_id = books.id
    LEFT JOIN (
        SELECT book_id, COUNT(*) AS review_count
        FROM reviews
        GROUP BY book_id
    ) AS book_reviews ON book_reviews.book_id = books.id
    LEFT JOIN (
        SELECT reservations.book_id, MAX(reservations.id) AS latest_reservation_id
        FROM reservations
        WHERE reservations.status IN ('Pending', 'Approved')
        GROUP BY reservations.book_id
    ) AS latest_reservation ON latest_reservation.book_id = books.id
    LEFT JOIN reservations AS reserved_record ON reserved_record.id = latest_reservation.latest_reservation_id
    LEFT JOIN users AS reserved_user ON reserved_user.id = reserved_record.user_id
    LEFT JOIN (
        SELECT borrowed_books.book_id, MAX(borrowed_books.id) AS latest_borrow_id
        FROM borrowed_books
        WHERE borrowed_books.status = 'borrowed'
        GROUP BY borrowed_books.book_id
    ) AS latest_borrow ON latest_borrow.book_id = books.id
    LEFT JOIN borrowed_books AS borrowed_record ON borrowed_record.id = latest_borrow.latest_borrow_id
    LEFT JOIN users AS borrowed_user ON borrowed_user.id = borrowed_record.user_id
"""


def list_books():
    return fetch_all(
        BOOK_SELECT_WITH_METRICS
        + """
        ORDER BY books.available DESC, books.title ASC
        """
    )


def get_book(book_id):
    return fetch_one(
        BOOK_SELECT_WITH_METRICS
        + """
        WHERE books.id = %s
        """,
        (book_id,),
    )


def _normalized_book_inventory(data):
    stock_quantity = max(int(data.get("stock_quantity") or data.get("available_copies") or 0), 0)
    total_copies = max(int(data.get("total_copies") or stock_quantity or 1), stock_quantity, 1)
    allowed_statuses = {"Available", "Borrowed", "Reserved", "Purchased", "In Buy List"}
    requested_status = data.get("book_status")
    book_status = requested_status if requested_status in allowed_statuses else ("Available" if stock_quantity > 0 else "Purchased")
    return {
        "total_copies": total_copies,
        "available_copies": stock_quantity,
        "availability_status": "Available" if stock_quantity > 0 else "Out of Stock",
        "available": 1 if stock_quantity > 0 else 0,
        "stock_quantity": stock_quantity,
        "book_status": book_status,
    }


def create_book(data):
    inventory = _normalized_book_inventory(data)
    return execute(
        """
        INSERT INTO books (
            title, author, category, isbn, publication_year, publisher, language,
            description, image, total_copies, available_copies, availability_status,
            available, price, stock_quantity, book_status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            inventory["total_copies"],
            inventory["available_copies"],
            inventory["availability_status"],
            inventory["available"],
            data.get("price", 0),
            inventory["stock_quantity"],
            inventory["book_status"],
        ),
    )


def update_book(book_id, data):
    inventory = _normalized_book_inventory(data)
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
            available = %s,
            price = %s,
            stock_quantity = %s,
            book_status = %s
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
            inventory["total_copies"],
            inventory["available_copies"],
            inventory["availability_status"],
            inventory["available"],
            data.get("price", 0),
            inventory["stock_quantity"],
            inventory["book_status"],
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
                       , stock_quantity
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
                or book["stock_quantity"] < 1
            ):
                return False
            new_stock = max(book["stock_quantity"] - 1, 0)
            new_available = 1 if new_stock > 0 else 0
            new_status = "Available" if new_available else "Out of Stock"
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
                    stock_quantity = %s,
                    available = %s,
                    availability_status = %s,
                    book_status = 'Borrowed'
                WHERE id = %s
                """,
                (new_stock, new_stock, new_available, new_status, book_id),
            )
            connection.commit()
            return loan["book_id"]
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
                SET stock_quantity = stock_quantity + 1,
                    available_copies = stock_quantity + 1,
                    total_copies = GREATEST(total_copies, stock_quantity + 1),
                    available = 1,
                    availability_status = 'Available',
                    book_status = 'Available'
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


def get_user_active_borrowed_books(user_id):
    return fetch_all(
        """
        SELECT *
        FROM (
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
              AND borrowed_books.status = 'borrowed'
        ) AS active_loans
        ORDER BY borrow_date DESC
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
        """
        SELECT id, username, email,
               COALESCE(phone_number, phone) AS phone_number,
               phone,
               address,
               role,
               status,
               created_at
        FROM users
        ORDER BY id ASC
        """
    )


def update_user(user_id, username, email, role, status, phone=None, address=None):
    execute(
        """
        UPDATE users
        SET username = %s,
            email = %s,
            role = %s,
            status = %s,
            phone = %s,
            phone_number = %s,
            address = %s
        WHERE id = %s
        """,
        (username, email, role, status, phone, phone, address, user_id),
    )
    if phone:
        execute(
            """
            INSERT IGNORE INTO phone_numbers (user_id, phone_number, is_primary)
            VALUES (%s, %s, 1)
            """,
            (user_id, phone),
        )


def delete_user(user_id):
    execute("DELETE FROM users WHERE id = %s", (user_id,))


def update_profile(user_id, username, email, phone, address):
    user = get_user_by_id(user_id)
    execute(
        """
        UPDATE users
        SET username = %s,
            email = %s,
            phone = %s,
            phone_number = %s,
            address = %s
        WHERE id = %s
        """,
        (username, email, phone, phone, address, user_id),
    )
    if phone:
        execute(
            """
            INSERT IGNORE INTO phone_numbers (user_id, phone_number, is_primary)
            VALUES (%s, %s, 1)
            """,
            (user_id, phone),
        )
    if user:
        for field_name, new_value in {
            "username": username,
            "email": email,
            "phone_number": phone,
            "address": address,
        }.items():
            old_value = user.get(field_name)
            if (old_value or "") != (new_value or ""):
                execute(
                    """
                    INSERT INTO profile_updates (user_id, field_name, old_value, new_value)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, field_name, old_value, new_value),
                )
                log_event(user_id, "profile_updated", "user", user_id, f"Profile field {field_name} updated")


def list_profile_updates(limit=20):
    return fetch_all(
        """
        SELECT profile_updates.*, users.username, users.email
        FROM profile_updates
        INNER JOIN users ON profile_updates.user_id = users.id
        ORDER BY profile_updates.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


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


def get_favourite_book_ids(user_id):
    rows = fetch_all("SELECT book_id FROM favourites WHERE user_id = %s", (user_id,))
    return {row["book_id"] for row in rows}


def is_book_favourite(user_id, book_id):
    return (
        fetch_one(
            "SELECT id FROM favourites WHERE user_id = %s AND book_id = %s",
            (user_id, book_id),
        )
        is not None
    )


def add_favourite(user_id, book_id):
    return execute(
        """
        INSERT IGNORE INTO favourites (user_id, book_id)
        VALUES (%s, %s)
        """,
        (user_id, book_id),
    )


def remove_favourite(user_id, book_id):
    execute("DELETE FROM favourites WHERE user_id = %s AND book_id = %s", (user_id, book_id))


def list_user_favourites(user_id):
    return fetch_all(
        """
        SELECT
            favourites.id AS favourite_id,
            favourites.created_at AS favourited_at,
            books.*,
            COALESCE(book_rating.average_rating, 0) AS average_rating,
            COALESCE(book_rating.total_ratings, 0) AS total_ratings,
            COALESCE(book_reviews.review_count, 0) AS review_count
        FROM favourites
        INNER JOIN books ON favourites.book_id = books.id
        LEFT JOIN (
            SELECT book_id, ROUND(AVG(rating), 1) AS average_rating, COUNT(*) AS total_ratings
            FROM ratings
            GROUP BY book_id
        ) AS book_rating ON book_rating.book_id = books.id
        LEFT JOIN (
            SELECT book_id, COUNT(*) AS review_count
            FROM reviews
            GROUP BY book_id
        ) AS book_reviews ON book_reviews.book_id = books.id
        WHERE favourites.user_id = %s
        ORDER BY favourites.created_at DESC
        """,
        (user_id,),
    )


def create_reservation(user_id, book_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM books WHERE id = %s", (book_id,))
            if not cursor.fetchone():
                return None

            cursor.execute(
                """
                SELECT id FROM reservations
                WHERE user_id = %s AND book_id = %s AND status IN ('Pending', 'Approved')
                LIMIT 1
                """,
                (user_id, book_id),
            )
            existing = cursor.fetchone()
            if existing:
                return existing["id"]

            expiry_date = datetime.now() + timedelta(days=3)
            cursor.execute(
                """
                INSERT INTO reservations (user_id, book_id, expiry_date, status)
                VALUES (%s, %s, %s, 'Pending')
                """,
                (user_id, book_id, expiry_date),
            )
            reservation_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                VALUES (%s, %s, %s, 'reservation', %s)
                """,
                (
                    user_id,
                    "Reservation requested",
                    "Your reservation request is pending admin approval.",
                    reservation_id,
                ),
            )
            cursor.execute(
                "UPDATE books SET book_status = 'Reserved' WHERE id = %s",
                (book_id,),
            )
            connection.commit()
            return reservation_id
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def expire_reservations():
    execute(
        """
        UPDATE reservations
        SET status = 'Expired',
            admin_note = COALESCE(admin_note, 'Reservation expired automatically')
        WHERE status IN ('Pending', 'Approved')
          AND expiry_date < NOW()
        """
    )
    execute(
        """
        UPDATE books
        SET available_copies = stock_quantity,
            available = CASE WHEN stock_quantity > 0 THEN 1 ELSE 0 END,
            availability_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Out of Stock' END
        """
    )


def list_user_reservations(user_id):
    expire_reservations()
    return fetch_all(
        """
        SELECT reservations.*, books.title, books.author, books.category, books.image
        FROM reservations
        INNER JOIN books ON reservations.book_id = books.id
        WHERE reservations.user_id = %s
          AND reservations.status IN ('Pending', 'Approved')
          AND reservations.expiry_date >= NOW()
        ORDER BY reservations.reservation_date DESC
        """,
        (user_id,),
    )


def list_admin_reservations():
    expire_reservations()
    return fetch_all(
        """
        SELECT reservations.*, users.username, users.email, books.title, books.author
        FROM reservations
        INNER JOIN users ON reservations.user_id = users.id
        INNER JOIN books ON reservations.book_id = books.id
        WHERE reservations.status IN ('Pending', 'Approved')
          AND reservations.expiry_date >= NOW()
        ORDER BY reservations.reservation_date DESC
        """
    )


def get_reservation(reservation_id):
    return fetch_one(
        """
        SELECT reservations.*, users.username, users.email, books.title, books.author
        FROM reservations
        INNER JOIN users ON reservations.user_id = users.id
        INNER JOIN books ON reservations.book_id = books.id
        WHERE reservations.id = %s
        """,
        (reservation_id,),
    )


def cancel_reservation(user_id, reservation_id):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT book_id FROM reservations
                WHERE id = %s AND user_id = %s AND status IN ('Pending', 'Approved')
                """,
                (reservation_id, user_id),
            )
            reservation = cursor.fetchone()
            if not reservation:
                return False
            cursor.execute(
                """
                UPDATE reservations
                SET status = 'Cancelled', admin_note = COALESCE(admin_note, 'Cancelled by user')
                WHERE id = %s
                """,
                (reservation_id,),
            )
            cursor.execute(
                """
                UPDATE books
                SET book_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Purchased' END
                WHERE id = %s
                """,
                (reservation["book_id"],),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_reservation_status(reservation_id, status, note=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, book_id FROM reservations
                WHERE id = %s
                """,
                (reservation_id,),
            )
            reservation = cursor.fetchone()
            if not reservation:
                return False

            cursor.execute(
                """
                UPDATE reservations
                SET status = %s, admin_note = %s
                WHERE id = %s
                """,
                (status, note, reservation_id),
            )
            next_book_status = "Reserved" if status in {"Pending", "Approved"} else "Available"
            cursor.execute(
                """
                UPDATE books
                SET book_status = CASE
                    WHEN %s = 'Reserved' THEN 'Reserved'
                    WHEN stock_quantity > 0 THEN 'Available'
                    ELSE 'Purchased'
                END
                WHERE id = %s
                """,
                (next_book_status, reservation["book_id"]),
            )
            cursor.execute(
                """
                INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                VALUES (%s, %s, %s, 'reservation', %s)
                """,
                (
                    reservation["user_id"],
                    f"Reservation {status.lower()}",
                    f"Your reservation has been {status.lower()}.",
                    reservation_id,
                ),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_reservation_admin(reservation_id, expiry_date, status, note=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT book_id FROM reservations WHERE id = %s", (reservation_id,))
            reservation = cursor.fetchone()
            if not reservation:
                return False
            cursor.execute(
                """
                UPDATE reservations
                SET expiry_date = %s,
                    status = %s,
                    admin_note = %s
                WHERE id = %s
                """,
                (expiry_date, status, note, reservation_id),
            )
            cursor.execute(
                """
                UPDATE books
                SET book_status = CASE
                    WHEN %s IN ('Pending', 'Approved') THEN 'Reserved'
                    WHEN stock_quantity > 0 THEN 'Available'
                    ELSE 'Purchased'
                END
                WHERE id = %s
                """,
                (status, reservation["book_id"]),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_reservation(reservation_id):
    reservation = fetch_one("SELECT book_id FROM reservations WHERE id = %s", (reservation_id,))
    execute("DELETE FROM reservations WHERE id = %s", (reservation_id,))
    if reservation:
        execute(
            """
            UPDATE books
            SET book_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Purchased' END
            WHERE id = %s
            """,
            (reservation["book_id"],),
        )


def create_order(user_id, book_id, quantity=1):
    quantity = max(int(quantity or 1), 1)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, price, stock_quantity
                FROM books
                WHERE id = %s
                FOR UPDATE
                """,
                (book_id,),
            )
            book = cursor.fetchone()
            if not book or book["stock_quantity"] < quantity:
                return None

            unit_price = book["price"] or 0
            total_amount = unit_price * quantity
            cursor.execute(
                """
                INSERT INTO orders (user_id, book_id, quantity, unit_price, total_amount, status)
                VALUES (%s, %s, %s, %s, %s, 'Pending')
                """,
                (user_id, book_id, quantity, unit_price, total_amount),
            )
            order_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO book_purchases (order_id, user_id, book_id, quantity, amount, status)
                VALUES (%s, %s, %s, %s, %s, 'Pending')
                """,
                (order_id, user_id, book_id, quantity, total_amount),
            )
            cursor.execute(
                """
                UPDATE books
                SET stock_quantity = stock_quantity - %s,
                    available_copies = stock_quantity - %s,
                    available = CASE WHEN stock_quantity - %s > 0 THEN 1 ELSE 0 END,
                    availability_status = CASE WHEN stock_quantity - %s > 0 THEN 'Available' ELSE 'Out of Stock' END,
                    book_status = 'In Buy List'
                WHERE id = %s
                """,
                (quantity, quantity, quantity, quantity, book_id),
            )
            cursor.execute(
                """
                INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                VALUES (%s, 'Order created', 'Your order has been recorded and is pending processing.', 'order', %s)
                """,
                (user_id, order_id),
            )
            connection.commit()
            return order_id
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_user_orders(user_id):
    return fetch_all(
        """
        SELECT orders.*, books.title, books.author, books.image, books.category
        FROM orders
        INNER JOIN books ON orders.book_id = books.id
        WHERE orders.user_id = %s
          AND orders.status != 'Cancelled'
        ORDER BY orders.order_date DESC
        """,
        (user_id,),
    )


def get_order(order_id, user_id=None):
    params = [order_id]
    user_filter = ""
    if user_id is not None:
        user_filter = "AND orders.user_id = %s"
        params.append(user_id)
    return fetch_one(
        f"""
        SELECT orders.*, books.title, books.author, books.isbn, books.publisher, books.image,
               users.username, users.email,
               purchase_receipts.receipt_number,
               purchase_receipts.issued_at AS receipt_issued_at
        FROM orders
        INNER JOIN books ON orders.book_id = books.id
        INNER JOIN users ON orders.user_id = users.id
        LEFT JOIN purchase_receipts ON purchase_receipts.order_id = orders.id
        WHERE orders.id = %s {user_filter}
        """,
        tuple(params),
    )


def list_admin_orders():
    return fetch_all(
        """
        SELECT orders.*, users.username, users.email, books.title, books.author
        FROM orders
        INNER JOIN users ON orders.user_id = users.id
        INNER JOIN books ON orders.book_id = books.id
        ORDER BY orders.order_date DESC
        """
    )


def update_order_payment(order_id, user_id, payment_method, payment_reference, payment_note, status):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, book_id, total_amount FROM orders
                WHERE id = %s AND user_id = %s
                FOR UPDATE
                """,
                (order_id, user_id),
            )
            order = cursor.fetchone()
            if not order:
                return False
            cursor.execute(
                """
                UPDATE orders
                SET payment_method = %s,
                    payment_reference = %s,
                    payment_note = %s,
                    status = %s
                WHERE id = %s AND user_id = %s
                """,
                (payment_method, payment_reference, payment_note, status, order_id, user_id),
            )
            cursor.execute(
                """
                UPDATE book_purchases
                SET payment_method = %s,
                    status = %s
                WHERE order_id = %s
                """,
                (payment_method, status, order_id),
            )
            if status in {"Paid", "Completed", "Processing"}:
                cursor.execute(
                    "UPDATE books SET book_status = 'Purchased' WHERE id = %s",
                    (order["book_id"],),
                )
            receipt_number = f"BV-RCPT-{order_id:05d}"
            cursor.execute(
                """
                INSERT INTO purchase_receipts (
                    order_id, receipt_number, amount, payment_method, payment_status
                )
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    amount = VALUES(amount),
                    payment_method = VALUES(payment_method),
                    payment_status = VALUES(payment_status)
                """,
                (order_id, receipt_number, order["total_amount"], payment_method, status),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_order_status(order_id, status):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT book_id FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                return False
            cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
            cursor.execute("UPDATE book_purchases SET status = %s WHERE order_id = %s", (status, order_id))
            if status == "Cancelled":
                cursor.execute(
                    """
                    UPDATE books
                    SET book_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Purchased' END
                    WHERE id = %s
                    """,
                    (order["book_id"],),
                )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_order_admin(order_id, quantity, status):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT unit_price FROM orders WHERE id = %s FOR UPDATE",
                (order_id,),
            )
            order = cursor.fetchone()
            if not order:
                return False
            quantity = max(int(quantity or 1), 1)
            total_amount = order["unit_price"] * quantity
            cursor.execute(
                """
                UPDATE orders
                SET quantity = %s,
                    total_amount = %s,
                    status = %s
                WHERE id = %s
                """,
                (quantity, total_amount, status, order_id),
            )
            cursor.execute(
                """
                UPDATE book_purchases
                SET quantity = %s,
                    amount = %s,
                    status = %s
                WHERE order_id = %s
                """,
                (quantity, total_amount, status, order_id),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_order(order_id):
    execute("DELETE FROM orders WHERE id = %s", (order_id,))


def upsert_review(user_id, book_id, review_text):
    review_id = execute(
        """
        INSERT INTO reviews (user_id, book_id, review_text)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            review_text = VALUES(review_text),
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, book_id, review_text),
    )
    execute(
        """
        INSERT INTO book_reviews (user_id, book_id, review_text)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            review_text = VALUES(review_text),
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, book_id, review_text),
    )
    return review_id


def delete_review(review_id, user_id=None, is_admin=False):
    if is_admin:
        execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    else:
        execute("DELETE FROM reviews WHERE id = %s AND user_id = %s", (review_id, user_id))


def list_book_reviews(book_id):
    return fetch_all(
        """
        SELECT reviews.*, users.username
        FROM reviews
        INNER JOIN users ON reviews.user_id = users.id
        WHERE reviews.book_id = %s
        ORDER BY COALESCE(reviews.updated_at, reviews.review_date) DESC
        """,
        (book_id,),
    )


def set_book_rating(user_id, book_id, rating):
    rating_id = execute(
        """
        INSERT INTO ratings (user_id, book_id, rating)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rating = VALUES(rating),
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, book_id, rating),
    )
    execute(
        """
        INSERT INTO book_reviews (user_id, book_id, rating)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rating = VALUES(rating),
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, book_id, rating),
    )
    return rating_id


def get_user_book_rating(user_id, book_id):
    row = fetch_one(
        "SELECT rating FROM ratings WHERE user_id = %s AND book_id = %s",
        (user_id, book_id),
    )
    return row["rating"] if row else 0


def get_library_rating_summary():
    summary = fetch_one(
        """
        SELECT COALESCE(ROUND(AVG(rating), 1), 0) AS average_rating,
               COUNT(*) AS total_reviews
        FROM ratings
        """
    )
    distribution = fetch_all(
        """
        SELECT rating, COUNT(*) AS total
        FROM ratings
        GROUP BY rating
        ORDER BY rating DESC
        """
    )
    summary["distribution"] = {row["rating"]: row["total"] for row in distribution}
    return summary


def list_user_reviews_and_ratings(user_id):
    return fetch_all(
        """
        SELECT
            books.id AS book_id,
            books.title,
            books.author,
            books.image,
            book_reviews.rating,
            book_reviews.review_text,
            book_reviews.review_date,
            book_reviews.updated_at,
            COALESCE(book_rating.average_rating, 0) AS average_rating,
            COALESCE(book_rating.total_ratings, 0) AS total_ratings
        FROM book_reviews
        INNER JOIN books ON book_reviews.book_id = books.id
        LEFT JOIN (
            SELECT book_id, ROUND(AVG(rating), 1) AS average_rating, COUNT(rating) AS total_ratings
            FROM book_reviews
            WHERE rating IS NOT NULL
            GROUP BY book_id
        ) AS book_rating ON book_rating.book_id = books.id
        WHERE book_reviews.user_id = %s
        ORDER BY COALESCE(book_reviews.updated_at, book_reviews.review_date) DESC
        """,
        (user_id,),
    )


def list_user_notifications(user_id, limit=8):
    return fetch_all(
        """
        SELECT *
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )


def generate_return_reminders(user_id=None):
    params = []
    user_filter = ""
    if user_id is not None:
        user_filter = "AND borrowed_books.user_id = %s"
        params.append(user_id)

    loans = fetch_all(
        f"""
        SELECT borrowed_books.id AS borrowed_id,
               borrowed_books.user_id,
               users.email,
               users.username,
               books.title,
               DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY) AS due_date,
               DATEDIFF(DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY), CURDATE()) AS days_until_due
        FROM borrowed_books
        INNER JOIN users ON borrowed_books.user_id = users.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        WHERE borrowed_books.status = 'borrowed' {user_filter}
        """,
        tuple(params),
    )

    created = []
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for loan in loans:
                days = loan["days_until_due"]
                if days == 3:
                    reminder_type = "3 Days Before Due Date"
                elif days == 1:
                    reminder_type = "1 Day Before Due Date"
                elif days == 0:
                    reminder_type = "Due Date"
                elif days < 0:
                    reminder_type = "Overdue Notice"
                else:
                    continue

                cursor.execute(
                    """
                    INSERT IGNORE INTO return_reminders (borrowed_id, user_id, reminder_type)
                    VALUES (%s, %s, %s)
                    """,
                    (loan["borrowed_id"], loan["user_id"], reminder_type),
                )
                if cursor.rowcount:
                    message = f"{loan['title']} is tied to a {reminder_type.lower()} reminder."
                    cursor.execute(
                        """
                        INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                        VALUES (%s, 'Return reminder', %s, 'return_reminder', %s)
                        """,
                        (loan["user_id"], message, loan["borrowed_id"]),
                    )
                    created.append({**loan, "reminder_type": reminder_type, "message": message})
            connection.commit()
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()
    return created


def get_fine_per_day():
    row = fetch_one("SELECT fine_per_day FROM fine_settings WHERE id = 1")
    return row["fine_per_day"] if row else 10


def update_fine_per_day(fine_per_day):
    execute(
        """
        INSERT INTO fine_settings (id, fine_per_day)
        VALUES (1, %s)
        ON DUPLICATE KEY UPDATE fine_per_day = VALUES(fine_per_day)
        """,
        (fine_per_day,),
    )


def refresh_fine_records(user_id=None):
    fine_per_day = get_fine_per_day()
    params = []
    user_filter = ""
    if user_id is not None:
        user_filter = "AND user_id = %s"
        params.append(user_id)

    loans = fetch_all(
        f"""
        SELECT id AS borrowed_id,
               user_id,
               GREATEST(
                   DATEDIFF(COALESCE(return_date, NOW()), DATE_ADD(borrow_date, INTERVAL 21 DAY)),
                   0
               ) AS overdue_days
        FROM borrowed_books
        WHERE status IN ('borrowed', 'returned') {user_filter}
        """,
        tuple(params),
    )

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for loan in loans:
                overdue_days = int(loan["overdue_days"] or 0)
                if overdue_days < 1:
                    continue

                total_fine = fine_per_day * overdue_days
                cursor.execute(
                    "SELECT id, status FROM fine_records WHERE borrowed_id = %s FOR UPDATE",
                    (loan["borrowed_id"],),
                )
                existing = cursor.fetchone()
                if existing and existing["status"] == "Paid":
                    continue
                if existing:
                    cursor.execute(
                        """
                        UPDATE fine_records
                        SET overdue_days = %s,
                            fine_per_day = %s,
                            total_fine = %s
                        WHERE id = %s
                        """,
                        (overdue_days, fine_per_day, total_fine, existing["id"]),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO fine_records (
                            borrowed_id, user_id, overdue_days, fine_per_day, total_fine, status
                        )
                        VALUES (%s, %s, %s, %s, %s, 'Pending')
                        """,
                        (
                            loan["borrowed_id"],
                            loan["user_id"],
                            overdue_days,
                            fine_per_day,
                            total_fine,
                        ),
                    )
            connection.commit()
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_user_fines(user_id):
    return fetch_all(
        """
        SELECT fine_records.*,
               borrowed_books.borrow_date,
               DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY) AS due_date,
               borrowed_books.return_date,
               books.title,
               books.author,
               (
                   SELECT fine_payments.status
                   FROM fine_payments
                   WHERE fine_payments.fine_record_id = fine_records.id
                   ORDER BY fine_payments.created_at DESC
                   LIMIT 1
               ) AS payment_status,
               (
                   SELECT fine_payments.id
                   FROM fine_payments
                   WHERE fine_payments.fine_record_id = fine_records.id
                   ORDER BY fine_payments.created_at DESC
                   LIMIT 1
               ) AS payment_id
        FROM fine_records
        INNER JOIN borrowed_books ON fine_records.borrowed_id = borrowed_books.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        WHERE fine_records.user_id = %s
        ORDER BY fine_records.calculated_at DESC
        """,
        (user_id,),
    )


def create_fine_payment(user_id, fine_record_id, payment_method, transaction_id, amount, proof):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, total_fine, status
                FROM fine_records
                WHERE id = %s AND user_id = %s
                FOR UPDATE
                """,
                (fine_record_id, user_id),
            )
            fine = cursor.fetchone()
            if not fine or fine["status"] == "Paid":
                return None

            cursor.execute(
                """
                INSERT INTO fine_payments (
                    fine_record_id, user_id, payment_method, transaction_id,
                    payment_date, amount, proof_of_payment, status
                )
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, 'Pending Verification')
                """,
                (fine_record_id, user_id, payment_method, transaction_id, amount, proof),
            )
            payment_id = cursor.lastrowid
            receipt_number = f"BV-FINE-{payment_id:05d}"
            cursor.execute(
                """
                INSERT INTO payment_receipts (
                    payment_id, receipt_number, amount, payment_method, payment_status
                )
                VALUES (%s, %s, %s, %s, 'Pending Verification')
                """,
                (payment_id, receipt_number, amount, payment_method),
            )
            cursor.execute(
                "UPDATE fine_records SET status = 'Pending Verification' WHERE id = %s",
                (fine_record_id,),
            )
            connection.commit()
            return payment_id
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_admin_fine_payments():
    return fetch_all(
        """
        SELECT fine_payments.*,
               fine_records.total_fine,
               fine_records.overdue_days,
               users.username,
               users.email,
               books.title
        FROM fine_payments
        INNER JOIN fine_records ON fine_payments.fine_record_id = fine_records.id
        INNER JOIN users ON fine_payments.user_id = users.id
        INNER JOIN borrowed_books ON fine_records.borrowed_id = borrowed_books.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        ORDER BY fine_payments.created_at DESC
        """
    )


def get_fine_payment(payment_id, user_id=None):
    params = [payment_id]
    user_filter = ""
    if user_id is not None:
        user_filter = "AND fine_payments.user_id = %s"
        params.append(user_id)
    return fetch_one(
        f"""
        SELECT fine_payments.*,
               fine_records.total_fine,
               fine_records.overdue_days,
               users.username,
               users.email,
               books.title,
               books.author,
               payment_receipts.receipt_number,
               payment_receipts.issued_at AS receipt_issued_at
        FROM fine_payments
        INNER JOIN fine_records ON fine_payments.fine_record_id = fine_records.id
        INNER JOIN users ON fine_payments.user_id = users.id
        INNER JOIN borrowed_books ON fine_records.borrowed_id = borrowed_books.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        LEFT JOIN payment_receipts ON payment_receipts.payment_id = fine_payments.id
        WHERE fine_payments.id = %s {user_filter}
        """,
        tuple(params),
    )


def update_fine_payment(payment_id, payment_method, transaction_id, amount, proof, status):
    execute(
        """
        UPDATE fine_payments
        SET payment_method = %s,
            transaction_id = %s,
            amount = %s,
            proof_of_payment = %s,
            status = %s
        WHERE id = %s
        """,
        (payment_method, transaction_id, amount, proof, status, payment_id),
    )
    execute(
        """
        UPDATE payment_receipts
        SET amount = %s,
            payment_method = %s,
            payment_status = %s
        WHERE payment_id = %s
        """,
        (amount, payment_method, status, payment_id),
    )


def delete_fine_payment(payment_id):
    execute("DELETE FROM fine_payments WHERE id = %s", (payment_id,))


def update_fine_payment_status(payment_id, status):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT fine_record_id, user_id FROM fine_payments WHERE id = %s",
                (payment_id,),
            )
            payment = cursor.fetchone()
            if not payment:
                return False

            cursor.execute(
                """
                UPDATE fine_payments
                SET status = %s, verified_at = NOW()
                WHERE id = %s
                """,
                (status, payment_id),
            )
            fine_status = "Paid" if status == "Approved" else "Payment Rejected"
            cursor.execute(
                "UPDATE fine_records SET status = %s WHERE id = %s",
                (fine_status, payment["fine_record_id"]),
            )
            cursor.execute(
                "UPDATE payment_receipts SET payment_status = %s WHERE payment_id = %s",
                (status, payment_id),
            )
            cursor.execute(
                """
                INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                VALUES (%s, %s, %s, 'fine_payment', %s)
                """,
                (
                    payment["user_id"],
                    f"Fine payment {status.lower()}",
                    f"Your fine payment has been {status.lower()}.",
                    payment_id,
                ),
            )
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


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
