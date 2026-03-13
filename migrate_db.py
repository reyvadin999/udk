import sqlite3
import os

db_path = 'instance/local.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding 'note' column to 'audit_log' table...")
    cursor.execute("ALTER TABLE audit_log ADD COLUMN note TEXT")
    conn.commit()
    print("Column 'note' added successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("Column 'note' already exists.")
    else:
        print(f"Error adding column: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    conn.close()
