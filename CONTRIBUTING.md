# Contributing

Thanks for improving Codex Usage Dashboard.

## Development Setup

```bash
pipenv --python 3.12
pipenv install --dev
```

Generate safe sample data:

```bash
python install.py --sample --project-names
```

Run real local parsing only on your own machine:

```bash
python install.py --real --project-names
```

## Privacy Rules

- Do not commit `data/generated/`.
- Do not commit `.local/`.
- Do not add real prompt, response, or conversation content to tests or docs.
- Use synthetic fixtures and synthetic screenshots for public examples.
- Keep parser changes metadata-only unless a future design explicitly documents a different boundary.

## Pull Request Checklist

- Tests pass.
- Repo-wide security check passes.
- Public screenshots use synthetic data.
- New files are documented when they are user-facing.
- Any new artifact type is added to `scripts/check_repo_security.py`.

## Local Checks

```bash
pipenv run ruff format --check .
pipenv run ruff check .
pipenv run pyright
pipenv run bandit -r install.py scripts -c pyproject.toml
pipenv run python -m unittest discover -s tests
pipenv run python scripts/privacy_audit.py --forbid SYNTHETIC_PROMPT_TEXT_SHOULD_NOT_APPEAR
pipenv run python scripts/check_repo_security.py
node --check web/app.js
sh -n quickstart.command quickstart.sh install.sh
git diff --check
```
