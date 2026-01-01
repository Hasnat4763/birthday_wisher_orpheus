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
    cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS birthday_threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        channel_id TEXT NOT NULL,
        thread_ts TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    )
    
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS birthday_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        month INTEGER NOT NULL,
                        day INTEGER NOT NULL,
                        status BOOLEAN DEFAULT 0,
                        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, year, month, day)
                   )
                   """)
    
    cursor.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_wiki_date 
    ON wiki_cache(month, day)
    """)
    
    cursor.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_thread_date 
    ON birthday_threads(date)
    """)
    
    db.commit()
    db.close()
    print("✅ Database initialized!")


if __name__ == "__main__": 
    init()