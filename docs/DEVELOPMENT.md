# Development

## Virtual environment

This project has no runtime dependencies, but development uses Pipenv for repeatable linting, type checks, tests, and security checks.

Create the environment:

```bash
pipenv --python 3.12
pipenv install --dev
```

Run all local checks:

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

`scripts/check_repo_security.py` is the all-artifacts guardrail. It checks more than Python: Markdown, shell wrappers, batch files, HTML, CSS, JavaScript, JSON/JSONL/TOML/lock files, PNG screenshot assets, and expected executable modes.

GitHub also runs these checks through `.github/workflows/ci.yml`, and CodeQL scanning is configured in `.github/workflows/codeql.yml`.

## Sample screenshots

The README screenshots are generated from synthetic sample data:

```bash
python install.py --sample --project-names
```

Open `web/index.html?theme=light` and `web/index.html?theme=dark`, then capture `docs/assets/dashboard-sample-light.png` and `docs/assets/dashboard-sample-dark.png`.

## macOS quickstart permissions

`quickstart.command` must be executable for Finder double-click launch:

```bash
chmod +x quickstart.command quickstart.sh
```

If macOS Gatekeeper adds quarantine metadata after downloading a zip, remove it locally:

```bash
xattr -d com.apple.quarantine quickstart.command
```

Do not run that command on files you do not trust.
