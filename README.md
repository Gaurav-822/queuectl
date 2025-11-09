# QueueCTL, CLI-Based Background Job Queue System

## 1. Introduction

**QueueCTL** is a lightweight, production-grade backend system that manages background job execution through a **Command Line Interface (CLI)**.
It enables reliable asynchronous processing using worker processes, supports automatic retry with exponential backoff, and maintains a Dead Letter Queue (DLQ) for permanently failed jobs.

This project implements a **minimal but production-oriented job queue system** that ensures persistence, fault tolerance, and configurability through a simple and extensible design.

---

## 2. Objectives

The key objectives of QueueCTL are:

* To manage background jobs using worker processes.
* To support automatic retries with exponential backoff for transient failures.
* To maintain a **Dead Letter Queue (DLQ)** for jobs that fail after exceeding the maximum retry limit.
* To persist job data using a reliable storage backend (SQLite3).
* To provide complete operational control through a **CLI interface**.

---

## 3. Core Features

* Persistent job storage using **SQLite3** for durability across restarts.
* Multi-worker processing using **Python multiprocessing**.
* Configurable retry mechanism with **exponential backoff** (`delay = base ^ attempts`).
* Dead Letter Queue (DLQ) management for failed jobs.
* CLI commands for enqueueing, managing, and monitoring jobs.
* Atomic job claiming using **SQLite transactions** to prevent duplicate processing.
* Graceful shutdown of workers (workers complete current jobs before exiting).
* Configurable system parameters (`max_retries`, `exp_backoff_base`, `poll_interval`) via CLI.
* Standardized **exit codes** for operational clarity.

---

## 4. System Design Overview

QueueCTL operates as a **CLI-based job management system** where users can enqueue jobs, start worker processes, and monitor system state.
Each worker polls the database at a configurable interval, claims pending jobs atomically, and executes their associated shell commands.
Failed jobs are retried automatically using an exponential backoff delay. If retries exceed the configured maximum, the job is moved to the **Dead Letter Queue (DLQ)**.

### Components

1. **CLI Layer** — User interface for managing jobs, workers, DLQ, and configurations.
2. **Core Engine** — Handles job lifecycle, retries, and DLQ logic.
3. **Worker Module** — Executes jobs in separate processes and ensures atomic job claiming.
4. **Storage Layer** — SQLite-based persistent store for jobs and configuration.

---

## 5. Job Model

Each job is stored in the database with the following structure:

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

## 6. Job Lifecycle

| State        | Description                                           |
| ------------ | ----------------------------------------------------- |
| `pending`    | Job is queued and waiting to be picked by a worker.   |
| `processing` | Job is currently being executed by a worker.          |
| `completed`  | Job has executed successfully.                        |
| `failed`     | Job execution failed but is eligible for retry.       |
| `dead`       | Job permanently failed and has been moved to the DLQ. |

---

## 7. CLI Commands

### 7.1 Job Management

| Command                                                | Description                               |
| ------------------------------------------------------ | ----------------------------------------- |
| `queuectl enqueue '{"id":"job1","command":"sleep 2"}'` | Enqueue a new job into the queue.         |
| `queuectl list --state pending`                        | List jobs by state (optional filter).     |
| `queuectl status`                                      | Display summary counts of all job states. |

### 7.2 Worker Management

| Command                           | Description                          |
| --------------------------------- | ------------------------------------ |
| `queuectl worker start --count 3` | Start one or more worker processes.  |
| `queuectl worker stop`            | Gracefully stop all running workers. |

### 7.3 Dead Letter Queue (DLQ)

| Command                   | Description                                                |
| ------------------------- | ---------------------------------------------------------- |
| `queuectl dlq list`       | List all jobs in the DLQ.                                  |
| `queuectl dlq retry job1` | Move a DLQ job back to the pending queue for reprocessing. |

### 7.4 Configuration Management

| Command                                  | Description                      |
| ---------------------------------------- | -------------------------------- |
| `queuectl config set max-retries 5`      | Update the maximum retry count.  |
| `queuectl config set exp-backoff-base 3` | Modify exponential backoff base. |
| `queuectl config set poll-interval 4`    | Update worker polling interval.  |

---

## 8. Retry and Backoff Mechanism

QueueCTL implements exponential backoff to manage retries for failed jobs.

```
delay = base ^ attempts
```

Example (with base = 2):

| Attempt | Delay (seconds)  |
| ------- | ---------------- |
| 1       | 2                |
| 2       | 4                |
| 3       | 8                |
| >3      | Job moved to DLQ |

Retries are determined dynamically using the job’s `updated_at` timestamp:

```
current_time >= updated_at + (base ^ attempts)
```

---

## 9. Worker Operation

### Execution Flow

1. Fetches eligible jobs from the queue using SQLite locking (`BEGIN IMMEDIATE`).
2. Ensures the job’s retry delay has elapsed before execution.
3. Executes the command using Python’s `subprocess` module.
4. Updates job state to `completed` or triggers retry if failed.
5. Sleeps for the configured polling interval if no jobs are available.
6. Checks for stop signal and performs a graceful shutdown if detected.

### Graceful Shutdown

Workers respond to:

* `SIGINT` (Ctrl + C)
* `SIGTERM` (via `queuectl worker stop`)

On receiving a signal, workers complete their current job before exiting cleanly.

---

## 10. Persistent Storage Design

**Database:** `~/.queuectl/jobs.db`

**Tables:**

* `jobs` — Stores all job definitions, states, and retry information.
* `config` — Stores configurable runtime parameters.

**Triggers:**

* Automatically update `updated_at` on state changes (except when set to `pending`).

---

## 11. Configuration Defaults

| Key                | Default Value | Description                                          |
| ------------------ | ------------- | ---------------------------------------------------- |
| `max_retries`      | 3             | Maximum retry attempts per job before moving to DLQ. |
| `exp_backoff_base` | 2             | Base used for exponential backoff delay.             |
| `poll_interval`    | 2             | Worker polling interval in seconds.                  |

---

## 12. Exit Codes

| Code | Constant         | Meaning                                   |
| ---- | ---------------- | ----------------------------------------- |
| `0`  | `EXIT_OK`        | Command executed successfully.            |
| `1`  | `EXIT_ERR`       | General error occurred during execution.  |
| `4`  | `EXIT_NOT_FOUND` | Requested job or configuration not found. |

These exit codes enable integration with shell scripts and monitoring tools.

---

## 13. Example Run

```bash
# Enqueue jobs
queuectl enqueue '{"id":"job1","command":"echo Job 1"}'
queuectl enqueue '{"id":"job2","command":"bash -c '\''exit 1'\''"}'

# Start workers
queuectl worker start --count 2

# Monitor system
queuectl status

# Review failed jobs
queuectl dlq list
```

Example Output:

```
Queue Status Summary:
  completed : 8
  dead      : 7
  pending   : 0
  processing: 0
  failed    : 0
```

---

## 14. Key Design Highlights

* Concurrency-safe job execution using database-level transactions.
* Delay and retry logic computed dynamically using timestamps.
* Graceful shutdown implemented for process reliability.
* All operational parameters configurable via CLI.
* Extensible architecture for future enhancements (e.g., priority queues, scheduling).

---

## 15. Future Enhancements

* Scheduled or delayed job execution.
* Web dashboard for real-time monitoring.
* REST API for remote job management.
* Worker health and uptime tracking.
* Priority-based job queue.

---

## 16. Technology Stack

| Component   | Technology      |
| ----------- | --------------- |
| Language    | Python 3        |
| Database    | SQLite3         |
| Concurrency | Multiprocessing |
| Interface   | CLI (argparse)  |

---

## 17. Installation and Setup

```bash
git clone https://github.com/your-repo/queuectl.git
cd queuectl
pip install -e .
```

---

## 18. Conclusion

**QueueCTL** provides a reliable, lightweight, and extensible background job queue system that fulfills the core requirements of asynchronous job execution with fault tolerance and configurability.
Its modular architecture ensures maintainability and scalability while keeping implementation complexity minimal — making it an effective and practical solution for backend job processing.

---

## 19. Author

This project was developed by **Gaurav Bhushan Kumar** as a technical assignment submission for **FLAM**.

| Contact Channel | Details |
| :--- | :--- |
| **Email** | [gaurav.moocs@gmail.com](mailto:gaurav.moocs@gmail.com) |
| **LinkedIn** | [gauravbk08](https://www.linkedin.com/in/gauravbk08/) |
---
