# 🚀 Bookverse Library Management System - Setup Guide

## ✅ Completed So Far
- ✅ Cloned Anim branch successfully
- ✅ Created Python virtual environment
- ✅ Installed all dependencies (Flask, PyMySQL, Flask-WTF, Cryptography)

## 📋 Next Steps: MySQL Setup

### Current Configuration
- **Database Name**: `class_db`
- **MySQL User**: `root`
- **MySQL Password**: `AnimShr@11softw@ricA` (from config.py)
- **MySQL Port**: `3306`
- **Your SQL Password**: `@A2n0s6b2` (provided)

---

## 🔧 Setup Steps in SQL Workbench

### Step 1: Open SQL Workbench
1. Launch **MySQL Workbench**
2. Create a new connection or use existing with:
   - **Host**: localhost
   - **Port**: 3306
   - **Username**: root
   - **Password**: (Use the one set during MySQL installation)

### Step 2: Create Database (Execute in SQL Workbench Query)
```sql
-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS class_db;

-- Use the database
USE class_db;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skills table
CREATE TABLE IF NOT EXISTS skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    proficiency_level VARCHAR(50) NOT NULL,
    CONSTRAINT fk_skills_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);
```

### Step 3: Verify Connection
```sql
SELECT * FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'class_db';
```

---

## 🚀 Running the Application

### From Terminal (in the project folder):
```bash
# Navigate to project
cd c:\Users\97798\OneDrive\Desktop\AI39A_Group8_Anim_Clone

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run the app
python run.py
```

### From VS Code:
1. Open the folder: `c:\Users\97798\OneDrive\Desktop\AI39A_Group8_Anim_Clone`
2. Select Python interpreter from `.\venv\Scripts\python.exe`
3. Press **F5** or Go to Run → Start Debugging
4. App runs at: **http://127.0.0.1:5000/**

---

## 🌐 Access Points

**Login Page**: http://127.0.0.1:5000/
- Register, Login, Home, Books, Profile, Services, Contact, About

---

## ⚠️ Important Notes

1. **MySQL Must Be Running** before starting the Flask app
2. **Port 5000** must be available for Flask
3. The app will **auto-create tables** on first run if database exists
4. **This clone is completely separate** from your other project

---

## 🔐 Password Change (If Needed)

If you want to use your password `@A2n0s6b2` instead of `AnimShr@11softw@ricA`:

Edit `config.py` and change:
```python
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "YOUR_NEW_PASSWORD_HERE")
```

Then update MySQL root password in your database.

---

## ✅ Verification Checklist

- [ ] MySQL is running
- [ ] Database `class_db` created
- [ ] Tables (users, skills) created
- [ ] Virtual environment activated
- [ ] Dependencies installed
- [ ] Run `python run.py` successfully
- [ ] App accessible at http://127.0.0.1:5000/

