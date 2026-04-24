import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def init_db():
    host = os.getenv('MYSQL_HOST')
    user = os.getenv('MYSQL_USER')
    password = os.getenv('MYSQL_PASSWORD')
    database = os.getenv('MYSQL_DATABASE')
    port = int(os.getenv('MYSQL_PORT', 3306))

    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            port=port,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
            cursor.execute(f"USE {database}")
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT,
                    role ENUM('user', 'model'),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            
        connection.commit()
        print("Database and tables initialized successfully.")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    init_db()
