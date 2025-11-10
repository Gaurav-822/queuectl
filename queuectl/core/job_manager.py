import json
from datetime import datetime, timedelta
from queuectl.storage.db import get_connection, insert_job, list_jobs as db_list_jobs
from queuectl.constants import VALID_STATES
import os
from queuectl.storage.db import get_connection


"""
Inserting Maintaing and Updating Job's Implementations

- Enqueue Jobs
- Listing all the Jobs (by state if required)
- Updating Job's State/Lifecycle
- Retry Job's Execution
- Status Summary of all the Jobs
- Maintaing DLQ (Dead Letter Queue) within the SQL db
- DLQ operations (listing, retrying)
"""

# Enqueue jobs by taking only 'id' and 'command' as input, other columns are self determined
def enqueue_job(job_json: str):
    try:
        data = json.loads(job_json)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON. Example: {\"id\": \"job1\", \"command\": \"echo 'Hi'\"}")

    if not isinstance(data, dict):
        raise ValueError("Job must be a JSON object.")

    allowed_keys = {"id", "command"}
    extra = set(data.keys()) - allowed_keys
    if extra:
        raise ValueError(f"Invalid field(s): {', '.join(extra)}. Only 'id' and 'command' allowed.")

    insert_job(data)
    return {"status": "success", "message": f"Job '{data['id']}' added successfully."}


# list all the jobs in the queue (sqlite3)
def list_jobs(state=None):
    if state and state not in VALID_STATES:
        raise ValueError(f"Invalid state '{state}'. Must be one of {VALID_STATES}.")
    return db_list_jobs(state)


# function to update job state
def update_job_state(job_id: str, new_state: str):
    if new_state not in VALID_STATES:
        raise ValueError(f"Invalid state '{new_state}'. Must be one of {VALID_STATES}.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"No job found with id '{job_id}'")

    cur.execute("UPDATE jobs SET state = ? WHERE id = ?", (new_state, job_id))
    conn.commit()
    conn.close()
    return {"status": "updated", "id": job_id, "new_state": new_state}


# retry a job after it failed in the first go
def retry_job(job_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, attempts, max_retries FROM jobs WHERE id = ?", (job_id,))
    job = cur.fetchone()

    if not job:
        conn.close()
        raise ValueError(f"No job found with id '{job_id}'")

    # Increment attempts count
    attempts = int(job["attempts"]) + 1
    max_retries = int(job["max_retries"])

    if attempts >= max_retries:
        # Move job to Dead Letter Queue
        cur.execute(
            "UPDATE jobs SET state='dead', attempts=?, updated_at=? WHERE id=?",
            (attempts, datetime.utcnow().isoformat(), job_id),
        )
        msg = f"Job '{job_id}' moved to DLQ after {max_retries} retries."
    else:
        # Re-enqueue job for retry
        cur.execute(
            """
            UPDATE jobs
            SET state='pending',
                attempts=?,
                updated_at=? 
            WHERE id=?
            """,
            (attempts, datetime.utcnow().isoformat(), job_id),
        )
        msg = f"Job '{job_id}' scheduled for retry #{attempts}."

    conn.commit()
    conn.close()

    return {"status": "retry", "id": job_id, "attempts": attempts, "message": msg}


# get summary of the queue
def get_status_summary():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) AS count FROM jobs GROUP BY state;")
    rows = cur.fetchall()
    conn.close()

    summary = {r["state"]: r["count"] for r in rows}
    for s in VALID_STATES:
        summary.setdefault(s, 0)
    return summary



# List all jobs currently in DLQ.
def list_dlq():
    return db_list_jobs("dead")


SHUTDOWN_FILE = os.path.expanduser("~/.queuectl/stop.flag")

# manually move dlq jobs back to pending and re run those
def retry_dlq(job_id: str):
    conn = get_connection()
    cur = conn.cursor()

    # Verify DLQ job exists
    cur.execute("SELECT id FROM jobs WHERE id=? AND state='dead'", (job_id,))
    job = cur.fetchone()
    if not job:
        conn.close()
        raise ValueError(f"No DLQ job found with id '{job_id}'")

    # Move to pending, mark force_retry
    cur.execute("""
        UPDATE jobs
        SET state='pending',
            force_retry=1,
            updated_at=DATETIME('now')
        WHERE id=? AND state='dead'
    """, (job_id,))
    conn.commit()
    conn.close()

    # Detect worker activity based on stop flag (fix this)
    if os.path.exists(SHUTDOWN_FILE):
        message = f"Job '{job_id}' moved from DLQ and will run as soon as a worker is started."
    else:
        message = f"Job '{job_id}' moved from DLQ and will be picked up shortly by an active worker."

    return {
        "status": "retried",
        "id": job_id,
        "new_state": "pending",
        "message": message
    }