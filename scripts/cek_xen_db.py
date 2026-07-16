import sqlite3
import os

db_path = os.path.expanduser("~/xen/data/chat_history.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)
if 'messages' in tables:
    schema = c.execute("SELECT sql FROM sqlite_master WHERE name='messages'").fetchone()[0]
    print('Schema:', schema)
    count = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    print('Rows:', count)
    rows = c.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 5").fetchall()
    for r in rows:
        print(r)
else:
    for t in tables:
        sch = c.execute(f"SELECT sql FROM sqlite_master WHERE name='{t}'").fetchone()[0]
        print(f'Table {t}: {sch}')
conn.close()
