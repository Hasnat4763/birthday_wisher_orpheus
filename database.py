import sqlite3

def connect_db():
    conn = sqlite3.connect("Database/birthdays.db")
    return conn

def init():
    db = connect_db()
    cursor = db.cursor()
    cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS birthday_info (
        user_id TEXT PRIMARY KEY,
        day INTEGER NOT NULL,
        month INTEGER NOT NULL,
        tz TEXT NOT NULL
    )
    """
    )
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS wiki_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day INTEGER NOT NULL,
        month INTEGER NOT NULL,
        year TEXT,
        name TEXT NOT NULL,
        description TEXT,
        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(day, month, name)
    )
    """
    )
    db.commit()
    db.close()

if __name__ == "__main__":
    init()