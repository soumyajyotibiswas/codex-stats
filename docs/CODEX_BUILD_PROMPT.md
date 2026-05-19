# Reusable Codex Build Prompt

Copy this prompt into Codex when you want to recreate or adapt this project in a new local repository. It is intentionally generic and contains no private user names, company names, local absolute paths, real usage metrics, secrets, or machine-specific details.

```text
You are Codex working on my local machine.

Goal:
Build a local-first, privacy-preserving "AI Usage Dashboard" as a small self-hosted portfolio-quality project. It should parse local AI assistant session metadata, generate daily usage metrics, and render a polished local HTML dashboard with charts, tables, and useful insights.

Safety rules:
- Do not read, print, summarize, or export conversation content.
- Only parse metadata needed for usage analytics.
- Never read secrets, API keys, tokens, .env files, SSH keys, browser profiles, credential stores, or production credentials.
- Do not upload data anywhere.
- Do not use network access unless I explicitly approve it.
- Do not deploy, publish, push, email, message, or configure external services.
- Keep everything local.
- Prefer explicit allowlists over broad scans.
- Keep diffs small and reviewable.
- Ask before installing dependencies.
- If a command would be destructive, ask first.

Suggested local metadata roots:
- ~/.codex/sessions
- ~/.codex/archived_sessions

The local JSONL records may include token metadata like:
- payload.info.total_token_usage.input_tokens
- payload.info.total_token_usage.cached_input_tokens
- payload.info.total_token_usage.output_tokens
- payload.info.total_token_usage.total_tokens
- payload.info.last_token_usage.*

Use those metadata fields only. Do not inspect or display prompt/response text.

Project:
Create a git repository for this project in a user-chosen local folder. Build a simple local project that can be opened directly in a browser, with VS Code Live Server, or through a tiny local Python static server.

Preferred stack:
- Python standard library for the parser/server.
- Static HTML/CSS/JavaScript for the dashboard.
- No remote CDN dependencies.
- No runtime package dependencies unless I approve them.
- Use plain SVG/canvas charts unless I approve a chart library.

Before making edits, show me:
- proposed repo path
- proposed file tree
- data fields to extract
- files that will be read
- files that will be written
- risks and assumptions

Process:
1. Plan.
2. Inspect only local metadata file structure safely.
3. Build tests using synthetic JSONL fixtures.
4. Implement the parser.
5. Generate JSON and CSV outputs.
6. Build the dashboard.
7. Add local server and quickstart options.
8. Add scheduled refresh command generation without installing anything by default.
9. Add docs and security notes.
10. Run verification and iterate.

Deliverables:
- README.md
- docs/ONE_PAGER.md
- docs/PROJECT_PLAN.md
- docs/TECHNICAL_DESIGN.md
- docs/IMPLEMENTATION_PLAN.md
- docs/SECURITY_AND_PRIVACY.md
- docs/USAGE.md
- docs/METRICS_GUIDE.md
- docs/OPERATIONS.md
- docs/DEVELOPMENT.md
- docs/REPOSITORY_DEFAULTS.md
- scripts/build_usage_data.py
- scripts/serve_dashboard.py
- scripts/schedule_dashboard.py
- scripts/privacy_audit.py
- scripts/check_repo_security.py
- data/generated/codex_usage_summary.json
- data/generated/codex_usage_daily.csv
- data/generated/codex_usage_sessions.csv
- web/index.html
- web/styles.css
- web/app.js
- tests/fixtures/*.jsonl
- tests/sample_data/*.jsonl
- tests/test_*.py
- install.py
- install.sh
- quickstart.command
- quickstart.sh
- quickstart.bat
- SECURITY.md
- CONTRIBUTING.md
- LICENSE
- .github/workflows/ci.yml
- .github/workflows/codeql.yml
- .github/dependabot.yml
- .github/pull_request_template.md
- .github/ISSUE_TEMPLATE/bug_report.yml
- .github/ISSUE_TEMPLATE/feature_request.yml
- .github/ISSUE_TEMPLATE/config.yml
- .gitignore

Dashboard requirements:
- Total tokens by day.
- Input tokens by day.
- Cached input tokens by day.
- Output tokens by day.
- Daily sessions count.
- Daily turns count if available.
- Largest sessions by total tokens.
- Project/cwd breakdown if available in metadata.
- Model breakdown if available in metadata.
- Cache effectiveness: cached_input_tokens / input_tokens.
- Output/input ratio.
- Rolling 7-day totals.
- Time-range toggle for latest 7 days, 1 month, 6 months, and 1 year.
- Memory reuse signals:
  - sessions that cite memory, if detectable from metadata only
  - high-token repeated project sessions
  - candidates for future memory/skill creation
- Data freshness card:
  - last parsed timestamp
  - number of files scanned
  - number of sessions parsed
  - number of records skipped
- Privacy status card:
  - confirms content fields are ignored
  - confirms only metadata was extracted
- Day/night theme toggle.
- Help button that can display script help when served locally.
- Hoverable charts.
- Responsive layout.

Metric meaning:
Make the dashboard understandable for a layperson. Add plain-English insight cards and a metrics guide explaining:
- what each metric means
- why high token days are not automatically bad
- when repeated high-token sessions suggest better docs, memory, prompts, scripts, or skills
- how cache ratio reflects context reuse
- how output/input ratio separates generation-heavy work from context-heavy debugging or review

Parser requirements:
- Read only from explicit allowed roots by default:
  - ~/.codex/sessions
  - ~/.codex/archived_sessions
- Support explicit --input-root for tests and controlled local experiments.
- Parse JSONL defensively.
- Skip malformed records and count them.
- Extract only allowed metadata fields.
- Do not persist raw message content.
- Do not include full file paths by default.
- Add --redact-paths by default.
- Add --project-names to show basename-only project labels while keeping raw paths redacted.
- Add --no-redact-paths only as an explicit local opt-in.
- Include --dry-run or summary mode.
- Include deterministic synthetic fixtures.

Suggested session metrics:
- session_id
- source_file
- date
- first_timestamp
- last_updated_at
- project
- cwd, only when no redaction is explicitly requested
- model
- input_tokens
- cached_input_tokens
- output_tokens
- total_tokens
- turn_count
- token_events_count
- max_single_turn_total_tokens
- memory_citation_detected

Suggested daily metrics:
- date
- sessions
- turns
- usage_events
- input_tokens
- cached_input_tokens
- output_tokens
- total_tokens
- cache_ratio
- output_input_ratio
- rolling_7_day_total_tokens
- max_single_turn_total_tokens

Local server requirements:
- Bind to 127.0.0.1 by default.
- Refuse non-loopback hosts unless explicitly allowed.
- Serve only web/ and data/generated/.
- Disable directory listing.
- Block path traversal and hidden files.
- Add CSP, frame blocking, MIME sniffing, referrer policy, and cache-control headers.
- Use fixed subprocess argument lists, not shell command strings.
- Use a random quickstart token for local API calls.
- Add start/status/stop commands.
- Quickstart should open the dashboard and auto-shutdown after page close when possible.
- Document that auto-shutdown is best effort and provide a stop command.

Security checks:
- Add tests for parser behavior and server path validation.
- Add a generated-data privacy audit that fails if forbidden text appears in generated outputs.
- Add a repo-wide security checker for all committed artifact types, not only Python.
- Check Python formatting/linting/types if dev tools are installed.
- Check shell scripts with sh -n.
- Check JavaScript syntax with node --check when Node is available.
- Check for secret-like patterns and local absolute paths in committed files.
- Ensure generated real usage data and local server state are gitignored.

Documentation requirements:
- README with table of contents, screenshots from synthetic sample data, directory structure, file guide, quickstart, run modes, security checks, and limitations.
- Technical design document with Mermaid diagrams for architecture, parser flow, data model, and server lifecycle.
- Security and privacy document with trust-boundary diagram.
- Metrics guide with metric-to-action diagram.
- Usage and operations docs.
- Development docs with all local verification commands.
- Repository defaults doc covering security policy, license, contributing guide, CI, CodeQL, Dependabot, and all-artifact security checks.

Verification:
Run or document results for:
- parser on synthetic fixture
- parser on real local metadata with redaction
- unit tests
- generated-data privacy audit
- repo-wide artifact security check
- Python lint/type/security checks if configured
- JavaScript syntax check if Node is available
- shell syntax checks
- local server start/status/fetch/stop smoke test
- git status showing generated real data is ignored

Final response:
Summarize:
- files created
- commands run
- verification results
- privacy/security posture
- known limitations
- suggested next steps
```
