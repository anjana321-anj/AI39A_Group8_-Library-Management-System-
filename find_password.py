#!/usr/bin/env python3
"""
🔑 MySQL Password Finder - Tries common credentials
"""

import pymysql
import sys

print("\n" + "="*60)
print("🔑 MySQL Credentials Finder")
print("="*60)

# List of common passwords to try
passwords_to_try = [
    "@A2n0s6b2",                    # User provided password
    "AnimShr@11softw@ricA",         # Default in config.py
    "",                              # Empty password
    "root",                          # Common default
    "password",                      # Common default
    "mysql",                         # Common default
    "12345",                         # Common default
    "admin",                         # Common default
]

print("\nAttempting to connect to MySQL with different credentials...")
print("Host: localhost | User: root | Port: 3306\n")

for idx, password in enumerate(passwords_to_try, 1):
    pwd_display = password if password else "[EMPTY]"
    print(f"Attempt {idx}: Password = {pwd_display}...", end=" ")
    
    try:
        connection = pymysql.connect(
            host="localhost",
            user="root",
            password=password,
            port=3306,
        )
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        print(f"✅ SUCCESS!")
        print(f"\n{'='*60}")
        print(f"✅ FOUND WORKING PASSWORD: '{password}'")
        print(f"{'='*60}")
        print(f"\nMySQL Version: {version[0]}\n")
        
        print("📝 Update config.py with this line:")
        print(f'   MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "{password}")')
        
        print("\n🚀 Then run:")
        print("   python test_database.py")
        print("   python run.py\n")
        
        cursor.close()
        connection.close()
        sys.exit(0)
        
    except pymysql.MySQLError as e:
        if "1045" in str(e) or "Access denied" in str(e):
            print("❌ Invalid password")
        else:
            print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n" + "="*60)
print("❌ Could not find working password!")
print("="*60)
print("\n📋 Manual Solution:")
print("1. Open MySQL Workbench")
print("2. Create connection to localhost:3306 with root user")
print("3. Check what password works")
print("4. Update config.py MYSQL_PASSWORD line")
print("5. Run: python test_database.py\n")
