import argparse
import sys
from queuectl.storage.db import init_db
from queuectl.core import job_manager
from queuectl.core import worker_manager
from queuectl.constants import EXIT_OK, EXIT_ERR, EXIT_NOT_FOUND


# checking the CLI (for testing)
# def cmd_check(_):
#     print(True)
#     return EXIT_OK

# Add a job to the queue
def cmd_enqueue(args):
    try:
        result = job_manager.enqueue_job(args.job_json)
        print(result["message"])
        return EXIT_OK
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ERR


# List all jobs, or by the state
def cmd_list(args):
    try:
        jobs = job_manager.list_jobs(args.state)
        if not jobs:
            print("No jobs found.")
            return EXIT_OK
        for job in jobs:
            print(job)
        return EXIT_OK
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ERR


# # Manually change job state (for testing)
# def cmd_update(args):
#     try:
#         result = job_manager.update_job_state(args.id, args.state)
#         print(result)
#         return EXIT_OK
#     except Exception as e:
#         print(f"ERROR: {e}", file=sys.stderr)
#         return EXIT_ERR


# Manually Trigger Retry for a Job
def cmd_retry(args):
    try:
        result = job_manager.retry_job(args.id)
        print(result["message"])
        return EXIT_OK
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ERR


# DLQ commands
def cmd_dlq(args):
    if args.action == "list":
        jobs = job_manager.list_dlq()
        if not jobs:
            print("DLQ is empty.")
            return EXIT_OK
        for job in jobs:
            print(job)
        return EXIT_OK

    elif args.action == "retry":
        try:
            result = job_manager.retry_dlq(args.id)
            print(result["message"])
            return EXIT_OK
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return EXIT_NOT_FOUND


# Status
def cmd_status(_):
    summary = job_manager.get_status_summary()
    print("Queue Status Summary:")
    for state, count in summary.items():
        print(f"  {state:10s}: {count}")
    return EXIT_OK


def main():
    init_db()

    parser = argparse.ArgumentParser(
        prog="queuectl",
        description="QueueCTL - Lightweight Job Queue CLI"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    '''
    All Parsers that makes up the available cmd comand
    '''

    # check (for testing)
    # subparsers.add_parser("check", help="Sanity check").set_defaults(func=cmd_check)

    # enqueue
    enqueue_parser = subparsers.add_parser("enqueue", help="Add a job")
    enqueue_parser.add_argument("job_json", help="Job JSON string with id and command")
    enqueue_parser.set_defaults(func=cmd_enqueue)

    # list
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--state", help="Filter by state", required=False)
    list_parser.set_defaults(func=cmd_list)

    # update (for testing)
    # update_parser = subparsers.add_parser("update", help="Manually change job state")
    # update_parser.add_argument("id", help="Job ID")
    # update_parser.add_argument("state", help="New state (pending/processing/completed/failed/dead)")
    # update_parser.set_defaults(func=cmd_update)

    # retry
    retry_parser = subparsers.add_parser("retry", help="Retry a job (applies backoff logic)")
    retry_parser.add_argument("id", help="Job ID to retry")
    retry_parser.set_defaults(func=cmd_retry)

    # dlq
    dlq_parser = subparsers.add_parser("dlq", help="View or retry DLQ jobs")
    dlq_sub = dlq_parser.add_subparsers(dest="action", required=True)

    dlq_list_parser = dlq_sub.add_parser("list", help="List jobs in DLQ")
    dlq_list_parser.set_defaults(func=cmd_dlq)

    dlq_retry_parser = dlq_sub.add_parser("retry", help="Retry a DLQ job")
    dlq_retry_parser.add_argument("id", help="Job ID")
    dlq_retry_parser.set_defaults(func=cmd_dlq)

    # worker
    worker_parser = subparsers.add_parser("worker", help="Start or stop background workers")
    worker_sub = worker_parser.add_subparsers(dest="action", required=True)
    worker_start = worker_sub.add_parser("start", help="Start worker processes")
    worker_start.add_argument("--count", type=int, default=1, help="Number of worker processes")
    worker_start.set_defaults(func=lambda args: worker_manager.start_workers(args.count))
    worker_stop = worker_sub.add_parser("stop", help="Stop all workers gracefully")
    worker_stop.set_defaults(func=lambda args: worker_manager.stop_workers())


    # status
    status_parser = subparsers.add_parser("status", help="Show queue summary")
    status_parser.set_defaults(func=cmd_status)

    # Parse + execute
    args = parser.parse_args()
    rc = args.func(args)
    sys.exit(rc)


if __name__ == "__main__":
    main()