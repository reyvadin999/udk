import sqlite3
import os

db_path = 'instance/local.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("PRAGMA table_info(audit_log)")
    columns = cursor.fetchall()
    print("Columns in audit_log:")
    for col in columns:
        print(col)
    
    has_note = any(col[1] == 'note' for col in columns)
    if not has_note:
        print("\nColumn 'note' is MISSING.")
    else:
        print("\nColumn 'note' EXISTS.")
except Exception as e:
    print(f"Error checking schema: {e}")
finally:
    conn.close()
