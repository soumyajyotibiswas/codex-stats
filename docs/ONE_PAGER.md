# Codex Usage Dashboard One Pager

## What it is

Codex Usage Dashboard is a local analytics project for understanding Codex usage patterns from local session metadata. It turns token metadata into a static dashboard with daily charts, session tables, project/model breakdowns, cache effectiveness, and memory reuse signals.

The dashboard is designed to answer a practical question: where is Codex saving time, and where are repeated high-context workflows asking for better reusable context?

## Who it is for

- Individual Codex users who want private usage visibility.
- Developers who want a portfolio-quality local analytics project.
- Teams that want a reusable pattern for privacy-preserving local telemetry.

## What it does not do

- It does not upload data.
- It does not call external APIs.
- It does not use trackers or remote CDNs.
- It does not persist prompt, response, or conversation text.
- It does not run as a background daemon.

## Why it matters

Codex usage data is useful for understanding personal workflows, cache effectiveness, and high-token repeated work that could benefit from better memory or skills. This project makes those signals visible without creating a new privacy risk.

## How it creates value

- Identifies repeated high-token work that may deserve a memory, project guide, or skill.
- Shows whether context reuse is improving through cached input tokens.
- Highlights largest sessions so developers can review where time and attention went.
- Separates generation-heavy work from context-heavy debugging and exploration.

## Run it

```bash
python install.py --sample --start-server
python install.py --real --start-server
```
