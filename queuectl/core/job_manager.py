import json
from datetime import datetime, timedelta
from queuectl.storage.db import get_connection, insert_job, list_jobs as db_list_jobs, get_config_value
from queuectl.constants import VALID_STATES


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


# working
def enqueue_job(job_json: str):
    """
    Taking only 'id' and 'command' as input, other columns are self determined
    """
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


# working
def list_jobs(state=None):
    """Return all jobs or jobs filtered by state."""
    if state and state not in VALID_STATES:
        raise ValueError(f"Invalid state '{state}'. Must be one of {VALID_STATES}.")
    return db_list_jobs(state)


# working
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

    if attempts > max_retries:
        # Move job to Dead Letter Queue
        cur.execute(
            "UPDATE jobs SET state='dead', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), job_id),
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


# working
def get_status_summary():
    """Return a summary count of jobs by state."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) AS count FROM jobs GROUP BY state;")
    rows = cur.fetchall()
    conn.close()

    summary = {r["state"]: r["count"] for r in rows}
    for s in VALID_STATES:
        summary.setdefault(s, 0)
    return summary


# working
def move_to_dlq(job_id: str):
    """Force move a job to DLQ."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET state='dead' WHERE id=?", (job_id,))
    if cur.rowcount == 0:
        conn.close()
        raise ValueError(f"No job found with id '{job_id}'")
    conn.commit()
    conn.close()
    return {"status": "moved", "id": job_id, "new_state": "dead"}



# working
def list_dlq():
    """List all jobs currently in DLQ."""
    return db_list_jobs("dead")


# error here, shows message
def retry_dlq(job_id: str):
    """Move a DLQ job back to pending and reset attempts."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET state='pending', attempts=0 WHERE id=? AND state='dead'", (job_id,))
    if cur.rowcount == 0:
        conn.close()
        raise ValueError(f"No DLQ job found with id '{job_id}'")
    conn.commit()
    conn.close()
    return {"status": "retried", "id": job_id, "new_state": "pending"}
