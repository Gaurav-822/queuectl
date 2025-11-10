# QueueCTL, CLI-Based Background Job Queue System

## 1. Introduction

**QueueCTL** is a command-line-based background job management system developed as a technical assignment for **FLAM**.
It provides a minimal yet production-oriented backend capable of handling asynchronous job execution through worker processes.
The system supports **automatic retries with exponential backoff**, maintains a **Dead Letter Queue (DLQ)** for permanently failed jobs, and ensures **persistent state management** using SQLite3.

The project demonstrates reliability, configurability, and modular design principles through a clean, extensible architecture.

---

## 2. Academic Integrity and Originality Declaration

This project has been independently designed and implemented by **Gaurav Bhushan Kumar** for submission to **FLAM**.
All work is original, created without external code copying or collaboration.
Any external concepts (e.g., multiprocessing, SQLite usage) have been adapted from standard Python documentation and implemented independently.

This submission adheres strictly to institutional academic integrity guidelines prohibiting plagiarism or unauthorized assistance.

---

## 3. Objectives

The primary objectives of QueueCTL are:

* To manage and execute background jobs using worker processes.
* To implement automatic job retries with exponential backoff for transient failures.
* To maintain a **Dead Letter Queue (DLQ)** for jobs that permanently fail after exceeding retry limits.
* To ensure persistence and fault tolerance using **SQLite3**.
* To expose all operations through a consistent and intuitive **CLI interface**.

---

## 4. Core Features

* Persistent job storage using **SQLite3** for durability and restart safety.
* Multi-worker parallel processing with **Python multiprocessing**.
* Configurable retry mechanism with **exponential backoff** (`delay = base ^ attempts`).
* Dedicated **Dead Letter Queue (DLQ)** for permanently failed jobs.
* Graceful worker shutdown - active jobs complete before exit.
* Fully configurable runtime parameters (`max_retries`, `exp_backoff_base`, `poll_interval`).
* Safe concurrent access using **SQLite transactions**.
* Standardized **exit codes** for reliable scripting and monitoring.

---

## 5. System Overview

QueueCTL operates as a **CLI-based asynchronous job queue system**.
Users enqueue jobs with shell commands, which are processed by background workers that execute them in isolation.
Workers handle retries using exponential backoff and move unrecoverable jobs to the DLQ for review or manual retry.

### System Components

1. **CLI Layer** - User interface for all queue and configuration commands.
2. **Core Logic** - Job lifecycle management (enqueue, retry, DLQ, config).
3. **Worker Engine** - Executes jobs in subprocesses and handles retries.
4. **Storage Layer** - SQLite-based persistent backend ensuring durability.

---

## 6. Job Model

Each job is stored with the following structure:

```json
{
  "id": "unique-job-id",
  "command": "echo 'Hello World'",
  "state": "pending",
  "attempts": 0,
  "max_retries": 3,
  "created_at": "2025-11-04T10:30:00Z",
  "updated_at": "2025-11-04T10:30:00Z"
}
```

---

## 7. Job Lifecycle

| State        | Description                              |
| ------------ | ---------------------------------------- |
| `pending`    | Job is queued and awaiting execution.    |
| `processing` | Job is being executed by a worker.       |
| `completed`  | Job finished successfully.               |
| `failed`     | Job failed but can be retried.           |
| `dead`       | Job failed permanently and moved to DLQ. |

---

## 8. Command Line Interface (CLI)

### Job Management

| Command                                                | Description                          |
| ------------------------------------------------------ | ------------------------------------ |
| `queuectl enqueue '{"id":"job1","command":"sleep 2"}'` | Enqueue a new job.                   |
| `queuectl list --state pending`                        | List jobs filtered by state.         |
| `queuectl status`                                      | Display a summary of all job states. |

### Worker Control

| Command                           | Description                          |
| --------------------------------- | ------------------------------------ |
| `queuectl worker start --count 3` | Start one or more worker processes.  |
| `queuectl worker stop`            | Gracefully stop all running workers. |

### Dead Letter Queue (DLQ)

| Command                   | Description                                      |
| ------------------------- | ------------------------------------------------ |
| `queuectl dlq list`       | List jobs currently in DLQ.                      |
| `queuectl dlq retry job1` | Move a DLQ job back to pending for reprocessing. |

### Configuration Management

| Command                                  | Description                      |
| ---------------------------------------- | -------------------------------- |
| `queuectl config set max-retries 5`      | Set maximum retry count.         |
| `queuectl config set exp-backoff-base 3` | Update exponential backoff base. |
| `queuectl config set poll-interval 4`    | Adjust worker polling interval.  |

---

## 9. Retry and Backoff

Jobs use **exponential backoff** for retries:

```
delay = base ^ attempts
```

Example (`base = 2`):

| Attempt | Delay (seconds) |
| ------- | --------------- |
| 1       | 2               |
| 2       | 4               |
| 3       | 8               |
| >3      | Moved to DLQ    |

Execution eligibility:

```
current_time >= updated_at + (base ^ attempts)
```

---

## 10. Worker Operation

1. Atomically fetch eligible jobs (`BEGIN IMMEDIATE` transaction).
2. Skip jobs until retry delay elapses.
3. Execute job commands in isolated subprocesses.
4. Update job state after completion or failure.
5. Sleep for `poll_interval` seconds between polling cycles.
6. Exit gracefully when stop signal is received.

### Graceful Shutdown

Triggered via:

* `SIGINT` (Ctrl+C) - from terminal
* `SIGTERM` - via `queuectl worker stop`

Workers finish the current job before exiting safely.

---

## 11. Database Structure

| Table    | Description                                          |
| -------- | ---------------------------------------------------- |
| `jobs`   | Stores job metadata, states, and retry info.         |
| `config` | Stores user-defined and system configuration values. |

**Database Location:**
`~/.queuectl/jobs.db`

---

## 12. Default Configuration

| Key                | Default | Description                        |
| ------------------ | ------- | ---------------------------------- |
| `max_retries`      | 3       | Max retry attempts per job.        |
| `exp_backoff_base` | 2       | Base used for exponential delay.   |
| `poll_interval`    | 2       | Worker polling interval (seconds). |

---

## 13. Exit Codes

| Code | Constant         | Meaning                  |
| ---- | ---------------- | ------------------------ |
| 0    | `EXIT_OK`        | Successful execution.    |
| 1    | `EXIT_ERR`       | Error occurred.          |
| 4    | `EXIT_NOT_FOUND` | Job or config not found. |

---

## 14. Example Usage

```bash
# Enqueue jobs
queuectl enqueue '{"id":"job1","command":"echo Job 1"}'
queuectl enqueue '{"id":"job2","command":"bash -c '\''exit 1'\''"}'

# Start workers
queuectl worker start --count 2

# Check status
queuectl status

# Review DLQ
queuectl dlq list
```

Sample output:

```
Queue Status Summary:
  completed : 8
  dead      : 7
  pending   : 0
  processing: 0
  failed    : 0
```

---

## 15. Design Highlights

* Concurrency-safe job claiming with SQLite transactions.
* Dynamic delay and retry calculation via timestamps.
* Graceful termination with no data loss.
* Runtime configurability via CLI.
* Extensible architecture supporting future enhancements.

---

## 16. Future Enhancements

* Scheduled (time-delayed) jobs.
* Web-based monitoring dashboard.
* REST API integration.
* Worker health tracking and metrics.
* Priority-based job queue.

---

## 17. Technology Stack

| Component   | Technology                        |
| ----------- | --------------------------------- |
| Language    | Python 3                          |
| Database    | SQLite3                           |
| Concurrency | Multiprocessing                   |
| Interface   | CLI via argparse                  |
| Packaging   | pipx (for isolated CLI execution) |

---

## 18. Installation (via `pipx`)

QueueCTL is packaged for isolated CLI usage using **`pipx`**, which creates a self-contained virtual environment.

### Steps:

```bash
# 1. Clone the repository
git clone https://github.com/Gaurav-822/queuectl.git
cd queuectl

# 2. Install using pipx
pipx install .
```

Once installed, the `queuectl` command becomes globally available:

```bash
queuectl --help
```

### Updating the CLI

If you make local changes and wish to reinstall:

```bash
pipx uninstall queuectl
pipx install .
```

---

## 19. Conclusion

**QueueCTL** is a self-contained, reliable, and extensible background job queue system demonstrating the principles of asynchronous processing, exponential backoff retry logic, and robust CLI-driven configuration.
Its modular structure and process isolation design make it suitable for production-grade backend use cases as well as academic evaluation.

---

## 20. Author Declaration

**Developed and Submitted by:** **Gaurav Bhushan Kumar**, for: **FLAM - Technical Assignment Submission**

| Contact  | Information                                                           |
| -------- | --------------------------------------------------------------------- |
| Email    | [gaurav.moocs@gmail.com](mailto:gaurav.moocs@gmail.com)               |
| LinkedIn | [linkedin.com/in/gauravbk08](https://www.linkedin.com/in/gauravbk08/) |

