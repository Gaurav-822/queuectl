import os
import time
import subprocess
import signal
from datetime import datetime, timedelta
from queuectl.storage.db import get_connection
from queuectl.core.job_manager import retry_job
from queuectl.storage.db import get_config_value
import queuectl.constants as constants



"""
Each Worker's Functionality
- Gracefull Shutdown
- Fetch Job (atomically, to avoid duplicate Jobs being executed)
- Implementation of Exponential Backoff while Fetching Job
- Executing Commands
- Worker in Loop to execute commands coming in future (with polling to limit resource consumption)
"""


def handle_sigterm(sig, frame):
    constants.SHUTDOWN = True
    print(f"[Worker {os.getpid()}] Stopping gracefully, finishing current job...")


# Catch both Ctrl+C and kill signals
signal.signal(signal.SIGINT, handle_sigterm)
signal.signal(signal.SIGTERM, handle_sigterm)


# fetching jobs with locking (using SQLite3's to prevent duplicate execution)
# Also atomically claim one pending job whose retry delay has elapsed. (implementation of execution delay)
def fetch_next_job():
    conn = get_connection()
    cur = conn.cursor()
    try:
        base = get_config_value("exp_backoff_base") or 2
        conn.execute("BEGIN IMMEDIATE;")

        # Select all pending jobs ordered by creation time
        cur.execute("""
            SELECT id, command, attempts, max_retries, updated_at
            FROM jobs
            WHERE state='pending'
            ORDER BY created_at ASC
        """)
        jobs = cur.fetchall()

        selected_job = None
        now = datetime.utcnow()

        for job in jobs:
            attempts = int(job["attempts"])

            # Calculate the delay and last updated time for this job
            delay_seconds = base ** attempts if attempts > 0 else 0
            updated_at = datetime.fromisoformat(job["updated_at"]) if job["updated_at"] else now

            # Job eligible if current_time >= updated_at + delay
            if now >= updated_at + timedelta(seconds=delay_seconds):
                selected_job = job
                break  # pick the first eligible job

        if not selected_job:
            conn.rollback()
            conn.close()
            return None

        # Mark job as processing
        cur.execute("""
            UPDATE jobs
            SET state='processing', updated_at=DATETIME('now')
            WHERE id=? AND state='pending'
        """, (selected_job["id"],))

        if cur.rowcount == 0:
            conn.rollback()
            conn.close()
            return None

        conn.commit()
        return dict(selected_job)

    except Exception as e:
        conn.rollback()
        print(f"[Worker {os.getpid()}] Error during job fetch: {e}")
        return None
    finally:
        conn.close()



# execute the command using subprocess
def execute_command(cmd: str):
    try:
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0
    except Exception as e:
        print(f"[Worker {os.getpid()}] Command error: {e}")
        return False


# main worker loop to execute commands
def run_worker_loop():
    pid = os.getpid()
    poll_interval = int(get_config_value("poll_interval") or 2)  # taking polling rate for each worker to decrease resource overhead

    print(f"[Worker {pid}] Started")

    while not constants.SHUTDOWN:
        job = fetch_next_job()

        if not job:
            time.sleep(poll_interval)
            continue

        job_id = job["id"]
        cmd = job["command"]
        print(f"[Worker {pid}] Processing job : {job_id} : {cmd}")

        success = execute_command(cmd)

        if success:
            # Mark as completed
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE jobs SET state='completed', updated_at=DATETIME('now') WHERE id=?",
                    (job_id,),
                )
                conn.commit()
                conn.close()
                print(f"[Worker {pid}] Job {job_id} completed successfully.")
            except Exception as e:
                print(f"[Worker {pid}] Error updating job {job_id}: {e}")
        else:
            # Failed, call retry
            print(f"[Worker {pid}] Job {job_id} failed. Retrying if possible...")
            try:
                result = retry_job(job_id)
                print(f"[Worker {pid}] {result['message']}")
            except ValueError:
                print(f"[Worker {pid}] Job {job_id} not found during retry.")
            except Exception as e:
                print(f"[Worker {pid}] Unexpected retry error: {e}")

        # Graceful shutdown check after each job
        if constants.SHUTDOWN:
            print(f"[Worker {pid}] Graceful shutdown — exiting after current job.")
            break

    print(f"[Worker {pid}] Stopped.")
