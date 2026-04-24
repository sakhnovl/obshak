import os

import pymysql
from dotenv import load_dotenv

load_dotenv()


def ensure_messages_chat_id(cursor):
    cursor.execute("SHOW COLUMNS FROM messages LIKE 'chat_id'")
    column = cursor.fetchone()
    if column:
        return

    cursor.execute("ALTER TABLE messages ADD COLUMN chat_id BIGINT NULL AFTER id")
    cursor.execute("UPDATE messages SET chat_id = user_id WHERE chat_id IS NULL")
    cursor.execute("ALTER TABLE messages MODIFY chat_id BIGINT NOT NULL")


def ensure_messages_index(cursor):
    cursor.execute("SHOW INDEX FROM messages WHERE Key_name = 'idx_messages_chat_user_id'")
    index_row = cursor.fetchone()
    if index_row:
        return

    cursor.execute(
        """
        CREATE INDEX idx_messages_chat_user_id
        ON messages (chat_id, user_id, id)
        """
    )


def create_table_if_missing(cursor, table_name, create_sql):
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    existing_table = cursor.fetchone()
    if existing_table:
        return

    cursor.execute(create_sql)


def init_db():
    host = os.getenv("MYSQL_HOST")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQL_DATABASE")
    port = int(os.getenv("MYSQL_PORT", 3306))

    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            port=port,
            cursorclass=pymysql.cursors.DictCursor,
        )

        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
            cursor.execute(f"USE {database}")

            create_table_if_missing(
                cursor,
                "users",
                """
                CREATE TABLE users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            )

            create_table_if_missing(
                cursor,
                "messages",
                """
                CREATE TABLE messages (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    role ENUM('user', 'model'),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
                """,
            )

            ensure_messages_chat_id(cursor)
            ensure_messages_index(cursor)

        connection.commit()
        print("Database and tables initialized successfully.")

    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if "connection" in locals():
            connection.close()


if __name__ == "__main__":
    init_db()
