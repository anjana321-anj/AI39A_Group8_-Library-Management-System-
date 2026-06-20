import sys
import pymysql
import config
from app import database

def main():
    conn = None
    try:
        print("Connecting to database...")
        conn = pymysql.connect(**config.DATABASE_CONFIG)
        with conn.cursor() as cursor:
            # 1. Create base tables
            print("Ensuring users table...")
            database._ensure_users_table(cursor)
            
            print("Ensuring books table...")
            database._ensure_books_table(cursor)
            
            # 2. CRITICAL: Create borrowed_books first as it is a parent table
            print("Ensuring borrowed_books table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS borrowed_books (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    book_id INT NOT NULL,
                    borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    due_date DATETIME NOT NULL,
                    return_date DATETIME NULL,
                    status VARCHAR(30) NOT NULL DEFAULT 'Borrowed',
                    CONSTRAINT fk_borrowed_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT fk_borrowed_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            """)
            
            # 3. Now create the dependent feature tables
            print("Ensuring all other feature tables...")
            database._ensure_feature_tables(cursor)
            
            conn.commit()
            print("Database initialization complete.")
    except Exception as exc:
        if conn: conn.rollback()
        print("Error while initializing database:", exc)
        sys.exit(1)
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    main()