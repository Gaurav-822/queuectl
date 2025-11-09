import os
import time
import signal
from multiprocessing import Process
from queuectl.core.worker import run_worker_loop

"""
Starting the Workers and Gracefully Stopping the Workers
"""


WORKERS = []
SHUTDOWN_FILE = os.path.expanduser("~/.queuectl/stop.flag")


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


# gracefully stopping the workers
def stop_workers():
    open(SHUTDOWN_FILE, "w").close()
    print("[Manager] Stop flag created, workers will exit gracefully.")
    time.sleep(2)

    for p in WORKERS:
        if p.is_alive():
            os.kill(p.pid, signal.SIGINT)
            p.join(timeout=5)
