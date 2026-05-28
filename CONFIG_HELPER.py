"""
📋 MySQL Configuration Helper

Follow these steps to get the app running:
"""

# OPTION 1: Use your existing MySQL password
# ============================================
# If you already have MySQL set up with password @A2n0s6b2:
# 
# 1. Edit config.py and change:
#    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "@A2n0s6b2")
#
# 2. Change MySQL_USER if not root:
#    MYSQL_USER = os.getenv("MYSQL_USER", "your_username")


# OPTION 2: Find your current MySQL root password
# ================================================
# If you installed MySQL recently and don't remember the password:
#
# a) Open MySQL Workbench
# b) Try connecting with:
#    - Username: root
#    - Password: (leave blank, or try common defaults like "root", "password", "mysql")
#    - If successful, note that password
#
# c) Edit config.py to use the correct password


# OPTION 3: Reset MySQL root password (Windows)
# =============================================
# If you've forgotten the root password completely:
#
# 1. Stop MySQL Service:
#    - Press Windows + R
#    - Type: services.msc
#    - Find "MySQL" service and Stop it
#
# 2. In PowerShell (Run as Admin), start MySQL without grant tables:
#    mysqld --skip-grant-tables
#
# 3. In another PowerShell window, connect without password:
#    mysql -u root
#
# 4. Reset the password:
#    FLUSH PRIVILEGES;
#    SET PASSWORD FOR 'root'@'localhost' = PASSWORD('@A2n0s6b2');
#    EXIT;
#
# 5. Restart MySQL normally


# OPTION 4: Create a new database user
# ====================================
# Instead of using root, create a dedicated user for this app:
#
# In MySQL Workbench, execute:
# '''sql
# CREATE USER 'bookverse'@'localhost' IDENTIFIED BY '@A2n0s6b2';
# GRANT ALL PRIVILEGES ON class_db.* TO 'bookverse'@'localhost';
# FLUSH PRIVILEGES;
# '''
#
# Then edit config.py:
# MYSQL_USER = os.getenv("MYSQL_USER", "bookverse")
# MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "@A2n0s6b2")


# OPTION 5: Check if MySQL is running
# =====================================
# In PowerShell:
# Get-Service | Where-Object {$_.Name -like '*MySQL*'} | Select-Object Status, Name
#
# Or in Services.msc to see MySQL status


print(__doc__)
