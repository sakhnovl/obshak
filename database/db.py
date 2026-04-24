import os
import aiomysql
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None
        self.host = os.getenv('MYSQL_HOST')
        self.port = int(os.getenv('MYSQL_PORT', 3306))
        self.user = os.getenv('MYSQL_USER')
        self.password = os.getenv('MYSQL_PASSWORD')
        self.database = os.getenv('MYSQL_DATABASE')

    async def connect(self):
        if not self.pool:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                minsize=5,
                maxsize=20
            )
            print("Database connection pool created.")

    async def init_db(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT,
                        role VARCHAR(50),
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS gemini_keys (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        api_key VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS gemini_models (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        model_name VARCHAR(100) NOT NULL,
                        priority INT DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("Database tables initialized.")

    async def get_active_gemini_keys(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT api_key FROM gemini_keys WHERE is_active = TRUE")
                return [row[0] for row in await cur.fetchall()]

    async def get_active_gemini_models(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT model_name FROM gemini_models WHERE is_active = TRUE ORDER BY priority DESC")
                rows = await cur.fetchall()
                return [row["model_name"] for row in rows]

    async def add_gemini_key(self, api_key):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO gemini_keys (api_key) VALUES (%s)", (api_key,))
                return cur.lastrowid

    async def list_gemini_keys(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, api_key FROM gemini_keys")
                return await cur.fetchall()

    async def delete_gemini_key(self, key_id):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM gemini_keys WHERE id = %s", (key_id,))
                return cur.rowcount

    async def add_gemini_model(self, model_name, priority=0):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO gemini_models (model_name, priority) VALUES (%s, %s)", (model_name, priority))
                return cur.lastrowid

    async def list_gemini_models(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, model_name, priority FROM gemini_models ORDER BY priority DESC")
                return await cur.fetchall()

    async def delete_gemini_model(self, model_id):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM gemini_models WHERE id = %s", (model_id,))
                return cur.rowcount

    async def disconnect(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            print("Database connection pool closed.")

    async def ensure_user_exists(self, user_id, username, first_name):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (user_id, username, first_name)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        username = VALUES(username),
                        first_name = VALUES(first_name)
                    """,
                    (user_id, username, first_name)
                )

    async def save_message(self, user_id, username, first_name, role, content):
        await self.ensure_user_exists(user_id, username, first_name)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)",
                    (user_id, role, content)
                )

    async def get_user_context(self, user_id, limit=20):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                    (user_id, limit)
                )
                rows = await cur.fetchall()
                # Return in chronological order (oldest first)
                return rows[::-1]

    async def clear_user_context(self, user_id):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
                return cur.rowcount

    async def reset_all_contexts(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("TRUNCATE TABLE messages")
                return True

db = Database()
