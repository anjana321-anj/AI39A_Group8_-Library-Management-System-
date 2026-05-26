import pymysql

import config


def initialize_mysql_database():
    """
    Initialize the configured MySQL database and required tables for the project.
    """
    connection = None
    cursor = None
    database_name = config.MYSQL_DATABASE or "class_db"

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
    except pymysql.MySQLError as error:
        print(f"MySQL connection test failed: {error}")
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
