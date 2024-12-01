import sqlite3

TAG_DB = "client_tags.db"

def init_tag_db():
    """Initialize the SQLite database for storing client tags."""
    conn = sqlite3.connect(TAG_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_tags (
            client_ip TEXT PRIMARY KEY,
            tag TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_tags():
    """Retrieve all client tags from the SQLite database."""
    conn = sqlite3.connect(TAG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT client_ip, tag FROM client_tags")
    tags = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return tags

def add_or_update_tag(client_ip, tag):
    """Add or update a tag for a client IP in the SQLite database."""
    conn = sqlite3.connect(TAG_DB)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO client_tags (client_ip, tag) 
        VALUES (?, ?) 
        ON CONFLICT(client_ip) 
        DO UPDATE SET tag = excluded.tag
    """, (client_ip, tag))
    conn.commit()
    conn.close()
