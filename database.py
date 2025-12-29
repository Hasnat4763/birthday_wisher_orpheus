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
    db.commit()
    db.close()
