# Usage

## Build sample data

```bash
python install.py --sample --project-names
```

Sample data is synthetic and lives in `tests/sample_data/`. It exists so screenshots and demos can show realistic charts without exposing local usage.

## Build real local data

```bash
python install.py --real
python install.py --real --project-names
```

## One-click quickstart

Double-click `quickstart.command` on macOS, or run:

```bash
python install.py --quickstart --project-names
```

Quickstart builds data, starts a tokenized local server, opens the dashboard, and enables page-close auto-shutdown.

## Serve locally

```bash
python install.py --sample --start-server
python install.py --real --project-names --start-server
```

The default local URL is:

```text
http://127.0.0.1:8765/web/index.html
```

Stop the background server:

```bash
python install.py --stop-server
```

Run a foreground server instead:

```bash
python install.py --real --serve
```

## Open directly

After generating data, open:

```text
web/index.html
```

The page loads `../data/generated/codex_usage_summary.js`, which works from `file://` in normal browsers because it is a script tag rather than a fetch call.

## Theme preferences

Use the moon/sun button in the dashboard header to switch day and night themes. The browser remembers only non-sensitive UI preferences:

- theme
- selected deep-dive type
- selected deep-dive item

For screenshot generation or demos, `web/index.html?theme=light` and `web/index.html?theme=dark` override the stored theme for that page load.

## Time range

Use the range control near the top of the dashboard to switch between:

- 7 days
- 1 month
- 6 months
- 1 year

The selected range is stored as a non-sensitive browser preference. You can also open a specific range with `web/index.html?range=30d`, `web/index.html?range=180d`, or `web/index.html?range=365d`.

## Dry run

```bash
python scripts/build_usage_data.py --dry-run
```

## Redaction

Redaction is enabled by default:

```bash
python scripts/build_usage_data.py --redact-paths
```

To include raw local paths and session identifiers:

```bash
python scripts/build_usage_data.py --no-redact-paths
```

## Tests

```bash
python -m unittest discover -s tests
```

## Privacy audit

```bash
python scripts/privacy_audit.py
```

## Scheduled refresh

Print a schedule without installing it:

```bash
python scripts/schedule_dashboard.py --target cron
python scripts/schedule_dashboard.py --target launchd
python scripts/schedule_dashboard.py --target windows
```

Install cron only when you mean to modify your crontab:

```bash
python scripts/schedule_dashboard.py --install-cron --yes
```

## Sources

List supported sources:

```bash
python scripts/build_usage_data.py --list-sources
```

Use Codex only:

```bash
python scripts/build_usage_data.py --source codex
```

Use an explicit local JSONL root:

```bash
python scripts/build_usage_data.py --input-root /path/to/metadata-jsonl
```
