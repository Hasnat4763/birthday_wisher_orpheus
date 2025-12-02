import sqlite3

conn = sqlite3.connect("birthdays.db")
cursor = conn.cursor()

def init():
    