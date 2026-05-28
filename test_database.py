#!/usr/bin/env python3
"""
Database Connection Test Script
Tests MySQL connectivity and initializes the database for Bookverse App
"""

import sys
import pymysql

# Import configuration
try:
    import config
except ImportError:
    print("❌ ERROR: config.py not found. Make sure you're in the project root.")
    sys.exit(1)

def test_mysql_connection():
    """Test if MySQL is accessible"""
    print("\n🔍 Testing MySQL Connection...")
    print(f"   Host: {config.MYSQL_HOST}")
    print(f"   User: {config.MYSQL_USER}")
    print(f"   Port: {config.MYSQL_PORT}")
    
    try:
        connection = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
        )
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"✅ Connected! MySQL Version: {version[0]}")
        cursor.close()
        connection.close()
        return True
    except pymysql.MySQLError as e:
        print(f"❌ MySQL Connection Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False

def initialize_database():
    """Initialize database and tables"""
    print("\n📦 Initializing Database...")
    
    from app.database import initialize_mysql_database
    
    result = initialize_mysql_database()
    
    if result:
        print("✅ Database initialized successfully!")
        return True
    else:
        print("❌ Failed to initialize database")
        return False

def verify_tables():
    """Verify that required tables exist"""
    print("\n🔎 Verifying Tables...")
    
    try:
        connection = pymysql.connect(**config.DATABASE_CONFIG)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = %s
        """, (config.MYSQL_DATABASE,))
        
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"   Found tables: {', '.join(table_names)}")
        
        required_tables = ['users', 'skills']
        missing = [t for t in required_tables if t not in table_names]
        
        if missing:
            print(f"❌ Missing tables: {', '.join(missing)}")
            cursor.close()
            connection.close()
            return False
        else:
            print("✅ All required tables exist!")
            cursor.close()
            connection.close()
            return True
            
    except pymysql.MySQLError as e:
        print(f"❌ Error checking tables: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🚀 Bookverse - Database Setup Verification")
    print("="*60)
    
    # Step 1: Test Connection
    if not test_mysql_connection():
        print("\n⚠️  Cannot connect to MySQL. Please ensure:")
        print("   1. MySQL Server is running")
        print("   2. Check your MySQL credentials in config.py")
        print("   3. MySQL is accessible on port 3306")
        sys.exit(1)
    
    # Step 2: Initialize Database
    if not initialize_database():
        print("\n❌ Database initialization failed!")
        sys.exit(1)
    
    # Step 3: Verify Tables
    if not verify_tables():
        print("\n❌ Table verification failed!")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✅ ALL CHECKS PASSED! Ready to run the app.")
    print("   Command: python run.py")
    print("   Access: http://127.0.0.1:5000/")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
