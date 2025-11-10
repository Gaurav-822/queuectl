import sqlite3
import os
from datetime import datetime

# Database location: ~/.queuectl/jobs.db
DB_PATH = os.path.expanduser("~/.queuectl/jobs.db")

def get_connection():
    """Create or connect to the SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables and defaults."""
    conn = get_connection()
    cursor = conn.cursor()

    # CONFIG TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    cursor.execute("SELECT COUNT(*) AS cnt FROM config;")
    if cursor.fetchone()["cnt"] == 0:
        cursor.executemany(
            "INSERT INTO config (key, value) VALUES (?, ?)",
            [
                ("max_retries", "3"),
                ("exp_backoff_base", "2"),
                ("poll_interval", "2"),
            ],
        )

    # JOBS TABLE with force_retry column
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        command TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        created_at TEXT NOT NULL DEFAULT (DATETIME('now')),
        updated_at TEXT,
        force_retry INTEGER NOT NULL DEFAULT 0
    );
    """)

    # TRIGGER to update updated_at when state changes
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_update_timestamp
    AFTER UPDATE OF state ON jobs
    FOR EACH ROW
    WHEN NEW.state != 'pending'
    BEGIN
        UPDATE jobs
        SET updated_at = DATETIME('now')
        WHERE id = NEW.id;
    END;
    """)

    conn.commit()

    # Migration, backfill force_retry column if db already exists but column is missing
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN force_retry INTEGER NOT NULL DEFAULT 0;")
        conn.commit()
        print("[DB] Added missing column 'force_retry' to jobs table.")
    except sqlite3.OperationalError:
        # Column already exists — ignore
        pass

    conn.close()




def get_config_value(key: str) -> int:
    """Retrieve an integer configuration value from the config table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise KeyError(f"Configuration key '{key}' not found.")
    return int(row["value"])


def insert_job(job_data: dict):
    """
    Insert a job into the jobs table.
    The user may only provide 'id' and 'command'.
    All other values (state, attempts, max_retries, timestamps)
    are automatically filled based on system config.
    """
    if not isinstance(job_data, dict):
        raise TypeError("Job must be a dictionary.")

    # Validate required fields
    required = {"id", "command"}
    missing = required - job_data.keys()
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    job_id = job_data["id"]
    command = job_data["command"]

    # Fetch default retry count from config
    max_retries = get_config_value("max_retries")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO jobs (id, command, max_retries)
            VALUES (?, ?, ?)
        """, (job_id, command, max_retries))
    except sqlite3.IntegrityError:
        raise ValueError(f"Job with id '{job_id}' already exists.")
    finally:
        conn.commit()
        conn.close()


def list_jobs(state: str = None):
    """Fetch jobs from the database, optionally filtered by state."""
    conn = get_connection()
    cur = conn.cursor()
    if state:
        cur.execute("SELECT * FROM jobs WHERE state = ? ORDER BY created_at", (state,))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
