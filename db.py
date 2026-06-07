import sqlite3
import os
from cryptography.fernet import Fernet

DB_PATH = os.path.join(os.path.dirname(__file__), "agora_bot.db")

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------
# ENCRYPTION_KEY must be a 32-byte url-safe base64 string generated with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Store it in your .env file.

def _get_cipher() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set in .env. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())

def _encrypt(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()

def _decrypt(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users — encrypted private key, creation timestamp
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            wallet_address  TEXT    NOT NULL,
            private_key_enc TEXT    NOT NULL,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    ''')

    # Address book
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS address_book (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name    TEXT    NOT NULL,
            address TEXT    NOT NULL,
            UNIQUE(user_id, name)
        )
    ''')

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User wallet helpers
# ---------------------------------------------------------------------------

def save_user_wallet(user_id: int, wallet_address: str, private_key: str):
    """Encrypt the private key before storing it."""
    encrypted = _encrypt(private_key)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO users (user_id, wallet_address, private_key_enc) VALUES (?, ?, ?)',
        (user_id, wallet_address, encrypted)
    )
    conn.commit()
    conn.close()


def get_user_wallet(user_id: int) -> dict | None:
    """Return wallet info with the decrypted private key, or None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT wallet_address, private_key_enc FROM users WHERE user_id = ?',
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "wallet_address": row[0],
            "private_key": _decrypt(row[1]),
        }
    return None


def get_all_users() -> list[dict]:
    """Return all registered users (wallet address only — never exposes keys)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, wallet_address, created_at FROM users')
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "wallet_address": r[1], "created_at": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# Contact / address-book helpers
# ---------------------------------------------------------------------------

def save_contact(user_id: int, name: str, address: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO address_book (user_id, name, address) VALUES (?, ?, ?)',
        (user_id, name.lower(), address)
    )
    conn.commit()
    conn.close()


def get_contact_address(user_id: int, name: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT address FROM address_book WHERE user_id = ? AND name = ?',
        (user_id, name.lower())
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
init_db()
