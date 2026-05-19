# Metrics Guide

## Reading the dashboard

Use the time-range toggle to compare the latest 7 days, 1 month, 6 months, or 1 year. The dashboard keeps the generated data full-history locally and filters the cards, charts, breakdowns, deep dive, and largest sessions in the browser.

```mermaid
flowchart TD
    totals["High total tokens"] --> complexity["Complex task, long context, or repeated loop"]
    complexity --> review["Review largest sessions"]
    review --> reuse["Create docs, memory, prompt, script, or skill"]

    cache["Cache ratio"] --> cacheHigh{"Higher over time?"}
    cacheHigh -->|"Yes"| stable["Stable reusable context is working"]
    cacheHigh -->|"No"| setup["Repeated setup may be leaking effort"]

    ratio["Output/input ratio"] --> style{"Work style"}
    style -->|"High"| generation["Generation-heavy writing or implementation"]
    style -->|"Low"| exploration["Context-heavy debugging, review, or discovery"]

    turns["Turns per session"] --> loop["Iteration rhythm"]
    loop --> action["Improve tests, instructions, examples, or task framing"]
```

## Total tokens

Total tokens are a rough measure of how much context Codex processed and generated. High days are not automatically bad; they usually mark complex implementation, long debugging loops, or large reviews.

Daily totals are calculated from token metadata events by timestamp. Session totals remain the latest cumulative total for that session. This distinction avoids assigning a long-running session's full usage to only its start date.

## Input tokens

Input tokens estimate how much context Codex had to read. If input is high while output is low, the work may have involved exploration, debugging, or repeated context loading.

## Cached input tokens

Cached input tokens indicate context reuse. A higher cache ratio often means Codex is reusing stable context instead of paying the full context cost every turn.

## Output tokens

Output tokens estimate how much Codex generated. High output can mean code generation, documentation, summaries, or large explanations.

## Output/input ratio

This ratio helps identify the style of work:

- Higher ratio: generation-heavy work.
- Lower ratio: context-heavy work, often debugging or review.
- Middle ratio: balanced collaboration.

## Sessions and turns

Sessions show work blocks. Turns show conversational iteration. A large number of turns can mean useful refinement, but it can also signal that the task could benefit from clearer project context or a reusable workflow.

## Largest sessions

Largest sessions are the best places to look for ROI. A repeated high-token workflow may be a candidate for:

- a better README or AGENTS.md section
- a durable memory note
- a reusable prompt
- a local script
- a Codex skill

## Memory reuse signals

The dashboard looks for metadata-only evidence that memory was used and for repeated high-token project activity. The goal is not to score the developer; it is to identify where a small investment in reusable context could reduce future effort.

## Developer self-improvement

Use the dashboard to ask:

- Which projects repeatedly require the most context?
- Are high-token sessions producing reusable assets?
- Is cache reuse improving over time?
- Are long loops caused by missing tests, unclear docs, or scattered project knowledge?
- Would a memory, project guide, or skill reduce repeated setup?

## Project names

By default the dashboard uses redacted project labels. Use `--project-names` to show only the basename of each project path. Raw full paths still stay out of generated data unless you explicitly choose `--no-redact-paths`.
