import re

with open("/home/teguh_gnfadhilah/xen/xen_agent.py", "r") as f:
    content = f.read()

# 1. Add current_user_id after CHAT_HISTORY
old1 = "CHAT_HISTORY = []"
new1 = "CHAT_HISTORY = []\n\ncurrent_user_id = None  # set by handler before calling AI"
content = content.replace(old1, new1)

# 2. Update init_db - add user_id to schema
old2 = '''    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)'''

new2 = '''    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL DEFAULT (julianday("now") - 2440587.5) * 86400.0
        )
    """)'''
content = content.replace(old2, new2)

# 3. Update db_save_message to accept user_id
old3 = '''def db_save_message(role: str, content: str):
    """Save a message to DB"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB save error: {e}")'''

new3 = '''def db_save_message(role: str, content: str, user_id: int = None):
    """Save a message to DB"""
    try:
        if user_id is None:
            user_id = current_user_id or 0
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, (julianday(\"now\") - 2440587.5) * 86400.0)",
            (user_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB save error: {e}")'''
content = content.replace(old3, new3)

# 4. Add current_user_id set in handle_message
old4 = '''    user_id = update.effective_user.id
    text = update.message.text or ""
    logger.info(f"Received message from {user_id} in {update.message.chat.type}: {text}")'''

new4 = '''    global current_user_id
    current_user_id = update.effective_user.id
    user_id = current_user_id
    text = update.message.text or ""
    logger.info(f"Received message from {user_id} in {update.message.chat.type}: {text}")'''
content = content.replace(old4, new4)

# 5. Add current_user_id in voice handler
old5 = '''    thinking_msg = await update.message.reply_text("Mendengarkan...")

    try:
        temp_dir = tempfile.mkdtemp(prefix='xen_voice_')'''
new5 = '''    global current_user_id
    current_user_id = update.effective_user.id
    thinking_msg = await update.message.reply_text("Mendengarkan...")

    try:
        temp_dir = tempfile.mkdtemp(prefix='xen_voice_')'''
content = content.replace(old5, new5)

# 6. Add current_user_id in photo handler
old6 = '''    thinking_msg = await update.message.reply_text("Menganalisa foto...")'''
new6 = '''    global current_user_id
    current_user_id = update.effective_user.id
    thinking_msg = await update.message.reply_text("Menganalisa foto...")'''
content = content.replace(old6, new6)

# 7. Add current_user_id in document handler
old7 = '''    file_name = doc.file_name
    thinking_msg = await update.message.reply_text(f'Membaca {file_name}...')'''
new7 = '''    file_name = doc.file_name
    global current_user_id
    current_user_id = update.effective_user.id
    thinking_msg = await update.message.reply_text(f'Membaca {file_name}...')'''
content = content.replace(old7, new7)

with open("/home/teguh_gnfadhilah/xen/xen_agent.py", "w") as f:
    f.write(content)

print("Done patching")
