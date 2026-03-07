# nightly-evolution — SPEC

## Background

A recurring nightly instance that performs autonomous workspace maintenance and improvement. Runs every night via cron, resets and re-executes all tasks each cycle.

## Iron Rules

- No config file modifications (openclaw.json, launchd plists, etc.)
- Write knowledge docs in Chinese (通俗易懂), code in English
- Each task produces exactly ONE output file
- All tasks must complete within worker_timeout (180s recommended)
- This is a RECURRING instance — all tasks reset to pending each night

## Goals

1. Keep workspace files healthy and synchronized
2. Distill daily notes into long-term memory
3. Track community developments and new tools
4. Auto-commit and push workspace changes

## Phase 0: Workspace Scan

| ID  | Title           | Depends On | Output              |
|-----|-----------------|------------|----------------------|
| 0.1 | Workspace scan  | —          | `workspace-scan.md`  |

Scan all workspace directories, note file counts, recent changes, anomalies.

## Phase 1: Core Review

| ID  | Title              | Depends On | Output                 |
|-----|--------------------|------------|------------------------|
| 1.1 | Core files review  | 0.1        | `review-core.md`       |
| 1.2 | Playbooks review   | 0.1        | `review-playbooks.md`  |
| 1.3 | Symlink check      | 0.1        | _(inline in task log)_ |
| 1.4 | Script/cron health | 0.1        | `review-health.md`     |

## Phase 2: Memory Distillation

| ID  | Title                    | Depends On | Output                   |
|-----|--------------------------|------------|--------------------------|
| 2.1 | Daily notes → MEMORY.md  | 1.1        | `distill-memory.md`      |
| 2.2 | SHARED-FACTS sync        | 2.1        | `sync-shared-facts.md`   |

## Phase 3: Community Research

| ID  | Title                | Depends On | Output                    |
|-----|----------------------|------------|---------------------------|
| 3.1 | OpenClaw ecosystem   | —          | `community-openclaw.md`   |
| 3.2 | AI/LLM news          | —          | `community-ai.md`         |
| 3.3 | Vertical research    | —          | `community-vertical.md`   |

## Phase 4: Wrap Up

| ID  | Title              | Depends On       | Output          |
|-----|--------------------|------------------|-----------------|
| 4.1 | Git commit + push  | 2.2              | `git-push.md`   |
| 4.G | Gate: Summary      | 4.1, 3.1, 3.2, 3.3 | `summary.md` |

Gate: compile summary of all findings, send Discord notification.

## Output Structure

```
workspace-scan.md
review-core.md
review-playbooks.md
review-health.md
distill-memory.md
sync-shared-facts.md
community-openclaw.md
community-ai.md
community-vertical.md
git-push.md
summary.md
```
