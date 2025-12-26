import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the database and create the posts table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shortcode TEXT UNIQUE NOT NULL,
                publication_date TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def insert_post(self, shortcode: str, description: str = None) -> bool:
        """Insert a new post into the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            publication_date = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO posts (shortcode, publication_date, description)
                VALUES (?, ?, ?)
            ''', (shortcode, publication_date, description))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def post_exists(self, shortcode: str) -> bool:
        """Check if a post with the given shortcode already exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM posts WHERE shortcode = ?', (shortcode,))
        result = cursor.fetchone()
        conn.close()
        
        return result is not None

    def delete_post(self, shortcode: str) -> bool:
        """Delete a post by shortcode."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM posts WHERE shortcode = ?', (shortcode,))
        conn.commit()
        
        deleted = cursor.rowcount > 0
        conn.close()
        
        return deleted

    def get_all_posts(self):
        """Retrieve all posts from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT shortcode, publication_date, description FROM posts')
        posts = cursor.fetchall()
        conn.close()
        
        return posts