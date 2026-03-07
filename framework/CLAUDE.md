# Evolution Worker Context

You are executing a task inside an Evolution Loop instance.

## Runner Modes

Tasks have a `runner` field that determines execution environment:

- **`agent`** (default) — Runs via `openclaw agent`. Full tools: web_search, web_fetch, memory, plugins, Bash, Read/Write/Edit. Use for research, fetching URLs, anything needing internet.
- **`claude`** — Runs via `claude -p`. Local tools only: Bash, Read/Write/Edit. Faster, no session overhead. Use for code generation, writing docs from existing context, gates.

## Available Tools (agent mode)

- **web_search** — Search the web (Brave API). USE THIS for research tasks!
- **web_fetch** — Fetch and extract content from URLs
- **exec** (Bash) — Run shell commands, create files, execute code
- **Read / Write / Edit** — File operations
- **memory_search** — Search agent memory for context

## Rules

1. Read your task instructions carefully. Produce the output file(s) specified.
2. After completing work, update tasks.json:
   - Set your task's `status` to `"done"` and `completed_at` to current ISO timestamp
   - If you're a gate task and the condition passes, also set `planner_trigger: true`
   - Update `summary` counts
   - Use atomic write: write to tmpfile, then `os.rename()`
3. If you cannot complete the task, set `status` to `"failed"` with an `error` message.
4. Do NOT modify other tasks. Only update your assigned task.
5. All file paths are relative to the instance directory (your cwd).
6. Keep output files clean and well-structured.

## Research Quality Standards

- **USE web_search** to find real papers, products, benchmarks. Do NOT fabricate citations.
- For Chinese docs: 通俗易懂, 用形象的例子解释概念
- For code: English comments, runnable, well-structured
- Include sources and references where applicable
- Dependency outputs are injected into your prompt — use them as context, don't repeat them
