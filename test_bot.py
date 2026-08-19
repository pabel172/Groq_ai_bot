import os
import unittest
import sqlite3
import tempfile
import bot

class TestBotFunctions(unittest.TestCase):

    def test_split_text(self):
        text = "Hello world\nThis is a test message."
        chunks = bot.split_text(text, max_length=50)
        self.assertTrue(len(chunks) >= 1)
        self.assertEqual("".join(chunks).replace("\n", " "), "Hello world This is a test message.")

    def test_database_init_and_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "nested", "test_bot.db")
            bot.DATABASE = db_path

            bot.init_database()
            self.assertTrue(os.path.exists(db_path))

            conn = bot.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            self.assertIn("users", tables)
            self.assertIn("conversations", tables)

    def test_rate_limiting(self):
        bot.user_requests.clear()
        user_id = 99999
        bot.RATE_LIMIT_MESSAGES = 2
        bot.RATE_LIMIT_WINDOW = 60

        self.assertFalse(bot.is_rate_limited(user_id))
        self.assertFalse(bot.is_rate_limited(user_id))
        self.assertTrue(bot.is_rate_limited(user_id))

if __name__ == "__main__":
    unittest.main()
