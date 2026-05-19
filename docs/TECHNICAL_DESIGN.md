# Technical Design

## Architecture

```mermaid
flowchart LR
    codex["Allowed local JSONL roots"] --> parser["scripts/build_usage_data.py"]
    parser --> summary["data/generated/codex_usage_summary.json"]
    parser --> bridge["data/generated/codex_usage_summary.js"]
    parser --> csv["data/generated/*.csv"]
    bridge --> browser["web/index.html"]
    webjs["web/app.js"] --> browser
    css["web/styles.css"] --> browser
    browser --> dashboard["Local usage dashboard"]

    classDef local fill:#eef7ef,stroke:#167a5a,color:#17211b
    classDef generated fill:#eef3fb,stroke:#3767a5,color:#17211b
    class codex,parser,browser,webjs,css,dashboard local
    class summary,bridge,csv generated
```

Optional operations:

```mermaid
flowchart TD
    start["install.py"] --> mode{"Run mode"}
    mode -->|"--quickstart"| quick["Build data, start tokenized server, open browser"]
    mode -->|"--start-server"| bg["Start background localhost server"]
    mode -->|"--serve"| fg["Run foreground localhost server"]
    mode -->|"--sample or --real"| build["Generate local dashboard data"]
    mode -->|"--stop-server"| stop["Stop tracked server process"]
    quick --> server["scripts/serve_dashboard.py"]
    bg --> server
    fg --> server
    build --> parser["scripts/build_usage_data.py"]
    server --> state[".local/server.json and .local/server.log"]
    sched["scripts/schedule_dashboard.py"] --> print["Print cron, launchd, or Windows Task Scheduler commands"]
    print --> install{"Install schedule?"}
    install -->|"Only --install-cron --yes"| cron["Modify local crontab"]
    install -->|"Default"| noop["No system change"]
```

## Parser

The parser is implemented with the Python standard library. By default it reads only:

- `~/.codex/sessions`
- `~/.codex/archived_sessions`

It also supports explicit `--input-root` values for tests and sample fixtures.

## Metadata extraction

Allowed fields:

- top-level `timestamp`
- top-level `type`
- `payload.id` for session identity
- `payload.cwd` for project breakdown
- `payload.model` for model breakdown
- `payload.num_turns`
- `payload.memory_citation` presence
- `payload.info.total_token_usage.*`
- `payload.info.last_token_usage.*`

Ignored fields include conversation-bearing fields such as `content`, `message`, `input`, `output`, `summary`, and `text_elements`.

```mermaid
sequenceDiagram
    participant File as JSONL file
    participant Parser as Metadata parser
    participant Acc as Session accumulator
    participant Output as Generated outputs

    loop Each JSONL line
        File->>Parser: Parse JSON object
        alt Malformed record
            Parser->>Acc: Increment skipped count
        else Well-formed record
            Parser->>Parser: Read allowlisted metadata keys
            Note over Parser: Ignore content-bearing fields
            Parser->>Acc: Update tokens, model, cwd, turns, timestamps
        end
    end
    Acc->>Output: Write redacted JSON, JS bridge, and CSV files
```

## Data model

Each JSONL file is treated as one usage session for analytics. This keeps the parser simple and avoids joining records across files by content or conversation text.

```mermaid
flowchart TD
    record["JSONL records"] --> session["Session accumulator"]
    session --> sessionRows["Session rows"]
    session --> tokenEvents["Token event deltas"]
    session --> turnEvents["Turn events"]
    tokenEvents --> daily["Daily summaries"]
    turnEvents --> daily
    sessionRows --> projects["Project breakdown"]
    sessionRows --> models["Model breakdown"]
    sessionRows --> largest["Largest sessions"]
    projects --> memory["Memory reuse signals"]
    sessionRows --> memory
    daily --> insights["Plain-English insights"]
    projects --> insights
    memory --> insights
```

Generated session fields:

- `session_id`
- `source_file`
- `date`
- `last_updated_at`
- `project`
- `cwd`
- `model`
- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `total_tokens`
- `turn_count`
- `token_events_count`
- `max_single_turn_total_tokens`
- `memory_citation_detected`

Daily summary fields:

- `date`
- `sessions`
- `turns`
- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `total_tokens`
- `cache_ratio`
- `output_input_ratio`
- `rolling_7_day_total_tokens`

## Dashboard

The dashboard is static. It uses a generated `codex_usage_summary.js` file to support direct browser opening without a local HTTP server. When served through a local server, the same static files work unchanged.

No external JavaScript or CSS is loaded.

## Server lifecycle

The background server is a Python standard-library static server bound to `127.0.0.1`. It does not index data into memory and serves files directly from disk. Server state is stored in `.local/server.json`; logs are stored in `.local/server.log`.

```mermaid
stateDiagram-v2
    [*] --> Stopped
    Stopped --> Starting: install.py --start-server
    Starting --> Running: Server binds to 127.0.0.1
    Starting --> Failed: Port unavailable or bind denied
    Running --> Refreshing: POST /api/refresh
    Refreshing --> Running: Data regenerated
    Running --> ShutdownScheduled: POST /api/page-closed
    ShutdownScheduled --> Running: POST /api/page-opened
    ShutdownScheduled --> Stopped: Grace timer expires
    Running --> Stopped: install.py --stop-server
```

Stop it with:

```bash
python install.py --stop-server
```

The server is optional; opening `web/index.html` directly works after data generation.

## Local API

When served locally, the dashboard can call:

- `GET /api/status`
- `GET /api/help`
- `POST /api/refresh`
- `POST /api/page-opened`
- `POST /api/page-closed`
- `POST /api/shutdown`

Tokenized quickstart mode appends a random token to the dashboard URL and requires that token for local API calls.

## Source registry

The parser has built-in source definitions for Codex, Claude, Gemini, and ChatGPT. Codex is enabled by default. Claude and Gemini are experimental opt-in JSONL roots. ChatGPT is manual-root-required because no stable metadata-only JSONL root is assumed.
