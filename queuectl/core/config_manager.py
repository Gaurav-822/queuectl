from queuectl.storage.db import get_connection

"""
Listing and Managing Configuration Files
"""

def list_config():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config")
    rows = cur.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def get_config(key: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise ValueError(f"Configuration key '{key}' not found.")
    return row["value"]

def set_config(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO config (key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()
    conn.close()
    return {"status": "updated", "key": key, "value": value}
