import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "agora_bot.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            wallet_address TEXT,
            private_key TEXT
        )
    ''')
    
    # Create address book table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS address_book (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            address TEXT,
            UNIQUE(user_id, name)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_user_wallet(user_id: int, wallet_address: str, private_key: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, wallet_address, private_key)
        VALUES (?, ?, ?)
    ''', (user_id, wallet_address, private_key))
    conn.commit()
    conn.close()

def get_user_wallet(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT wallet_address, private_key FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"wallet_address": row[0], "private_key": row[1]}
    return None

def save_contact(user_id: int, name: str, address: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    name_lower = name.lower()
    cursor.execute('''
        INSERT OR REPLACE INTO address_book (user_id, name, address)
        VALUES (?, ?, ?)
    ''', (user_id, name_lower, address))
    conn.commit()
    conn.close()

def get_contact_address(user_id: int, name: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    name_lower = name.lower()
    cursor.execute('SELECT address FROM address_book WHERE user_id = ? AND name = ?', (user_id, name_lower))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# Initialize DB on import
init_db()
