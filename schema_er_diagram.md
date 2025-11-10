# Database Schema (ER Diagram)

```mermaid
erDiagram

    CONFIG {
        TEXT key PK "Primary key — config parameter name"
        TEXT value "Stored configuration value"
    }

    JOBS {
        TEXT id PK "Unique Job ID"
        TEXT command "Shell command to execute"
        TEXT state "Current lifecycle state"
        INTEGER attempts "Number of attempts so far"
        INTEGER max_retries "Maximum retry limit"
        INTEGER force_retry "Flag for manual force execution"
        TEXT created_at "Job creation timestamp"
        TEXT updated_at "Last update timestamp"
    }

    %% Relationships
    CONFIG ||--o{ JOBS : "applies to (via config values)"
