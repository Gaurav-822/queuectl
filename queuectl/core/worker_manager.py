import os
import time
import signal
from multiprocessing import Process
from queuectl.core.worker import run_worker_loop
from queuectl.constants import SHUTDOWN_FILE


"""
Starting the Workers and Gracefully Stopping the Workers
"""


WORKERS = []


# spawn worker processes
def start_workers(count: int):
    if os.path.exists(SHUTDOWN_FILE):
        os.remove(SHUTDOWN_FILE)

    for i in range(count):
        p = Process(target=run_worker_loop)
        p.start()
        WORKERS.append(p)
        print(f"[Manager] Worker ({i}) {p.pid} started")

    print(f"[Manager] Running {count} workers. Press Ctrl+C to stop.")

    try:
        while any(p.is_alive() for p in WORKERS):
            time.sleep(2)
    except KeyboardInterrupt:
        print("[Manager] Caught KeyboardInterrupt, stopping workers...")
        stop_workers()

    print("[Manager] All workers stopped.")


# gracefully stopping the workers (all the worker completes it's work before shutting down)
def stop_workers():
    # stop flag creation to stop all the workers to further take any job
    open(SHUTDOWN_FILE, "w").close()
    print("[Manager] Stop flag created, workers will exit gracefully.")

    term_wait = 3.0 # time before forcefully killing the processes
    for p in WORKERS:
        p.join(timeout=term_wait)

    still_alive = [p for p in WORKERS if p.is_alive()]
    if still_alive:
        print(f"[Manager] {len(still_alive)} worker(s) did not exit; sending SIGTERM")
        for p in still_alive:
            try:
                os.kill(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for p in still_alive:
            p.join(timeout=term_wait)

    still_alive = [p for p in WORKERS if p.is_alive()]
    if still_alive:
        print(f"[Manager] {len(still_alive)} worker(s) still running; sending SIGKILL")
        for p in still_alive:
            try:
                os.kill(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.join(timeout=1.0)
