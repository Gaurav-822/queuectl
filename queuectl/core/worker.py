import os
import time
import subprocess
import signal
from datetime import datetime, timedelta
from queuectl.storage.db import get_connection
from queuectl.core.job_manager import retry_job
from queuectl.storage.db import get_config_value
import queuectl.constants as constants
from queuectl.constants import SHUTDOWN_FILE



"""
Each Worker's Functionality
- Gracefull Shutdown
- Fetch Job (atomically, to avoid duplicate Jobs being executed)
- Implementation of Exponential Backoff while Fetching Job
- Executing Commands
- Worker in Loop to execute commands coming in future (with polling to limit resource consumption)
"""


def handle_sigterm(sig, frame):
    if not constants.SHUTDOWN:
        constants.SHUTDOWN = True
        if sig == signal.SIGINT:
            sig_name = "SIGINT (Ctrl+C)"
        elif sig == signal.SIGTERM:
            sig_name = "SIGTERM"
        else:
            sig_name = f"signal {sig}"

        print(f"[Worker {os.getpid()}] Received {sig_name}, will finish current job then stop.")


# Catch both Ctrl+C and kill signals
signal.signal(signal.SIGINT, handle_sigterm)
signal.signal(signal.SIGTERM, handle_sigterm)


# fetching jobs with locking (using SQLite3's to prevent duplicate execution)
# Also atomically claim one pending job whose retry delay has elapsed. (implementation of execution delay)
# if using force job then skip the execution delay
def fetch_next_job():
    conn = get_connection()
    cur = conn.cursor()
    try:
        base = get_config_value("exp_backoff_base") or 2
        conn.execute("BEGIN IMMEDIATE;")

        cur.execute("""
            SELECT id, command, attempts, max_retries, updated_at, force_retry
            FROM jobs
            WHERE state='pending'
            ORDER BY created_at ASC
        """)
        jobs = cur.fetchall()

        selected_job = None
        now = datetime.utcnow()

        for job in jobs:
            attempts = int(job["attempts"])
            force_retry = int(job["force_retry"])

            if force_retry == 1:
                selected_job = job
                break

            delay_seconds = base ** attempts if attempts > 0 else 0
            updated_at = datetime.fromisoformat(job["updated_at"]) if job["updated_at"] else now

            if now >= updated_at + timedelta(seconds=delay_seconds):
                print("Ran after", delay_seconds, "seconds")
                selected_job = job
                break

        if not selected_job:
            conn.rollback()
            conn.close()
            return None

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
        # result = subprocess.run(cmd, shell=True)
        result = subprocess.run(cmd, shell=True, preexec_fn=os.setpgrp)
        return result.returncode == 0
    except Exception as e:
        print(f"[Worker {os.getpid()}] Command error: {e}")
        return False


def run_worker_loop():
    pid = os.getpid()
    poll_interval = int(get_config_value("poll_interval") or 2)
    print(f"[Worker {pid}] Started")

    while not constants.SHUTDOWN:
        if os.path.exists(SHUTDOWN_FILE):
            constants.SHUTDOWN = True
            print(f"[Worker {pid}] Detected stop flag — shutting down gracefully.")
            break

        job = fetch_next_job()
        if not job:
            time.sleep(poll_interval)
            continue

        job_id = job["id"]
        cmd = job["command"]
        print(f"[Worker {pid}] Processing job : {job_id} : {cmd}")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT attempts, max_retries, force_retry FROM jobs WHERE id=?", (job_id,))
        job_meta = cur.fetchone()
        conn.close()

        if job_meta:
            attempts = int(job_meta["attempts"])
            max_retries = int(job_meta["max_retries"])
            force_retry = int(job_meta["force_retry"])

            if attempts > max_retries and not force_retry:
                print(f"[Worker {pid}] Skipping job {job_id} (exceeded max retries).")
                continue

            if force_retry:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE jobs SET attempts = attempts + 1 WHERE id=?", (job_id,))
                conn.commit()
                conn.close()
                print(f"[Worker {pid}] Force retry: incremented attempts for job {job_id}.")

        success = execute_command(cmd)

        conn = get_connection()
        cur = conn.cursor()

        if success:
            cur.execute(
                "UPDATE jobs SET state='completed', updated_at=DATETIME('now'), force_retry=0 WHERE id=?",
                (job_id,),
            )
            conn.commit()
            conn.close()
            print(f"[Worker {pid}] Job {job_id} completed successfully.")
        else:
            print(f"[Worker {pid}] Job {job_id} failed. Retrying if possible...")
            try:
                result = retry_job(job_id)
                print(f"[Worker {pid}] {result['message']}")
            except ValueError:
                print(f"[Worker {pid}] Job {job_id} not found during retry.")
            except Exception as e:
                print(f"[Worker {pid}] Unexpected retry error: {e}")
            finally:
                cur.execute("UPDATE jobs SET force_retry=0 WHERE id=?", (job_id,))
                conn.commit()
                conn.close()

        if constants.SHUTDOWN:
            print(f"[Worker {pid}] Graceful shutdown, exiting after current job.")
            break

    print(f"[Worker {pid}] Stopped.")
