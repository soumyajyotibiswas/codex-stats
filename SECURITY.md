# Security Policy

## Supported Versions

This project is a small local-first tool. Security fixes are supported on the default branch.

## Reporting A Vulnerability

Please report suspected vulnerabilities through GitHub private vulnerability reporting if it is enabled on the repository. If private reporting is not available, open a GitHub issue with a minimal description and avoid posting secrets, tokens, raw local usage data, or conversation content.

Useful report details:

- affected command or file
- operating system
- expected behavior
- observed behavior
- whether generated local data may be involved

## Data Boundary

This project is designed to stay local:

- no uploads
- no trackers
- no remote runtime dependencies
- no prompt or response text persisted
- generated real usage data ignored by git

Do not include real `data/generated/` output, `.local/` state, logs, secrets, browser profiles, credential stores, `.env` files, SSH keys, or production credentials in vulnerability reports.

## Maintainer Checklist

Before publishing changes, run:

```bash
pipenv run ruff format --check .
pipenv run ruff check .
pipenv run pyright
pipenv run bandit -r install.py scripts -c pyproject.toml
pipenv run pip-audit
pipenv run python -m unittest discover -s tests
pipenv run python scripts/privacy_audit.py --forbid SYNTHETIC_PROMPT_TEXT_SHOULD_NOT_APPEAR
pipenv run python scripts/check_repo_security.py
node --check web/app.js
sh -n quickstart.command quickstart.sh install.sh
git diff --check
```
