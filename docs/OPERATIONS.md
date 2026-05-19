# Operations

## Local server options

Quickstart:

```bash
python install.py --quickstart --project-names
```

Quickstart starts a tokenized local server, opens the dashboard in the browser, and enables auto-shutdown after the page closes.

Foreground server:

```bash
python install.py --real --serve
```

This is useful while developing because logs stay in the terminal.

Background server:

```bash
python install.py --real --start-server
```

This starts a local static server on `127.0.0.1` and writes process state to `.local/server.json`.

The server refuses non-loopback hosts unless `--allow-non-loopback` is explicitly passed to `scripts/serve_dashboard.py`. Normal usage should stay on localhost.

Stop it:

```bash
python install.py --stop-server
```

Check it:

```bash
python install.py --server-status
```

## Memory and lifecycle

The server is a static file server from the Python standard library. It does not keep session data in a long-running process; generated JSON/CSV files stay on disk and are read by the browser. This keeps the server lifecycle simple and reduces memory-leak risk.

In quickstart mode, the page sends a local `page-closed` signal on browser close. The server then waits briefly and shuts itself down. If the browser or OS blocks that signal, use:

```bash
python install.py --stop-server
```

## Scheduled refresh

Print schedule commands:

```bash
python scripts/schedule_dashboard.py --target cron
python scripts/schedule_dashboard.py --target launchd
python scripts/schedule_dashboard.py --target windows
```

Install cron explicitly:

```bash
python scripts/schedule_dashboard.py --install-cron --yes
```

The default schedule is 8 AM and 8 PM local time. Scheduled jobs run:

```bash
python install.py --real
```

## Logs

- Server log: `.local/server.log`
- Scheduler log: `.local/scheduler.log`

Both are ignored by git.

## Security posture

- No network dependencies.
- Server binds only to `127.0.0.1`.
- Non-loopback binding is blocked unless explicitly allowed.
- No package installation.
- No background daemon is installed unless the user explicitly installs a schedule.
- Static file serving is restricted to `web/` and `data/generated/`.
- Directory listing is disabled.
- Refresh and shutdown APIs require a random quickstart token when tokenized mode is used.
- Browser security headers are set for CSP, frame blocking, MIME sniffing, and referrer policy.
