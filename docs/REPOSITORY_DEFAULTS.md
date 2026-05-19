# Repository Defaults

Use these defaults for local-first portfolio projects unless a repo has a good reason to differ.

## Required Files

- `README.md` with table of contents, screenshots, directory structure, file guide, run modes, verification, and limitations
- `LICENSE`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `.gitignore`
- `.github/workflows/ci.yml`
- `.github/dependabot.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/`

## Security Defaults

- Keep generated local data and runtime state ignored by git.
- Use synthetic fixtures and screenshots for public docs.
- Run checks for all committed artifact types, not only the primary language.
- Add new artifact types to the repo-wide checker before committing them.
- Prefer explicit allowlists over broad scans.
- Avoid remote runtime dependencies unless they are explicitly approved and documented.

## GitHub Defaults

- Enable CI for linting, tests, privacy audit, and artifact security checks.
- Enable CodeQL code scanning for supported languages. Prefer GitHub default setup when available; use a custom CodeQL workflow only when default setup is not enabled.
- Enable Dependabot for GitHub Actions and Python dependency metadata.
- Use private vulnerability reporting when available.
- Add issue and pull-request templates that remind contributors not to include secrets, logs, real generated data, or conversation content.

## Documentation Defaults

- Add Mermaid diagrams for architecture, lifecycle, trust boundaries, parser flow, and metric interpretation when they improve clarity.
- Include a reusable Codex prompt when the repo is intended as a pattern others can adapt.
- Document exactly what data is read and what data is written.
