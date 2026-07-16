with open("/home/teguh_gnfadhilah/xen/xen_agent.py", "r") as f:
    content = f.read()

# Fix the db_save_message function - use time.time() instead of SQL julianday
old = '''def db_save_message(role: str, content: str, user_id: int = None):
    """Save a message to DB"""
    try:
        if user_id is None:
            user_id = current_user_id or 0
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, (julianday(\\"now\\") - 2440587.5) * 86400.0)",
            (user_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB save error: {e}")'''

new = '''def db_save_message(role: str, content: str, user_id: int = None):
    """Save a message to DB"""
    import time
    try:
        if user_id is None:
            user_id = current_user_id or 0
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, role, content, time.time())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB save error: {e}")'''

content = content.replace(old, new)

with open("/home/teguh_gnfadhilah/xen/xen_agent.py", "w") as f:
    f.write(content)

print("Timestamp fix applied")
