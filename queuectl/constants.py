"""
Global constants shared across QueueCTL components.
"""

# Job life cycle valid states
VALID_STATES = [
    "pending",     # waiting to be picked up by a worker
    "processing",  # currently being executed
    "completed",   # successfully executed
    "failed",      # failed but eligible for retry
    "dead",        # permanently failed, moved to DLQ
]

# Global in-process shutdown flag
SHUTDOWN = False

# Worker exit reason codes
EXIT_OK = 0
EXIT_ERR = 1
EXIT_NOT_FOUND = 4