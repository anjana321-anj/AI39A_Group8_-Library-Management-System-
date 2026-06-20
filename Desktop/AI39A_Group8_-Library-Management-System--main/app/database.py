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

    if "profile_pic_url" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN profile_pic_url VARCHAR(500) NULL AFTER address")
        columns.add("profile_pic_url")

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
            SET name = COALESCE(NULLIF(name, ''), NULLIF(username, ''), SUBSTRING_INDEX(email, '@', 1))
            WHERE name IS NULL OR name = ''
            """
        )
        try:
            cursor.execute("ALTER TABLE users MODIFY name VARCHAR(100) NULL")
        except pymysql.MySQLError:
            # Some legacy schemas may define name differently; including it in INSERTs still keeps writes safe.
            pass
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
        cursor.execute(
            """
            UPDATE users
            SET password = COALESCE(NULLIF(password, ''), password_hash)
            WHERE password IS NULL OR password = ''
            """
        )
        try:
            cursor.execute("ALTER TABLE users MODIFY password VARCHAR(255) NULL")
        except pymysql.MySQLError:
            pass

    fallback_hash = generate_password_hash("bookverse123")
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE password_hash IS NULL OR password_hash = ''",
        (fallback_hash,),
    )
    cursor.execute("ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL")
    cursor.execute("ALTER TABLE users MODIFY password_hash VARCHAR(255) NOT NULL")

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
    if cursor.fetchone()["total"] == 0:
        admin_hash = generate_password_hash("Admin123")
        insert_columns = ["username", "email", "password_hash", "role", "status"]
        values = ["BookVerse Admin", "admin@bookverse.com", admin_hash, "admin", "active"]
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
        "book_type": "ALTER TABLE books ADD COLUMN book_type VARCHAR(20) NOT NULL DEFAULT 'Physical' AFTER book_status",
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
            WHEN stock_quantity = 0 AND (book_status IS NULL OR book_status = '' OR book_status = 'Available') THEN 'Out of Stock'
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
            "book_type": "Physical",
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
            "book_type": "Digital",
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
            "book_type": "Physical",
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
            "book_type": "Digital",
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
            "book_type": "Physical",
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
            "book_type": "Digital",
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
            , book_type = 'Digital'
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
            sample.get("book_type", "Physical"),
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
                    book_status = %s,
                    book_type = %s
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
                    , book_status, book_type
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        INSERT IGNORE INTO phone_numbers (user_id, phone_number, is_primary)
        SELECT id, phone_number, 1
        FROM users
        WHERE phone_number IS NOT NULL AND phone_number != ''
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
        CREATE TABLE IF NOT EXISTS review_likes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            review_id INT NOT NULL,
            user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_review_like (review_id, user_id),
            CONSTRAINT fk_review_likes_review
                FOREIGN KEY (review_id) REFERENCES book_reviews(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_review_likes_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS review_replies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            review_id INT NOT NULL,
            user_id INT NOT NULL,
            reply_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_review_replies_review
                FOREIGN KEY (review_id) REFERENCES book_reviews(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_review_replies_user
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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS library_reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            rating INT NOT NULL,
            review_text TEXT NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'Visible',
            is_pinned TINYINT(1) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL,
            deleted_at TIMESTAMP NULL,
            UNIQUE KEY uq_library_review_user (user_id),
            CONSTRAINT fk_library_reviews_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT chk_library_review_rating CHECK (rating BETWEEN 1 AND 5)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS library_ratings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            rating INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL,
            UNIQUE KEY uq_library_rating_user (user_id),
            CONSTRAINT fk_library_ratings_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT chk_library_rating_range CHECK (rating BETWEEN 1 AND 5)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS review_moderation_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            review_type VARCHAR(30) NOT NULL,
            review_id INT NOT NULL,
            admin_user_id INT NULL,
            action VARCHAR(40) NOT NULL,
            note VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_review_moderation_admin
                FOREIGN KEY (admin_user_id) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_pictures (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            image_path VARCHAR(500) NOT NULL,
            object_position VARCHAR(40) NOT NULL DEFAULT 'center center',
            status VARCHAR(30) NOT NULL DEFAULT 'Active',
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP NULL,
            removed_at TIMESTAMP NULL,
            removed_by INT NULL,
            CONSTRAINT fk_profile_pictures_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_profile_pictures_removed_by
                FOREIGN KEY (removed_by) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    _ensure_column(
        cursor,
        "profile_pictures",
        "object_position",
        "ALTER TABLE profile_pictures ADD COLUMN object_position VARCHAR(40) NOT NULL DEFAULT 'center center' AFTER image_path",
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_picture_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            picture_id INT NULL,
            action VARCHAR(40) NOT NULL,
            image_path VARCHAR(500) NULL,
            admin_user_id INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_profile_picture_history_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_profile_picture_history_picture
                FOREIGN KEY (picture_id) REFERENCES profile_pictures(id)
                ON DELETE SET NULL,
            CONSTRAINT fk_profile_picture_history_admin
                FOREIGN KEY (admin_user_id) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS waitlists (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notification_date TIMESTAMP NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'Active',
            admin_note VARCHAR(255) NULL,
            UNIQUE KEY uq_waitlist_user_book (user_id, book_id),
            CONSTRAINT fk_waitlists_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_waitlists_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS waitlist_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            waitlist_id INT NULL,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            action VARCHAR(40) NOT NULL,
            note VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_waitlist_history_waitlist
                FOREIGN KEY (waitlist_id) REFERENCES waitlists(id)
                ON DELETE SET NULL,
            CONSTRAINT fk_waitlist_history_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_waitlist_history_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS borrow_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            borrowed_id INT NULL,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            action VARCHAR(40) NOT NULL,
            status VARCHAR(30) NOT NULL,
            note VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_borrow_history_borrowed
                FOREIGN KEY (borrowed_id) REFERENCES borrowed_books(id)
                ON DELETE SET NULL,
            CONSTRAINT fk_borrow_history_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_borrow_history_book
                FOREIGN KEY (book_id) REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS borrow_reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            report_name VARCHAR(120) NOT NULL,
            generated_by INT NULL,
            file_path VARCHAR(500) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_borrow_reports_admin
                FOREIGN KEY (generated_by) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fine_reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            report_name VARCHAR(120) NOT NULL,
            generated_by INT NULL,
            file_path VARCHAR(500) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_fine_reports_admin
                FOREIGN KEY (generated_by) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            backup_type VARCHAR(40) NOT NULL,
            file_path VARCHAR(500) NULL,
            admin_user_id INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_backup_history_admin
                FOREIGN KEY (admin_user_id) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS security_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NULL,
            email VARCHAR(255) NULL,
            event_type VARCHAR(80) NOT NULL,
            ip_address VARCHAR(80) NULL,
            summary VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_security_logs_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            access_level VARCHAR(40) NOT NULL DEFAULT 'full',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_admin_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dev_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            plain_password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            note VARCHAR(255) NOT NULL DEFAULT 'Development login only',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_dev_users_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )
    _ensure_column(
        cursor,
        "book_reviews",
        "action_type",
        "ALTER TABLE book_reviews ADD COLUMN action_type VARCHAR(30) NULL AFTER review_text",
    )
    _ensure_column(
        cursor,
        "book_reviews",
        "status",
        "ALTER TABLE book_reviews ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'Visible' AFTER action_type",
    )
    _ensure_column(
        cursor,
        "book_reviews",
        "is_pinned",
        "ALTER TABLE book_reviews ADD COLUMN is_pinned TINYINT(1) NOT NULL DEFAULT 0 AFTER status",
    )
    _ensure_column(
        cursor,
        "book_reviews",
        "deleted_at",
        "ALTER TABLE book_reviews ADD COLUMN deleted_at TIMESTAMP NULL AFTER updated_at",
    )
    _ensure_column(
        cursor,
        "fine_records",
        "reason",
        "ALTER TABLE fine_records ADD COLUMN reason VARCHAR(255) NOT NULL DEFAULT 'Overdue return' AFTER user_id",
    )


def _seed_sprint_accounts_and_activity(cursor):
    seed_accounts = [
        ("BookVerse Admin", "admin@bookverse.com", "Admin123", "admin", "active", "9800000000"),
        ("Hari Sharma", "hari@gmail.com", "hari456hari", "user", "active", "9811000001"),
        ("Sita Thapa", "sita@gmail.com", "sita456sita", "user", "active", "9811000002"),
        ("Ram Karki", "ram@gmail.com", "ram456ram", "user", "active", "9811000003"),
        ("Gita Rai", "gita@gmail.com", "gita456gita", "user", "active", "9811000004"),
        ("Bishal Gurung", "bishal@gmail.com", "bishal456", "user", "active", "9811000005"),
        ("Sabin Lama", "sabin@gmail.com", "sabin456", "user", "active", "9811000006"),
        ("Suman Adhikari", "suman@gmail.com", "suman456", "user", "active", "9811000007"),
        ("Prakash Shrestha", "prakash@gmail.com", "prakash456", "user", "active", "9811000008"),
        ("Anita Bhandari", "anita@gmail.com", "anita456", "user", "active", "9811000009"),
        ("Puja Basnet", "puja@gmail.com", "puja456", "user", "active", "9811000010"),
        ("Nirmala KC", "nirmala@gmail.com", "nirmala456", "user", "active", "9811000011"),
        ("Aashish Maharjan", "aashish@gmail.com", "aashish456", "user", "active", "9811000012"),
        ("Meena Tamang", "meena@gmail.com", "meena456", "user", "active", "9811000013"),
        ("Roshan Poudel", "roshan@gmail.com", "roshan456", "user", "active", "9811000014"),
        ("Kabita Nepal", "kabita@gmail.com", "kabita456", "user", "active", "9811000015"),
    ]

    for username, email, password, role, status, phone in seed_accounts:
        password_hash = generate_password_hash(password)
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, role, status, phone, phone_number, address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Kathmandu, Nepal')
            ON DUPLICATE KEY UPDATE
                username = VALUES(username),
                password_hash = VALUES(password_hash),
                role = VALUES(role),
                status = VALUES(status),
                phone = VALUES(phone),
                phone_number = VALUES(phone_number)
            """,
            (username, email, password_hash, role, status, phone, phone),
        )

    seed_emails = [account[1] for account in seed_accounts]
    placeholders = ", ".join(["%s"] * len(seed_emails))
    cursor.execute(f"SELECT id, email FROM users WHERE email IN ({placeholders})", seed_emails)
    users = {row["email"]: row["id"] for row in cursor.fetchall()}
    for username, email, password, role, _status, _phone in seed_accounts:
        cursor.execute(
            """
            INSERT INTO dev_users (user_id, email, plain_password, role)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                user_id = VALUES(user_id),
                plain_password = VALUES(plain_password),
                role = VALUES(role)
            """,
            (users.get(email), email, password, role),
        )
    if users.get("admin@bookverse.com"):
        cursor.execute(
            """
            INSERT IGNORE INTO admin (user_id, access_level)
            VALUES (%s, 'full')
            """,
            (users["admin@bookverse.com"],),
        )
    cursor.execute("SELECT id FROM books ORDER BY id ASC LIMIT 8")
    book_ids = [row["id"] for row in cursor.fetchall()]
    if not book_ids:
        return

    def book(index):
        return book_ids[index % len(book_ids)]

    def user(email):
        return users.get(email)

    def insert_activity(actor_id, event_type, entity_type, entity_id, summary):
        cursor.execute(
            """
            INSERT INTO activity_logs (actor_user_id, event_type, entity_type, entity_id, summary)
            SELECT %s, %s, %s, %s, %s
            FROM DUAL
            WHERE NOT EXISTS (
                SELECT 1 FROM activity_logs
                WHERE actor_user_id <=> %s AND event_type = %s AND entity_type = %s
                  AND entity_id <=> %s AND summary = %s
            )
            """,
            (actor_id, event_type, entity_type, entity_id, summary, actor_id, event_type, entity_type, entity_id, summary),
        )

    def insert_borrow(email, book_id, status, days_ago, returned_days_ago=None):
        user_id = user(email)
        if not user_id:
            return None
        cursor.execute(
            """
            SELECT id FROM borrowed_books
            WHERE user_id = %s AND book_id = %s AND status = %s
            LIMIT 1
            """,
            (user_id, book_id, status),
        )
        existing = cursor.fetchone()
        if existing:
            return existing["id"]
        return_date_sql = "DATE_SUB(NOW(), INTERVAL %s DAY)" if returned_days_ago is not None else "NULL"
        params = [user_id, book_id, days_ago, days_ago]
        if returned_days_ago is not None:
            params.append(returned_days_ago)
        params.append(status)
        cursor.execute(
            f"""
            INSERT INTO borrowed_books (user_id, book_id, borrow_date, due_date, return_date, status)
            VALUES (%s, %s, DATE_SUB(NOW(), INTERVAL %s DAY),
                    DATE_ADD(DATE_SUB(NOW(), INTERVAL %s DAY), INTERVAL 21 DAY),
                    {return_date_sql}, %s)
            """,
            tuple(params),
        )
        borrowed_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
            VALUES (%s, %s, %s, 'Seeded', %s, 'Sample sprint activity')
            """,
            (borrowed_id, user_id, book_id, status),
        )
        insert_activity(user_id, "borrow_book", "borrowed_book", borrowed_id, "Sample borrow activity")
        return borrowed_id

    hari_borrow = insert_borrow("hari@gmail.com", book(0), "borrowed", 4)
    insert_borrow("puja@gmail.com", book(1), "returned", 18, returned_days_ago=2)
    insert_borrow("nirmala@gmail.com", book(2), "borrowed", 2)
    insert_borrow("nirmala@gmail.com", book(3), "returned", 30, returned_days_ago=5)
    overdue_borrow = insert_borrow("aashish@gmail.com", book(4), "overdue", 35)
    gita_borrow = insert_borrow("gita@gmail.com", book(5), "returned", 42, returned_days_ago=6)
    meena_borrow = insert_borrow("meena@gmail.com", book(6), "overdue", 34)

    for email, book_index in (("sita@gmail.com", 1), ("kabita@gmail.com", 5)):
        user_id = user(email)
        if user_id:
            cursor.execute(
                """
                INSERT INTO reservations (user_id, book_id, expiry_date, status, admin_note)
                SELECT %s, %s, DATE_ADD(NOW(), INTERVAL 2 DAY), 'Pending', 'Sample active reservation'
                FROM DUAL
                WHERE NOT EXISTS (
                    SELECT 1 FROM reservations
                    WHERE user_id = %s AND book_id = %s AND status IN ('Pending', 'Approved')
                )
                """,
                (user_id, book(book_index), user_id, book(book_index)),
            )
            insert_activity(user_id, "reserve_book", "book", book(book_index), "Sample reservation activity")

    ram_id = user("ram@gmail.com")
    if ram_id:
        cursor.execute(
            """
            SELECT id FROM orders WHERE user_id = %s AND book_id = %s LIMIT 1
            """,
            (ram_id, book(2)),
        )
        order = cursor.fetchone()
        if not order:
            cursor.execute(
                """
                INSERT INTO orders (user_id, book_id, quantity, unit_price, total_amount, status, payment_method, payment_reference, payment_note)
                SELECT %s, books.id, 1, books.price, books.price, 'Paid', 'QR Payment', 'SEED-QR-001', 'Seed purchase receipt'
                FROM books WHERE books.id = %s
                """,
                (ram_id, book(2)),
            )
            order_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT IGNORE INTO book_purchases (order_id, user_id, book_id, quantity, amount, payment_method, status)
                SELECT %s, %s, books.id, 1, books.price, 'QR Payment', 'Paid'
                FROM books WHERE books.id = %s
                """,
                (order_id, ram_id, book(2)),
            )
            cursor.execute(
                """
                INSERT IGNORE INTO purchase_receipts (order_id, receipt_number, amount, payment_method, payment_status)
                SELECT %s, %s, books.price, 'QR Payment', 'Paid'
                FROM books WHERE books.id = %s
                """,
                (order_id, f"BV-SEED-{order_id:05d}", book(2)),
            )
            insert_activity(ram_id, "purchase_book", "order", order_id, "Sample purchase activity")

    for email, borrowed_id in (("gita@gmail.com", gita_borrow), ("meena@gmail.com", meena_borrow)):
        user_id = user(email)
        if user_id and borrowed_id:
            cursor.execute(
                """
                INSERT INTO fine_records (borrowed_id, user_id, reason, overdue_days, fine_per_day, total_fine, status)
                SELECT %s, %s, 'Overdue return', 14, 10.00, 140.00, 'Pending'
                FROM DUAL
                WHERE NOT EXISTS (SELECT 1 FROM fine_records WHERE borrowed_id = %s AND user_id = %s)
                """,
                (borrowed_id, user_id, borrowed_id, user_id),
            )
            insert_activity(user_id, "fine_payment", "fine_record", cursor.lastrowid or None, "Sample fine activity")

    bishal_id = user("bishal@gmail.com")
    if bishal_id:
        cursor.execute(
            """
            INSERT INTO library_reviews (user_id, rating, review_text, status, is_pinned)
            VALUES (%s, 5, 'BookVerse feels organized, clear, and easy to use for students.', 'Visible', 1)
            ON DUPLICATE KEY UPDATE rating = VALUES(rating), review_text = VALUES(review_text), status = 'Visible'
            """,
            (bishal_id,),
        )
        cursor.execute(
            """
            INSERT INTO library_ratings (user_id, rating)
            VALUES (%s, 5)
            ON DUPLICATE KEY UPDATE rating = VALUES(rating), updated_at = CURRENT_TIMESTAMP
            """,
            (bishal_id,),
        )
        insert_activity(bishal_id, "library_review", "library_review", None, "Sample library review")

    for email, rating, text, book_index, action_type in (
        ("sabin@gmail.com", 4, "A practical and memorable read for focused learners.", 0, "Borrowed"),
        ("roshan@gmail.com", 5, "Excellent book with strong ideas and clear examples.", 2, "Purchased"),
    ):
        user_id = user(email)
        if user_id:
            cursor.execute(
                """
                INSERT INTO book_reviews (user_id, book_id, rating, review_text, action_type, status)
                VALUES (%s, %s, %s, %s, %s, 'Visible')
                ON DUPLICATE KEY UPDATE
                    rating = VALUES(rating),
                    review_text = VALUES(review_text),
                    action_type = VALUES(action_type),
                    status = 'Visible'
                """,
                (user_id, book(book_index), rating, text, action_type),
            )
            cursor.execute(
                """
                INSERT INTO ratings (user_id, book_id, rating)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE rating = VALUES(rating)
                """,
                (user_id, book(book_index), rating),
            )
            cursor.execute(
                """
                INSERT INTO reviews (user_id, book_id, review_text)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE review_text = VALUES(review_text)
                """,
                (user_id, book(book_index), text),
            )
            insert_activity(user_id, "book_review", "book", book(book_index), "Sample book review")

    suman_id = user("suman@gmail.com")
    if suman_id:
        cursor.execute(
            """
            INSERT INTO waitlists (user_id, book_id, status, admin_note)
            VALUES (%s, %s, 'Active', 'Sample waitlist record')
            ON DUPLICATE KEY UPDATE status = 'Active', admin_note = VALUES(admin_note)
            """,
            (suman_id, book(6)),
        )
        waitlist_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
            VALUES (%s, %s, %s, 'Joined', 'Sample waitlist history')
            """,
            (waitlist_id or None, suman_id, book(6)),
        )
        insert_activity(suman_id, "waitlist_join", "book", book(6), "Sample waitlist activity")

    prakash_id = user("prakash@gmail.com")
    if prakash_id:
        cursor.execute(
            """
            INSERT INTO profile_updates (user_id, field_name, old_value, new_value)
            SELECT %s, 'address', 'Lalitpur', 'Kathmandu, Nepal'
            FROM DUAL
            WHERE NOT EXISTS (
                SELECT 1 FROM profile_updates
                WHERE user_id = %s AND field_name = 'address' AND new_value = 'Kathmandu, Nepal'
            )
            """,
            (prakash_id, prakash_id),
        )
        insert_activity(prakash_id, "profile_updated", "user", prakash_id, "Sample profile update")

    anita_id = user("anita@gmail.com")
    if anita_id:
        cursor.execute(
            """
            SELECT id FROM profile_pictures
            WHERE user_id = %s AND image_path = '/image/Logo.png'
            LIMIT 1
            """,
            (anita_id,),
        )
        picture = cursor.fetchone()
        if not picture:
            cursor.execute(
                """
                INSERT INTO profile_pictures (user_id, image_path, status)
                VALUES (%s, '/image/Logo.png', 'Active')
                """,
                (anita_id,),
            )
            picture_id = cursor.lastrowid
            cursor.execute(
                "UPDATE users SET profile_pic_url = '/image/Logo.png' WHERE id = %s",
                (anita_id,),
            )
            cursor.execute(
                """
                INSERT INTO profile_picture_history (user_id, picture_id, action, image_path)
                VALUES (%s, %s, 'Uploaded', '/image/Logo.png')
                """,
                (anita_id, picture_id),
            )
            insert_activity(anita_id, "profile_picture_change", "profile_picture", picture_id, "Sample profile picture change")

    admin_id = user("admin@bookverse.com")
    insert_activity(admin_id, "admin_login_ready", "security", None, "Seed admin account prepared")
    cursor.execute(
        f"""
        INSERT INTO notifications (user_id, title, message, notification_type, related_id)
        SELECT id, 'Welcome to BookVerse', 'Your sprint demo account is ready for testing.', 'system', NULL
        FROM users
        WHERE email IN ({placeholders})
          AND NOT EXISTS (
              SELECT 1 FROM notifications
              WHERE notifications.user_id = users.id AND title = 'Welcome to BookVerse'
          )
        """,
        seed_emails,
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
        _ensure_column(
            cursor,
            "borrowed_books",
            "due_date",
            "ALTER TABLE borrowed_books ADD COLUMN due_date DATETIME NULL AFTER borrow_date",
        )
        _ensure_column(
            cursor,
            "borrowed_books",
            "fine_amount",
            "ALTER TABLE borrowed_books ADD COLUMN fine_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER return_date",
        )
        _ensure_column(
            cursor,
            "borrowed_books",
            "payment_status",
            "ALTER TABLE borrowed_books ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'Unpaid' AFTER fine_amount",
        )
        _ensure_column(
            cursor,
            "borrowed_books",
            "payment_amount",
            "ALTER TABLE borrowed_books ADD COLUMN payment_amount DECIMAL(10,2) NOT NULL DEFAULT 50.00 AFTER payment_status",
        )
        _ensure_column(
            cursor,
            "borrowed_books",
            "payment_date",
            "ALTER TABLE borrowed_books ADD COLUMN payment_date DATETIME NULL AFTER payment_amount",
        )
        _ensure_column(
            cursor,
            "borrowed_books",
            "renewal_count",
            "ALTER TABLE borrowed_books ADD COLUMN renewal_count INT NOT NULL DEFAULT 0 AFTER due_date",
        )
        cursor.execute(
            """
            UPDATE borrowed_books
            SET due_date = DATE_ADD(borrow_date, INTERVAL 21 DAY)
            WHERE due_date IS NULL
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
        _seed_sprint_accounts_and_activity(cursor)
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


def get_user_by_username(username):
    return fetch_one("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))


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
        SELECT book_id, ROUND(AVG(rating), 1) AS average_rating, COUNT(rating) AS total_ratings
        FROM book_reviews
        WHERE rating IS NOT NULL AND status = 'Visible' AND deleted_at IS NULL
        GROUP BY book_id
    ) AS book_rating ON book_rating.book_id = books.id
    LEFT JOIN (
        SELECT book_id, COUNT(*) AS review_count
        FROM book_reviews
        WHERE review_text IS NOT NULL AND status = 'Visible' AND deleted_at IS NULL
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
        WHERE borrowed_books.status IN ('borrowed', 'overdue')
        GROUP BY borrowed_books.book_id
    ) AS latest_borrow ON latest_borrow.book_id = books.id
    LEFT JOIN borrowed_books AS borrowed_record ON borrowed_record.id = latest_borrow.latest_borrow_id
    LEFT JOIN users AS borrowed_user ON borrowed_user.id = borrowed_record.user_id
"""


def list_books():
    return fetch_all(
        BOOK_SELECT_WITH_METRICS
        + """
        WHERE books.id IN (
            SELECT MIN(unique_books.id)
            FROM books AS unique_books
            GROUP BY COALESCE(NULLIF(unique_books.isbn, ''), CONCAT(LOWER(TRIM(unique_books.title)), '|', LOWER(TRIM(unique_books.author))))
        )
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
    allowed_statuses = {"Available", "Out of Stock", "Borrowed", "Reserved", "Purchased", "In Buy List"}
    requested_status = data.get("book_status")
    if stock_quantity == 0 and requested_status == "Available":
        book_status = "Out of Stock"
    elif requested_status in allowed_statuses:
        book_status = requested_status
    else:
        book_status = "Available" if stock_quantity > 0 else "Out of Stock"
    return {
        "total_copies": total_copies,
        "available_copies": stock_quantity,
        "availability_status": "Available" if stock_quantity > 0 else "Out of Stock",
        "available": 1 if stock_quantity > 0 else 0,
        "stock_quantity": stock_quantity,
        "book_status": book_status,
        "book_type": data.get("book_type") if data.get("book_type") in {"Physical", "Digital"} else "Physical",
    }


def create_book(data):
    inventory = _normalized_book_inventory(data)
    return execute(
        """
        INSERT INTO books (
            title, author, category, isbn, publication_year, publisher, language,
            description, image, total_copies, available_copies, availability_status,
            available, price, stock_quantity, book_status, book_type
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            inventory["book_type"],
        ),
    )


def notify_waitlisted_users(book_id):
    connection = get_connection()
    notified = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id
                FROM waitlists
                WHERE book_id = %s AND status = 'Active'
                ORDER BY join_date ASC
                """,
                (book_id,),
            )
            for waitlist in cursor.fetchall():
                cursor.execute(
                    """
                    UPDATE waitlists
                    SET status = 'Notified',
                        notification_date = NOW(),
                        admin_note = COALESCE(admin_note, 'Book availability notification sent')
                    WHERE id = %s
                    """,
                    (waitlist["id"],),
                )
                cursor.execute(
                    """
                    INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
                    VALUES (%s, %s, %s, 'Notified', 'Book became available')
                    """,
                    (waitlist["id"], waitlist["user_id"], book_id),
                )
                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                    VALUES (%s, 'Book available', 'A book from your waitlist is now available.', 'waitlist', %s)
                    """,
                    (waitlist["user_id"], book_id),
                )
                notified += 1
            connection.commit()
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()
    return notified


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
            book_status = %s,
            book_type = %s
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
            inventory["book_type"],
            book_id,
        ),
    )
    if inventory["stock_quantity"] > 0:
        notify_waitlisted_users(book_id)


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
            if not book or not book["available"] or book["availability_status"] != "Available" or book["stock_quantity"] < 1:
                return False

            cursor.execute(
                """
                SELECT id FROM borrowed_books
                WHERE user_id = %s AND book_id = %s AND status IN ('borrowed', 'overdue')
                LIMIT 1
                """,
                (user_id, book_id),
            )
            if cursor.fetchone():
                return False
            new_stock = max(book["stock_quantity"] - 1, 0)
            new_available = 1 if new_stock > 0 else 0
            new_status = "Available" if new_available else "Out of Stock"
            cursor.execute(
                """
                INSERT INTO borrowed_books (user_id, book_id, due_date, status)
                VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 21 DAY), 'borrowed')
                """,
                (user_id, book_id),
            )
            borrowed_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
                VALUES (%s, %s, %s, 'Borrowed', 'borrowed', 'Book borrowed by user')
                """,
                (borrowed_id, user_id, book_id),
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
                WHERE id = %s AND user_id = %s AND status IN ('borrowed', 'overdue')
                """,
                (borrowed_id, user_id),
            )
            loan = cursor.fetchone()
            if not loan:
                return False
            cursor.execute(
                """
                UPDATE borrowed_books
                SET status = 'returned',
                    return_date = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (borrowed_id,),
            )
            cursor.execute(
                """
                INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
                VALUES (%s, %s, %s, 'Returned', 'returned', 'Book returned by user')
                """,
                (borrowed_id, user_id, loan["book_id"]),
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
            cursor.execute(
                """
                SELECT id, user_id
                FROM waitlists
                WHERE book_id = %s AND status = 'Active'
                ORDER BY join_date ASC
                """,
                (loan["book_id"],),
            )
            for waitlist in cursor.fetchall():
                cursor.execute(
                    """
                    UPDATE waitlists
                    SET status = 'Notified',
                        notification_date = NOW(),
                        admin_note = COALESCE(admin_note, 'Book availability notification sent')
                    WHERE id = %s
                    """,
                    (waitlist["id"],),
                )
                cursor.execute(
                    """
                    INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
                    VALUES (%s, %s, %s, 'Notified', 'Book became available')
                    """,
                    (waitlist["id"], waitlist["user_id"], loan["book_id"]),
                )
                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, title, message, notification_type, related_id)
                    VALUES (%s, 'Book available', 'A book from your waitlist is now available.', 'waitlist', %s)
                    """,
                    (waitlist["user_id"], loan["book_id"]),
                )
            connection.commit()
            return loan["book_id"]
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def renew_borrowed_book(user_id, borrowed_id, max_renewals=2):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    book_id,
                    due_date,
                    borrow_date,
                    renewal_count,
                    status,
                    COALESCE(due_date, DATE_ADD(borrow_date, INTERVAL 21 DAY)) AS effective_due_date
                FROM borrowed_books
                WHERE id = %s AND user_id = %s AND status = 'borrowed'
                FOR UPDATE
                """,
                (borrowed_id, user_id),
            )
            loan = cursor.fetchone()
            if not loan:
                return False, "not_found"
            if int(loan.get("renewal_count") or 0) >= max_renewals:
                return False, "limit"
            effective_due_date = loan.get("effective_due_date")
            if effective_due_date and not isinstance(effective_due_date, datetime):
                effective_due_date = datetime.combine(effective_due_date, datetime.max.time())
            if effective_due_date and effective_due_date < datetime.now():
                return False, "overdue"

            cursor.execute(
                """
                UPDATE borrowed_books
                SET due_date = DATE_ADD(COALESCE(due_date, DATE_ADD(borrow_date, INTERVAL 21 DAY)), INTERVAL 7 DAY),
                    renewal_count = renewal_count + 1
                WHERE id = %s
                """,
                (borrowed_id,),
            )
            cursor.execute(
                """
                INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
                VALUES (%s, %s, %s, 'Renewed', 'borrowed', 'Borrowed book renewed by user')
                """,
                (borrowed_id, user_id, loan["book_id"]),
            )
            connection.commit()
            return True, "renewed"
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
            borrowed_books.book_id,
            borrowed_books.borrow_date,
            borrowed_books.return_date,
            borrowed_books.fine_amount,
            borrowed_books.status,
            borrowed_books.payment_status,
            borrowed_books.payment_amount,
            borrowed_books.payment_date,
            borrowed_books.renewal_count,
            books.title,
            books.author,
            books.category,
            books.book_type,
            books.isbn,
            books.publisher,
            books.publication_year,
            books.language,
            books.total_copies,
            books.available_copies,
            books.availability_status,
            books.image,
            COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS due_date
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
                borrowed_books.book_id,
                borrowed_books.borrow_date,
                borrowed_books.return_date,
                borrowed_books.fine_amount,
                borrowed_books.status,
                borrowed_books.payment_status,
                borrowed_books.payment_amount,
                borrowed_books.payment_date,
                borrowed_books.renewal_count,
                books.title,
                books.author,
                books.category,
                books.book_type,
                books.isbn,
                books.publisher,
                books.publication_year,
                books.language,
                books.total_copies,
                books.available_copies,
                books.availability_status,
                books.image,
                COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS due_date
            FROM borrowed_books
            INNER JOIN books ON borrowed_books.book_id = books.id
            WHERE borrowed_books.user_id = %s
              AND borrowed_books.status IN ('borrowed', 'overdue')
        ) AS active_loans
        ORDER BY borrow_date DESC
        """,
        (user_id,),
    )


def get_borrow_record(borrowed_id, user_id=None):
    params = [borrowed_id]
    user_filter = ""
    if user_id is not None:
        user_filter = "AND borrowed_books.user_id = %s"
        params.append(user_id)
    return fetch_one(
        f"""
        SELECT 
            borrowed_books.id,
            borrowed_books.user_id,
            borrowed_books.book_id,
            borrowed_books.borrow_date,
            borrowed_books.return_date,
            borrowed_books.fine_amount,
            borrowed_books.status,
            borrowed_books.payment_status,
            borrowed_books.payment_amount,
            borrowed_books.payment_date,
            borrowed_books.renewal_count,
            books.title,
            books.author,
            books.image,
            books.category,
            books.book_type,
            COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS due_date
        FROM borrowed_books
        INNER JOIN books ON borrowed_books.book_id = books.id
        WHERE borrowed_books.id = %s {user_filter}
        """,
        tuple(params),
    )


def update_borrow_payment_status(borrowed_id, user_id, payment_status):
    execute(
        """
        UPDATE borrowed_books
        SET payment_status = %s,
            payment_date = CASE WHEN %s = 'Paid' THEN NOW() ELSE payment_date END
        WHERE id = %s AND user_id = %s
        """,
        (payment_status, payment_status, borrowed_id, user_id),
    )


def get_dashboard_stats():
    library_summary = fetch_one(
        """
        SELECT COALESCE(ROUND(AVG(rating), 1), 0) AS average_rating,
               COUNT(*) AS total_reviews
        FROM library_reviews
        WHERE status = 'Visible' AND deleted_at IS NULL
        """
    )
    return {
        "books": fetch_one("SELECT COUNT(*) AS total FROM books")["total"],
        "members": fetch_one("SELECT COUNT(*) AS total FROM users")["total"],
        "active_users": fetch_one("SELECT COUNT(*) AS total FROM users WHERE status = 'active'")["total"],
        "borrowed": fetch_one(
            "SELECT COUNT(*) AS total FROM borrowed_books WHERE status IN ('borrowed', 'overdue')"
        )["total"],
        "available": fetch_one("SELECT COUNT(*) AS total FROM books WHERE available = 1")["total"],
        "reserved": fetch_one(
            "SELECT COUNT(*) AS total FROM reservations WHERE status IN ('Pending', 'Approved') AND expiry_date >= NOW()"
        )["total"],
        "purchased": fetch_one("SELECT COUNT(*) AS total FROM orders WHERE status IN ('Paid', 'Processing', 'Completed')")["total"],
        "outstanding_fines": fetch_one(
            "SELECT COALESCE(SUM(total_fine), 0) AS total FROM fine_records WHERE status NOT IN ('Paid', 'Approved')"
        )["total"],
        "average_library_rating": library_summary["average_rating"] if library_summary else 0,
        "library_reviews": library_summary["total_reviews"] if library_summary else 0,
        "book_reviews": fetch_one(
            "SELECT COUNT(*) AS total FROM book_reviews WHERE review_text IS NOT NULL AND status = 'Visible' AND deleted_at IS NULL"
        )["total"],
        "pending_waitlists": fetch_one("SELECT COUNT(*) AS total FROM waitlists WHERE status = 'Active'")["total"],
        "notifications_sent": fetch_one("SELECT COUNT(*) AS total FROM notifications")["total"],
        "security_alerts": fetch_one(
            "SELECT COUNT(*) AS total FROM security_logs WHERE event_type IN ('failed_login', 'suspicious_activity', 'lockout')"
        )["total"],
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


def list_user_profile_updates(user_id):
    return fetch_all(
        """
        SELECT *
        FROM profile_updates
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (user_id,),
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
                SET book_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Out of Stock' END
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
                    ELSE 'Out of Stock'
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
                    ELSE 'Out of Stock'
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
            SET book_status = CASE WHEN stock_quantity > 0 THEN 'Available' ELSE 'Out of Stock' END
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
        SELECT orders.*, books.title, books.author, books.image, books.category,
               purchase_receipts.receipt_number
        FROM orders
        INNER JOIN books ON orders.book_id = books.id
        LEFT JOIN purchase_receipts ON purchase_receipts.order_id = orders.id
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
            cursor.execute("SELECT book_id, quantity, status FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                return False
            cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
            cursor.execute("UPDATE book_purchases SET status = %s WHERE order_id = %s", (status, order_id))
            if status == "Cancelled" and order["status"] != "Cancelled":
                cursor.execute(
                    """
                    UPDATE books
                    SET stock_quantity = stock_quantity + %s,
                        available_copies = stock_quantity + %s,
                        total_copies = GREATEST(total_copies, stock_quantity + %s),
                        available = 1,
                        availability_status = 'Available',
                        book_status = 'Available'
                    WHERE id = %s
                    """,
                    (order["quantity"], order["quantity"], order["quantity"], order["book_id"]),
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
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT book_id, quantity, status FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                return False
            if order["status"] not in {"Cancelled", "Completed", "Paid"}:
                cursor.execute(
                    """
                    UPDATE books
                    SET stock_quantity = stock_quantity + %s,
                        available_copies = stock_quantity + %s,
                        total_copies = GREATEST(total_copies, stock_quantity + %s),
                        available = 1,
                        availability_status = 'Available',
                        book_status = 'Available'
                    WHERE id = %s
                    """,
                    (order["quantity"], order["quantity"], order["quantity"], order["book_id"]),
                )
            cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
            connection.commit()
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def upsert_review(user_id, book_id, review_text, action_type=None):
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
        INSERT INTO book_reviews (user_id, book_id, review_text, action_type, status, deleted_at)
        VALUES (%s, %s, %s, %s, 'Visible', NULL)
        ON DUPLICATE KEY UPDATE
            review_text = VALUES(review_text),
            action_type = COALESCE(VALUES(action_type), action_type),
            status = 'Visible',
            deleted_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, book_id, review_text, action_type),
    )
    return review_id


def delete_review(review_id, user_id=None, is_admin=False):
    review = fetch_one("SELECT user_id, book_id FROM reviews WHERE id = %s", (review_id,))
    book_review = None
    if not review:
        book_review = fetch_one("SELECT user_id, book_id FROM book_reviews WHERE id = %s", (review_id,))
        review = book_review
    if not review:
        return
    if is_admin or review["user_id"] == user_id:
        execute(
            """
            DELETE FROM reviews
            WHERE user_id = %s AND book_id = %s
            """,
            (review["user_id"], review["book_id"]),
        )
        execute(
            """
            UPDATE book_reviews
            SET review_text = NULL,
                status = CASE WHEN rating IS NULL THEN 'Deleted' ELSE status END,
                deleted_at = CASE WHEN rating IS NULL THEN CURRENT_TIMESTAMP ELSE deleted_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND book_id = %s
            """,
            (review["user_id"], review["book_id"]),
        )


def list_book_reviews(book_id):
    return fetch_all(
        """
        SELECT book_reviews.*, users.username, profile_pictures.image_path AS profile_pic_url
        FROM book_reviews
        INNER JOIN users ON book_reviews.user_id = users.id
        LEFT JOIN profile_pictures
            ON profile_pictures.user_id = users.id
           AND profile_pictures.status = 'Active'
        WHERE book_reviews.book_id = %s
          AND book_reviews.review_text IS NOT NULL
          AND book_reviews.status = 'Visible'
          AND book_reviews.deleted_at IS NULL
        ORDER BY book_reviews.is_pinned DESC,
                 COALESCE(book_reviews.updated_at, book_reviews.review_date) DESC
        """,
        (book_id,),
    )


def list_community_reviews(sort="recent", user_id=None):
    order_sql = "like_count DESC, review_date DESC" if sort == "liked" else "review_date DESC"
    return fetch_all(
        f"""
        SELECT book_reviews.*,
               users.username,
               profile_pictures.image_path AS profile_pic_url,
               books.title,
               books.author,
               books.image,
               COALESCE(likes.like_count, 0) AS like_count,
               COALESCE(replies.reply_count, 0) AS reply_count,
               CASE WHEN user_likes.id IS NULL THEN 0 ELSE 1 END AS liked_by_current_user
        FROM book_reviews
        INNER JOIN users ON book_reviews.user_id = users.id
        INNER JOIN books ON book_reviews.book_id = books.id
        LEFT JOIN profile_pictures
            ON profile_pictures.user_id = users.id
           AND profile_pictures.status = 'Active'
        LEFT JOIN (
            SELECT review_id, COUNT(*) AS like_count
            FROM review_likes
            GROUP BY review_id
        ) AS likes ON likes.review_id = book_reviews.id
        LEFT JOIN (
            SELECT review_id, COUNT(*) AS reply_count
            FROM review_replies
            GROUP BY review_id
        ) AS replies ON replies.review_id = book_reviews.id
        LEFT JOIN review_likes AS user_likes
            ON user_likes.review_id = book_reviews.id
           AND user_likes.user_id = %s
        WHERE book_reviews.review_text IS NOT NULL
          AND book_reviews.status = 'Visible'
          AND book_reviews.deleted_at IS NULL
        ORDER BY {order_sql}
        """,
        (user_id or 0,),
    )


def list_review_replies(review_ids):
    if not review_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(review_ids))
    rows = fetch_all(
        f"""
        SELECT review_replies.*, users.username, profile_pictures.image_path AS profile_pic_url
        FROM review_replies
        INNER JOIN users ON review_replies.user_id = users.id
        LEFT JOIN profile_pictures
            ON profile_pictures.user_id = users.id
           AND profile_pictures.status = 'Active'
        WHERE review_replies.review_id IN ({placeholders})
        ORDER BY review_replies.created_at ASC
        """,
        tuple(review_ids),
    )
    grouped = {}
    for row in rows:
        grouped.setdefault(row["review_id"], []).append(row)
    return grouped


def like_review_once(review_id, user_id):
    return execute(
        """
        INSERT IGNORE INTO review_likes (review_id, user_id)
        VALUES (%s, %s)
        """,
        (review_id, user_id),
    )


def create_review_reply(review_id, user_id, reply_text):
    return execute(
        """
        INSERT INTO review_replies (review_id, user_id, reply_text)
        VALUES (%s, %s, %s)
        """,
        (review_id, user_id, reply_text),
    )


def set_book_rating(user_id, book_id, rating, action_type=None):
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
        INSERT INTO book_reviews (user_id, book_id, rating, action_type, status, deleted_at)
        VALUES (%s, %s, %s, %s, 'Visible', NULL)
        ON DUPLICATE KEY UPDATE
            rating = VALUES(rating),
            action_type = COALESCE(VALUES(action_type), action_type),
            status = 'Visible',
            deleted_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, book_id, rating, action_type),
    )
    return rating_id


def get_user_book_rating(user_id, book_id):
    row = fetch_one(
        "SELECT rating FROM ratings WHERE user_id = %s AND book_id = %s",
        (user_id, book_id),
    )
    return row["rating"] if row else 0


def get_library_rating_summary():
    return get_library_review_summary()


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
            book_reviews.action_type,
            book_reviews.status,
            book_reviews.review_date,
            book_reviews.updated_at,
            COALESCE(book_rating.average_rating, 0) AS average_rating,
            COALESCE(book_rating.total_ratings, 0) AS total_ratings
        FROM book_reviews
        INNER JOIN books ON book_reviews.book_id = books.id
        LEFT JOIN (
            SELECT book_id, ROUND(AVG(rating), 1) AS average_rating, COUNT(rating) AS total_ratings
            FROM book_reviews
            WHERE rating IS NOT NULL AND status = 'Visible' AND deleted_at IS NULL
            GROUP BY book_id
        ) AS book_rating ON book_rating.book_id = books.id
        WHERE book_reviews.user_id = %s
          AND book_reviews.deleted_at IS NULL
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


def log_security_event(user_id, email, event_type, ip_address, summary):
    try:
        execute(
            """
            INSERT INTO security_logs (user_id, email, event_type, ip_address, summary)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, email, event_type, ip_address, summary[:255]),
        )
        log_event(user_id, event_type, "security", None, summary)
    except pymysql.MySQLError:
        pass


def get_library_review_summary():
    summary = fetch_one(
        """
        SELECT COALESCE(ROUND(AVG(rating), 1), 0) AS average_rating,
               COUNT(*) AS total_reviews
        FROM library_reviews
        WHERE status = 'Visible' AND deleted_at IS NULL
        """
    )
    distribution = fetch_all(
        """
        SELECT rating, COUNT(*) AS total
        FROM library_reviews
        WHERE status = 'Visible' AND deleted_at IS NULL
        GROUP BY rating
        ORDER BY rating DESC
        """
    )
    featured = fetch_all(
        """
        SELECT library_reviews.*, users.username
        FROM library_reviews
        INNER JOIN users ON library_reviews.user_id = users.id
        WHERE library_reviews.status = 'Visible'
          AND library_reviews.deleted_at IS NULL
          AND library_reviews.is_pinned = 1
        ORDER BY library_reviews.updated_at DESC, library_reviews.created_at DESC
        LIMIT 6
        """
    )
    latest = fetch_all(
        """
        SELECT library_reviews.*, users.username
        FROM library_reviews
        INNER JOIN users ON library_reviews.user_id = users.id
        WHERE library_reviews.status = 'Visible'
          AND library_reviews.deleted_at IS NULL
        ORDER BY COALESCE(library_reviews.updated_at, library_reviews.created_at) DESC
        LIMIT 10
        """
    )
    return {
        "average_rating": summary["average_rating"] if summary else 0,
        "total_reviews": summary["total_reviews"] if summary else 0,
        "distribution": {row["rating"]: row["total"] for row in distribution},
        "featured": featured,
        "latest": latest,
    }


def get_user_library_review(user_id):
    return fetch_one(
        """
        SELECT *
        FROM library_reviews
        WHERE user_id = %s AND deleted_at IS NULL
        """,
        (user_id,),
    )


def upsert_library_review(user_id, rating, review_text):
    review_id = execute(
        """
        INSERT INTO library_reviews (user_id, rating, review_text, status)
        VALUES (%s, %s, %s, 'Visible')
        ON DUPLICATE KEY UPDATE
            rating = VALUES(rating),
            review_text = VALUES(review_text),
            status = 'Visible',
            deleted_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, rating, review_text),
    )
    execute(
        """
        INSERT INTO library_ratings (user_id, rating)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE rating = VALUES(rating), updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, rating),
    )
    log_event(user_id, "library_review_submitted", "library_review", review_id or user_id, "Library review submitted")
    return review_id


def delete_library_review(user_id):
    review = get_user_library_review(user_id)
    execute(
        """
        UPDATE library_reviews
        SET status = 'Deleted',
            deleted_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
        """,
        (user_id,),
    )
    if review:
        log_event(user_id, "library_review_deleted", "library_review", review["id"], "Library review deleted")


def list_admin_library_reviews():
    return fetch_all(
        """
        SELECT library_reviews.*, users.username, users.email
        FROM library_reviews
        INNER JOIN users ON library_reviews.user_id = users.id
        ORDER BY library_reviews.is_pinned DESC,
                 COALESCE(library_reviews.updated_at, library_reviews.created_at) DESC
        """
    )


def list_review_moderation_logs(review_type=None, review_id=None):
    params = []
    filters = []
    if review_type:
        filters.append("review_moderation_logs.review_type = %s")
        params.append(review_type)
    if review_id:
        filters.append("review_moderation_logs.review_id = %s")
        params.append(review_id)
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    return fetch_all(
        f"""
        SELECT review_moderation_logs.*, users.username AS admin_name
        FROM review_moderation_logs
        LEFT JOIN users ON review_moderation_logs.admin_user_id = users.id
        {where_sql}
        ORDER BY review_moderation_logs.created_at DESC
        LIMIT 100
        """,
        tuple(params),
    )


def moderate_library_review(review_id, action, admin_user_id):
    updates = {
        "approve": ("status = 'Visible', deleted_at = NULL", "Approved"),
        "pin": ("is_pinned = 1", "Pinned"),
        "unpin": ("is_pinned = 0", "Unpinned"),
        "hide": ("status = 'Hidden'", "Hidden"),
        "delete": ("status = 'Deleted', deleted_at = CURRENT_TIMESTAMP", "Deleted"),
        "restore": ("status = 'Visible', deleted_at = NULL", "Restored"),
    }
    if action not in updates:
        return False
    update_sql, label = updates[action]
    execute(
        f"""
        UPDATE library_reviews
        SET {update_sql},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (review_id,),
    )
    execute(
        """
        INSERT INTO review_moderation_logs (review_type, review_id, admin_user_id, action, note)
        VALUES ('library', %s, %s, %s, %s)
        """,
        (review_id, admin_user_id, label, f"Library review {label.lower()}"),
    )
    log_event(admin_user_id, "library_review_moderated", "library_review", review_id, f"Library review {label.lower()}")
    return True


def get_book_review_eligibility(user_id, book_id):
    checks = [
        (
            "Borrowed",
            """
            SELECT id FROM borrowed_books
            WHERE user_id = %s AND book_id = %s
            LIMIT 1
            """,
        ),
        (
            "Reserved",
            """
            SELECT id FROM reservations
            WHERE user_id = %s AND book_id = %s
            LIMIT 1
            """,
        ),
        (
            "Purchased",
            """
            SELECT id FROM orders
            WHERE user_id = %s AND book_id = %s
              AND status IN ('Pending', 'Paid', 'Processing', 'Completed')
            LIMIT 1
            """,
        ),
    ]
    for action_type, query in checks:
        if fetch_one(query, (user_id, book_id)):
            return action_type
    return None


def list_admin_book_reviews():
    return fetch_all(
        """
        SELECT book_reviews.*, users.username, users.email, books.title, books.author
        FROM book_reviews
        INNER JOIN users ON book_reviews.user_id = users.id
        INNER JOIN books ON book_reviews.book_id = books.id
        WHERE book_reviews.review_text IS NOT NULL OR book_reviews.rating IS NOT NULL
        ORDER BY book_reviews.is_pinned DESC,
                 COALESCE(book_reviews.updated_at, book_reviews.review_date) DESC
        """
    )


def moderate_book_review(review_id, action, admin_user_id):
    updates = {
        "approve": ("status = 'Visible', deleted_at = NULL", "Approved"),
        "pin": ("is_pinned = 1", "Pinned"),
        "unpin": ("is_pinned = 0", "Unpinned"),
        "hide": ("status = 'Hidden'", "Hidden"),
        "delete": ("status = 'Deleted', deleted_at = CURRENT_TIMESTAMP", "Deleted"),
        "restore": ("status = 'Visible', deleted_at = NULL", "Restored"),
    }
    if action not in updates:
        return False
    update_sql, label = updates[action]
    execute(
        f"""
        UPDATE book_reviews
        SET {update_sql},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (review_id,),
    )
    execute(
        """
        INSERT INTO review_moderation_logs (review_type, review_id, admin_user_id, action, note)
        VALUES ('book', %s, %s, %s, %s)
        """,
        (review_id, admin_user_id, label, f"Book review {label.lower()}"),
    )
    log_event(admin_user_id, "book_review_moderated", "book_review", review_id, f"Book review {label.lower()}")
    return True


def get_book_review_statistics():
    top_rated = fetch_all(
        """
        SELECT books.id, books.title, books.author,
               ROUND(AVG(book_reviews.rating), 1) AS average_rating,
               COUNT(book_reviews.rating) AS total_ratings
        FROM books
        INNER JOIN book_reviews ON book_reviews.book_id = books.id
        WHERE book_reviews.rating IS NOT NULL
          AND book_reviews.status = 'Visible'
          AND book_reviews.deleted_at IS NULL
        GROUP BY books.id, books.title, books.author
        ORDER BY average_rating DESC, total_ratings DESC
        LIMIT 5
        """
    )
    most_reviewed = fetch_all(
        """
        SELECT books.id, books.title, books.author,
               COUNT(book_reviews.review_text) AS review_count
        FROM books
        INNER JOIN book_reviews ON book_reviews.book_id = books.id
        WHERE book_reviews.review_text IS NOT NULL
          AND book_reviews.status = 'Visible'
          AND book_reviews.deleted_at IS NULL
        GROUP BY books.id, books.title, books.author
        ORDER BY review_count DESC
        LIMIT 5
        """
    )
    summary = fetch_one(
        """
        SELECT COALESCE(ROUND(AVG(rating), 1), 0) AS average_book_rating,
               COUNT(rating) AS total_ratings,
               COUNT(review_text) AS total_reviews
        FROM book_reviews
        WHERE status = 'Visible' AND deleted_at IS NULL
        """
    )
    return {"top_rated": top_rated, "most_reviewed": most_reviewed, "summary": summary}


def get_active_profile_picture(user_id):
    return fetch_one(
        """
        SELECT *
        FROM profile_pictures
        WHERE user_id = %s AND status = 'Active'
        ORDER BY modified_date DESC, upload_date DESC
        LIMIT 1
        """,
        (user_id,),
    )


def save_profile_picture(user_id, image_path, actor_user_id=None):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE profile_pictures
                SET status = 'Removed',
                    removed_at = NOW(),
                    removed_by = %s,
                    modified_date = NOW()
                WHERE user_id = %s AND status = 'Active'
                """,
                (actor_user_id or user_id, user_id),
            )
            cursor.execute(
                """
                INSERT INTO profile_pictures (user_id, image_path, status, modified_date)
                VALUES (%s, %s, 'Active', NOW())
                """,
                (user_id, image_path),
            )
            picture_id = cursor.lastrowid
            cursor.execute(
                "UPDATE users SET profile_pic_url = %s WHERE id = %s",
                (image_path, user_id),
            )
            cursor.execute(
                """
                INSERT INTO profile_picture_history (user_id, picture_id, action, image_path, admin_user_id)
                VALUES (%s, %s, 'Uploaded', %s, %s)
                """,
                (user_id, picture_id, image_path, actor_user_id if actor_user_id != user_id else None),
            )
            connection.commit()
            log_event(actor_user_id or user_id, "profile_picture_change", "profile_picture", picture_id, "Profile picture updated")
            return picture_id
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def remove_profile_picture(user_id, actor_user_id=None):
    picture = get_active_profile_picture(user_id)
    if not picture:
        return False
    execute(
        """
        UPDATE profile_pictures
        SET status = 'Removed',
            removed_at = NOW(),
            removed_by = %s,
            modified_date = NOW()
        WHERE id = %s
        """,
        (actor_user_id or user_id, picture["id"]),
    )
    execute("UPDATE users SET profile_pic_url = NULL WHERE id = %s", (user_id,))
    execute(
        """
        INSERT INTO profile_picture_history (user_id, picture_id, action, image_path, admin_user_id)
        VALUES (%s, %s, 'Removed', %s, %s)
        """,
        (user_id, picture["id"], picture["image_path"], actor_user_id if actor_user_id != user_id else None),
    )
    log_event(actor_user_id or user_id, "profile_picture_removed", "profile_picture", picture["id"], "Profile picture removed")
    return True


def update_profile_picture_position(user_id, object_position):
    allowed_positions = {
        "center center",
        "top center",
        "bottom center",
        "center left",
        "center right",
        "top left",
        "top right",
        "bottom left",
        "bottom right",
    }
    if object_position not in allowed_positions:
        object_position = "center center"
    picture = get_active_profile_picture(user_id)
    if not picture:
        return False
    execute(
        """
        UPDATE profile_pictures
        SET object_position = %s,
            modified_date = NOW()
        WHERE id = %s
        """,
        (object_position, picture["id"]),
    )
    execute(
        """
        INSERT INTO profile_picture_history (user_id, picture_id, action, image_path)
        VALUES (%s, %s, 'Adjusted', %s)
        """,
        (user_id, picture["id"], picture["image_path"]),
    )
    log_event(user_id, "profile_picture_adjusted", "profile_picture", picture["id"], "Profile picture crop position adjusted")
    return True


def restore_profile_picture(picture_id, admin_user_id):
    picture = fetch_one("SELECT * FROM profile_pictures WHERE id = %s", (picture_id,))
    if not picture:
        return False
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE profile_pictures
                SET status = 'Removed',
                    removed_at = NOW(),
                    removed_by = %s,
                    modified_date = NOW()
                WHERE user_id = %s AND status = 'Active'
                """,
                (admin_user_id, picture["user_id"]),
            )
            cursor.execute(
                """
                UPDATE profile_pictures
                SET status = 'Active',
                    removed_at = NULL,
                    removed_by = NULL,
                    modified_date = NOW()
                WHERE id = %s
                """,
                (picture_id,),
            )
            cursor.execute(
                "UPDATE users SET profile_pic_url = %s WHERE id = %s",
                (picture["image_path"], picture["user_id"]),
            )
            cursor.execute(
                """
                INSERT INTO profile_picture_history (user_id, picture_id, action, image_path, admin_user_id)
                VALUES (%s, %s, 'Restored', %s, %s)
                """,
                (picture["user_id"], picture_id, picture["image_path"], admin_user_id),
            )
            connection.commit()
            log_event(admin_user_id, "profile_picture_restored", "profile_picture", picture_id, "Profile picture restored")
            return True
    except pymysql.MySQLError:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_profile_picture_history(user_id):
    return fetch_all(
        """
        SELECT profile_picture_history.*, users.username AS admin_name
        FROM profile_picture_history
        LEFT JOIN users ON profile_picture_history.admin_user_id = users.id
        WHERE profile_picture_history.user_id = %s
        ORDER BY profile_picture_history.created_at DESC
        """,
        (user_id,),
    )


def list_admin_profile_pictures():
    return fetch_all(
        """
        SELECT profile_pictures.*, users.username, users.email
        FROM profile_pictures
        INNER JOIN users ON profile_pictures.user_id = users.id
        ORDER BY profile_pictures.modified_date DESC, profile_pictures.upload_date DESC
        """
    )


def join_waitlist(user_id, book_id):
    book = get_book(book_id)
    if not book:
        return None
    waitlist_id = execute(
        """
        INSERT INTO waitlists (user_id, book_id, status, admin_note)
        VALUES (%s, %s, 'Active', 'Joined by user')
        ON DUPLICATE KEY UPDATE
            status = 'Active',
            notification_date = NULL,
            admin_note = 'Rejoined by user'
        """,
        (user_id, book_id),
    )
    row = fetch_one("SELECT id FROM waitlists WHERE user_id = %s AND book_id = %s", (user_id, book_id))
    waitlist_id = waitlist_id or row["id"]
    execute(
        """
        INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
        VALUES (%s, %s, %s, 'Joined', 'User joined waitlist')
        """,
        (waitlist_id, user_id, book_id),
    )
    log_event(user_id, "waitlist_join", "book", book_id, "User joined waitlist")
    return waitlist_id


def leave_waitlist(user_id, waitlist_id):
    waitlist = fetch_one(
        "SELECT * FROM waitlists WHERE id = %s AND user_id = %s",
        (waitlist_id, user_id),
    )
    if not waitlist:
        return False
    execute(
        "UPDATE waitlists SET status = 'Left', admin_note = 'Left by user' WHERE id = %s",
        (waitlist_id,),
    )
    execute(
        """
        INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
        VALUES (%s, %s, %s, 'Left', 'User left waitlist')
        """,
        (waitlist_id, user_id, waitlist["book_id"]),
    )
    log_event(user_id, "waitlist_leave", "book", waitlist["book_id"], "User left waitlist")
    return True


def list_user_waitlists(user_id):
    return fetch_all(
        """
        SELECT waitlists.*, books.title, books.author, books.image, books.availability_status, books.stock_quantity
        FROM waitlists
        INNER JOIN books ON waitlists.book_id = books.id
        WHERE waitlists.user_id = %s AND waitlists.status IN ('Active', 'Notified')
        ORDER BY waitlists.join_date DESC
        """,
        (user_id,),
    )


def list_admin_waitlists():
    return fetch_all(
        """
        SELECT waitlists.*, users.username, users.email, books.title, books.author
        FROM waitlists
        INNER JOIN users ON waitlists.user_id = users.id
        INNER JOIN books ON waitlists.book_id = books.id
        ORDER BY waitlists.join_date DESC
        """
    )


def get_waitlist(waitlist_id):
    return fetch_one(
        """
        SELECT waitlists.*, users.username, users.email, books.title, books.author
        FROM waitlists
        INNER JOIN users ON waitlists.user_id = users.id
        INNER JOIN books ON waitlists.book_id = books.id
        WHERE waitlists.id = %s
        """,
        (waitlist_id,),
    )


def update_waitlist_admin(waitlist_id, status, note, admin_user_id):
    waitlist = get_waitlist(waitlist_id)
    if not waitlist:
        return False
    execute(
        "UPDATE waitlists SET status = %s, admin_note = %s WHERE id = %s",
        (status, note, waitlist_id),
    )
    execute(
        """
        INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (waitlist_id, waitlist["user_id"], waitlist["book_id"], status, note),
    )
    log_event(admin_user_id, "waitlist_updated", "waitlist", waitlist_id, "Waitlist record updated")
    return True


def delete_waitlist_admin(waitlist_id, admin_user_id):
    waitlist = get_waitlist(waitlist_id)
    if not waitlist:
        return False
    execute(
        """
        INSERT INTO waitlist_history (waitlist_id, user_id, book_id, action, note)
        VALUES (%s, %s, %s, 'Removed', 'Removed by admin')
        """,
        (waitlist_id, waitlist["user_id"], waitlist["book_id"]),
    )
    execute("DELETE FROM waitlists WHERE id = %s", (waitlist_id,))
    log_event(admin_user_id, "waitlist_removed", "waitlist", waitlist_id, "Waitlist record removed")
    return True


def mark_notification_read(user_id, notification_id):
    execute(
        "UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s",
        (notification_id, user_id),
    )


def mark_all_notifications_read(user_id):
    execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (user_id,))


def delete_notification(user_id, notification_id):
    execute("DELETE FROM notifications WHERE id = %s AND user_id = %s", (notification_id, user_id))


def create_notification(user_id, title, message, notification_type="manual", related_id=None):
    notification_id = execute(
        """
        INSERT INTO notifications (user_id, title, message, notification_type, related_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, title, message, notification_type, related_id),
    )
    log_event(user_id, "notification_sent", "notification", notification_id, title)
    return notification_id


def list_admin_notifications():
    return fetch_all(
        """
        SELECT notifications.*, users.username, users.email
        FROM notifications
        INNER JOIN users ON notifications.user_id = users.id
        ORDER BY notifications.created_at DESC
        LIMIT 200
        """
    )


def delete_notification_admin(notification_id, admin_user_id):
    execute("DELETE FROM notifications WHERE id = %s", (notification_id,))
    log_event(admin_user_id, "notification_deleted", "notification", notification_id, "Notification deleted")


def list_activity_logs(search=None, event_type=None, limit=200):
    params = []
    filters = []
    if search:
        filters.append("(activity_logs.summary LIKE %s OR users.username LIKE %s OR activity_logs.event_type LIKE %s)")
        value = f"%{search}%"
        params.extend([value, value, value])
    if event_type:
        filters.append("activity_logs.event_type = %s")
        params.append(event_type)
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    params.append(limit)
    return fetch_all(
        f"""
        SELECT activity_logs.*, users.username, users.email
        FROM activity_logs
        LEFT JOIN users ON activity_logs.actor_user_id = users.id
        {where_sql}
        ORDER BY activity_logs.created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )


def list_security_logs(search=None, limit=100):
    params = []
    where_sql = ""
    if search:
        where_sql = "WHERE email LIKE %s OR summary LIKE %s OR event_type LIKE %s"
        value = f"%{search}%"
        params.extend([value, value, value])
    params.append(limit)
    return fetch_all(
        f"""
        SELECT security_logs.*, users.username
        FROM security_logs
        LEFT JOIN users ON security_logs.user_id = users.id
        {where_sql}
        ORDER BY security_logs.created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )


def list_admin_borrows(search=None):
    params = []
    where_sql = ""
    if search:
        where_sql = "WHERE users.username LIKE %s OR users.email LIKE %s OR books.title LIKE %s OR borrowed_books.status LIKE %s"
        value = f"%{search}%"
        params.extend([value, value, value, value])
    return fetch_all(
        f"""
        SELECT borrowed_books.*,
               COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS display_due_date,
               users.username,
               users.email,
               books.title,
               books.author
        FROM borrowed_books
        INNER JOIN users ON borrowed_books.user_id = users.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        {where_sql}
        ORDER BY borrowed_books.borrow_date DESC
        """,
        tuple(params),
    )


def get_borrow_record(borrowed_id, user_id=None):
    params = [borrowed_id]
    user_filter = ""
    if user_id is not None:
        user_filter = "AND borrowed_books.user_id = %s"
        params.append(user_id)
    return fetch_one(
        f"""
        SELECT borrowed_books.*,
               users.username,
               users.email,
               books.title,
               books.author,
               books.image,
               books.category,
               books.book_type,
               COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS display_due_date
        FROM borrowed_books
        INNER JOIN users ON borrowed_books.user_id = users.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        WHERE borrowed_books.id = %s {user_filter}
        """,
        tuple(params),
    )


def update_borrow_record(borrowed_id, due_date, status, fine_amount, admin_user_id):
    borrow = get_borrow_record(borrowed_id)
    if not borrow:
        return False
    execute(
        """
        UPDATE borrowed_books
        SET due_date = %s,
            status = %s,
            fine_amount = %s,
            return_date = CASE WHEN %s = 'returned' AND return_date IS NULL THEN NOW() ELSE return_date END
        WHERE id = %s
        """,
        (due_date, status, fine_amount, status, borrowed_id),
    )
    execute(
        """
        INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
        VALUES (%s, %s, %s, 'Updated', %s, 'Borrow record updated by admin')
        """,
        (borrowed_id, borrow["user_id"], borrow["book_id"], status),
    )
    log_event(admin_user_id, "borrow_updated", "borrowed_book", borrowed_id, "Borrow record updated")
    return True


def force_return_borrow_record(borrowed_id, admin_user_id):
    borrow = get_borrow_record(borrowed_id)
    if not borrow:
        return False
    execute(
        """
        UPDATE borrowed_books
        SET status = 'returned',
            return_date = COALESCE(return_date, NOW())
        WHERE id = %s
        """,
        (borrowed_id,),
    )
    execute(
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
        (borrow["book_id"],),
    )
    execute(
        """
        INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
        VALUES (%s, %s, %s, 'Force Returned', 'returned', 'Force returned by admin')
        """,
        (borrowed_id, borrow["user_id"], borrow["book_id"]),
    )
    log_event(admin_user_id, "borrow_force_returned", "borrowed_book", borrowed_id, "Borrow record force returned")
    return True


def delete_borrow_record(borrowed_id, admin_user_id):
    borrow = get_borrow_record(borrowed_id)
    if not borrow:
        return False
    execute(
        """
        INSERT INTO borrow_history (borrowed_id, user_id, book_id, action, status, note)
        VALUES (%s, %s, %s, 'Deleted', %s, 'Borrow record deleted by admin')
        """,
        (borrowed_id, borrow["user_id"], borrow["book_id"], borrow["status"]),
    )
    execute("DELETE FROM borrowed_books WHERE id = %s", (borrowed_id,))
    log_event(admin_user_id, "borrow_deleted", "borrowed_book", borrowed_id, "Borrow record deleted")
    return True


def list_borrow_timeline(borrowed_id):
    return fetch_all(
        """
        SELECT *
        FROM borrow_history
        WHERE borrowed_id = %s
        ORDER BY created_at DESC
        """,
        (borrowed_id,),
    )


def list_admin_fine_records():
    refresh_fine_records()
    return fetch_all(
        """
        SELECT fine_records.*,
               users.username,
               users.email,
               books.title,
               books.author
        FROM fine_records
        INNER JOIN users ON fine_records.user_id = users.id
        INNER JOIN borrowed_books ON fine_records.borrowed_id = borrowed_books.id
        INNER JOIN books ON borrowed_books.book_id = books.id
        ORDER BY fine_records.calculated_at DESC
        """
    )


def update_fine_record(fine_id, amount, status, reason, admin_user_id):
    execute(
        """
        UPDATE fine_records
        SET total_fine = %s,
            status = %s,
            reason = %s
        WHERE id = %s
        """,
        (amount, status, reason, fine_id),
    )
    log_event(admin_user_id, "fine_updated", "fine_record", fine_id, "Fine record updated")


def update_fine_record_status(fine_id, status, admin_user_id):
    execute("UPDATE fine_records SET status = %s WHERE id = %s", (status, fine_id))
    log_event(admin_user_id, "fine_status_updated", "fine_record", fine_id, f"Fine status changed to {status}")


def delete_fine_record(fine_id, admin_user_id):
    execute("DELETE FROM fine_records WHERE id = %s", (fine_id,))
    log_event(admin_user_id, "fine_deleted", "fine_record", fine_id, "Fine record deleted")


def create_backup_record(backup_type, file_path, admin_user_id):
    backup_id = execute(
        """
        INSERT INTO backup_history (backup_type, file_path, admin_user_id)
        VALUES (%s, %s, %s)
        """,
        (backup_type, file_path, admin_user_id),
    )
    log_event(admin_user_id, "backup_created", "backup", backup_id, f"{backup_type} backup created")
    return backup_id


def list_backup_history():
    return fetch_all(
        """
        SELECT backup_history.*, users.username AS admin_name
        FROM backup_history
        LEFT JOIN users ON backup_history.admin_user_id = users.id
        ORDER BY backup_history.created_at DESC
        """
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
               COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS due_date,
               DATEDIFF(COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)), CURDATE()) AS days_until_due
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
                   DATEDIFF(COALESCE(return_date, NOW()), COALESCE(due_date, DATE_ADD(borrow_date, INTERVAL 21 DAY))),
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
               COALESCE(borrowed_books.due_date, DATE_ADD(borrowed_books.borrow_date, INTERVAL 21 DAY)) AS due_date,
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

