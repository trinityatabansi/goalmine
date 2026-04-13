import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

def get_connection():
    url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
    if url:
        parsed = urlparse(url)
        return mysql.connector.connect(
            host=parsed.hostname,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/"),
            port=parsed.port or 3306
        )
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "goalmine"),
        port=int(os.getenv("DB_PORT") or 3306)
    )

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255),
            google_id VARCHAR(100),
            coin_balance INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            goal_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            goal_id INT NOT NULL,
            week_number INT NOT NULL,
            step_text TEXT NOT NULL,
            is_completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS affirmations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            text TEXT NOT NULL,
            category VARCHAR(50) DEFAULT 'general'
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Tables created.")
