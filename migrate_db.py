"""
migrate_db.py — One-time migration to encrypt existing plain-text private keys.
Run this ONCE before restarting the bot.
"""
import sqlite3
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "agora_bot.db")
key = os.getenv("ENCRYPTION_KEY")
if not key:
    raise SystemExit("ERROR: ENCRYPTION_KEY not set in .env")

cipher = Fernet(key.encode())
conn   = sqlite3.connect(DB_PATH)
cur    = conn.cursor()

# Check current schema
cur.execute("PRAGMA table_info(users)")
cols = [c[1] for c in cur.fetchall()]
print("Existing columns:", cols)

if "private_key_enc" not in cols:
    print("Adding private_key_enc and created_at columns...")
    cur.execute("ALTER TABLE users ADD COLUMN private_key_enc TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT '2026-01-01 00:00:00'")

    cur.execute("SELECT user_id, private_key FROM users")
    rows = cur.fetchall()
    for user_id, pk in rows:
        if pk:
            encrypted = cipher.encrypt(pk.encode()).decode()
            cur.execute(
                "UPDATE users SET private_key_enc = ? WHERE user_id = ?",
                (encrypted, user_id)
            )
            print(f"  ✅ Encrypted key for user {user_id}")

    conn.commit()
    print("Migration complete!")
else:
    print("Already migrated — nothing to do.")

conn.close()
