# Evo — Evolution Loop Framework for OpenClaw

A task orchestration framework that breaks complex projects into phased, dependency-tracked tasks executed by AI agents. Built for [OpenClaw](https://github.com/openclaw/openclaw).

## How It Works

```
SPEC.md → Planner → tasks.json → Worker Loop → Output Files
              ↑                        ↓
              └─── Gate Pass ──────────┘
```

1. **You** write a `SPEC.md` defining phases, tasks, and gates
2. **Planner** (AI) converts the spec into structured `tasks.json`
3. **Worker Loop** picks tasks by dependency order, executes them via OpenClaw agent or Claude CLI
4. **Gates** validate phase completion before unlocking the next phase
5. **Circuit breaker** pauses after consecutive failures; **auto-escalation** after repeated task failures

## Features

- 🔄 **Phased execution** — tasks organized by phase, gates control progression
- 🔀 **Multi-runner** — `agent` (full tools, API tokens), `claude` / `codex` / `gemini` (coding CLIs, subscription plans)
- 🛡️ **Anti-stuck mechanisms** — L0 stale reset, L0.5 deadlock breaker, L0.75 auto-escalation
- 📊 **Budget control** — daily task limits prevent runaway costs
- 🔔 **Discord notifications** — gate passes, completions, circuit breakers (optional)
- 📦 **GitHub archiving** — auto-archive completed instances (optional)
- 🔁 **Recurring instances** — template-based reset for nightly/periodic tasks
- 📋 **Structured logging** — JSONL task logs + worker logs with rotation

## Requirements

- [OpenClaw](https://github.com/openclaw/openclaw) installed and running
- Python 3.8+
- Bash 4+
- (Optional) `gh` CLI for GitHub archiving
- (Optional) `claude` CLI for dual-runner mode

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USER/evo.git ~/.openclaw/evo

# Make CLI executable
chmod +x ~/.openclaw/evo/framework/evo

# Add to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.openclaw/evo/framework:$PATH"

# (Optional) Configure environment
cp ~/.openclaw/evo/framework/.env.example ~/.openclaw/evo/.env
# Edit .env with your settings
```

## Quick Start

### 1. Create an Instance

```bash
evo create my-research "Research project on topic X"
```

This creates `~/.openclaw/evo/instances/my-research/` with:
- `SPEC.md` — project specification (edit this!)
- `tasks.json` — task registry (auto-managed)
- `state.json` — runtime state

### 2. Write Your SPEC

Edit `~/.openclaw/evo/instances/my-research/SPEC.md`:

```markdown
# my-research — SPEC

## Background
Researching the feasibility of using LLMs for code analysis.

## Goals
1. Survey existing tools and approaches
2. Design a prototype architecture
3. Estimate costs and timelines

## Phase 0: Knowledge Building
| ID  | Title              | Depends On | Output                  |
|-----|--------------------|------------|-------------------------|
| 0.1 | Survey LLM tools   | —          | `knowledge/llm-tools.md`|
| 0.2 | Survey code analyzers | —       | `knowledge/analyzers.md`|
| 0.G | Gate: Phase 0 done | 0.1, 0.2   | —                       |

## Phase 1: Design
| ID  | Title              | Depends On | Output                  |
|-----|--------------------|------------|-------------------------|
| 1.1 | Architecture design| 0.G        | `output/architecture.md`|
| 1.G | Gate: Phase 1 done | 1.1        | —                       |
```

### 3. Plan & Start

```bash
# Generate tasks from SPEC (runs AI planner)
evo plan my-research

# Start the worker loop
evo start my-research

# Monitor progress
evo status my-research

# Watch logs
evo logs my-research --follow
```

### 4. Check Results

```bash
evo status my-research
# ✅ 0.1 Survey LLM tools
# ✅ 0.2 Survey code analyzers
# ✅ 0.G Gate: Phase 0 done [GATE]
# 🔵 1.1 Architecture design
# ⬜ 1.G Gate: Phase 1 done [GATE]
```

Output files appear in `instances/my-research/knowledge/` and `instances/my-research/output/`.

## Examples

### Example 1: Research Project

See [examples/research-project/](examples/research-project/) — a one-shot research instance that surveys a topic, synthesizes findings, and produces a report.

```bash
# Create from the example
cp -r examples/research-project ~/.openclaw/evo/instances/my-research
evo plan my-research
evo start my-research
```

### Example 2: Recurring Nightly Tasks

See [examples/nightly-evolution/](examples/nightly-evolution/) — a recurring instance that runs every night: scans workspace files, reviews configs, distills memory, researches community updates.

```bash
# Install template
cp examples/nightly-evolution/tasks.json \
   ~/.openclaw/evo/framework/templates/nightly-evolution/tasks.json

# Create instance from template
cp -r examples/nightly-evolution ~/.openclaw/evo/instances/nightly-evolution

# Set up cron (runs at 2:30 AM daily)
# In OpenClaw cron:
#   evo reset nightly-evolution && evo start nightly-evolution
```

For recurring instances, `evo reset` rebuilds tasks from the template:

```bash
# Reset all tasks to pending (uses template if available)
evo reset nightly-evolution

# Force reset even if worker is running
evo reset nightly-evolution --force
```

### Example 3: Batch Processing (auto_split)

See [examples/batch-processing/](examples/batch-processing/) — demonstrates `auto_split` for runtime task expansion. Task 0.1 scans files and produces a list; task 1.1 auto-splits into sub-tasks based on the list size.

```bash
cp -r examples/batch-processing ~/.openclaw/evo/instances/my-batch
# Edit SPEC.md to match your use case
evo start my-batch
```

**Key task in tasks.json:**

```json
{
  "id": "1.1",
  "title": "处理所有文件",
  "auto_split": {
    "items_file": "output/file-list.txt",
    "batch_size": 5,
    "output_prefix": "output/processed"
  }
}
```

If `file-list.txt` has 12 items with `batch_size: 5`, the worker automatically creates:
- `1.1.1` — items 1-5 → `output/processed.1.md`
- `1.1.2` — items 6-10 → `output/processed.2.md`
- `1.1.3` — items 11-12 → `output/processed.3.md`
- `1.1` becomes a gate waiting for all sub-tasks

## CLI Reference

| Command | Description |
|---------|-------------|
| `evo create <name> "<desc>"` | Create new instance with scaffolding |
| `evo start <name>` | Start the worker loop (background) |
| `evo stop <name>` | Stop the worker loop |
| `evo status [name]` | Show status (all instances or one) |
| `evo status --json` | Machine-readable status output |
| `evo logs <name> [--follow]` | View worker logs |
| `evo plan <name>` | Run the AI planner |
| `evo reset <name> [--force]` | Reset tasks to pending |
| `evo integrate <name>` | Show output routing suggestions |
| `evo health` | System health check (JSON) |
| `evo destroy <name>` | Stop + move to trash |
| `evo bootstrap` | Restore active instances after reboot |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EVO_ROOT` | `~/.openclaw/evo` | Base directory |
| `EVO_DISCORD_CHANNEL` | _(none)_ | Discord channel ID for notifications |
| `EVO_MENTION` | _(none)_ | Discord mention, e.g. `<@USER_ID>` |
| `EVO_ARCHIVE_REPO` | _(none)_ | GitHub repo for archiving completed instances |
| `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace` | OpenClaw workspace path |

Set these in `~/.openclaw/evo/.env` (auto-loaded by CLI).

### state.json Fields

| Field | Default | Description |
|-------|---------|-------------|
| `worker_model` | `sonnet` | Model for worker tasks |
| `planner_model` | `opus` | Model for planner |
| `worker_agent` | `evo` | OpenClaw agent ID for `agent` runner |
| `worker_timeout` | `600` | Timeout per task (seconds) |
| `budget_daily` | `50` | Max tasks per day |
| `recurring` | `false` | Whether instance supports `evo reset` from template |

### Task Runner Selection

Each task has a `runner` field:

- **`agent`** — Runs via `openclaw agent`. Full tools: web_search, web_fetch, plugins. Uses API tokens. Best for research tasks needing internet or plugins.
- **`claude`** — Runs via `claude -p`. Local tools (Bash, Read, Write, Edit). Uses Claude subscription. Faster, cheaper. Good for code generation, gates.
- **`codex`** — Runs via `codex exec`. Local tools + optional web search (auto-enabled for research tasks). Uses OpenAI/Codex subscription. Full-auto, full disk access. Good for code generation, refactoring.
- **`gemini`** — Runs via `gemini -p`. Local tools in sandbox. Uses Gemini subscription. Yolo (auto-approve) mode. Good for code generation, analysis, writing.

> **Cost tip**: Prefer `claude`/`codex`/`gemini` over `agent` when the task doesn't need web access or OpenClaw plugins — they use subscription plans instead of API tokens.

## Directory Structure

```
~/.openclaw/evo/
├── .env                          # Your local config (gitignored)
├── .gitignore
├── framework/
│   ├── evo                       # CLI entry point
│   ├── CLAUDE.md                 # Worker context instructions
│   ├── .env.example              # Config template
│   ├── scripts/
│   │   ├── worker-loop.sh        # Main execution loop
│   │   ├── planner.sh            # AI planner
│   │   ├── pick_next_task.py     # Task selection + anti-stuck
│   │   ├── expand_task.py        # Auto-split task expansion
│   │   ├── check_budget.py       # Daily budget enforcement
│   │   ├── log_task.py           # Structured JSONL logging
│   │   ├── reporter.sh           # Status reporting
│   │   ├── health_check.sh       # System health (JSON)
│   │   ├── integrate.sh          # Output routing suggestions
│   │   ├── notify-discord.sh     # Discord notifications
│   │   └── archive-to-github.sh  # GitHub archiving
│   └── templates/
│       ├── SPEC.md.template
│       ├── tasks.json.template
│       └── state.json.template
├── instances/
│   └── <instance-name>/
│       ├── SPEC.md
│       ├── tasks.json
│       ├── state.json
│       ├── knowledge/
│       ├── output/
│       └── logs/
└── examples/
    ├── research-project/         # One-shot research
    ├── nightly-evolution/        # Recurring nightly tasks
    └── batch-processing/         # Auto-split demo
```

## Auto-Split: Dynamic Task Expansion

When a task's workload depends on a previous task's output (e.g., "process N documents" where N is unknown at plan time), use `auto_split` to automatically split it into sub-tasks at runtime.

### How It Works

```
Task 0.1 produces file-list.txt (N items)
    ↓
Task 1.1 has auto_split → worker reads file-list.txt
    ↓ N > batch_size?
    ├── Yes → split into 1.1.1, 1.1.2, ... sub-tasks
    │         1.1 becomes a gate depending on all sub-tasks
    └── No  → execute 1.1 normally (no split)
    ↓
Task 2.1 depends on 1.1 (gate) → runs after all sub-tasks complete
```

### Task Schema

Add `auto_split` to any task in `tasks.json`:

```json
{
  "id": "1.1",
  "title": "Process all documents",
  "depends_on": ["0.1"],
  "auto_split": {
    "items_file": "output/file-list.txt",
    "batch_size": 5,
    "output_prefix": "output/processed"
  },
  "output_files": ["output/processed.md"]
}
```

| Field | Description |
|-------|-------------|
| `items_file` | Path to a newline-delimited file (one item per line), produced by upstream task |
| `batch_size` | Max items per sub-task (tune to stay within `worker_timeout`) |
| `output_prefix` | Output file prefix; sub-tasks produce `{prefix}.1.md`, `{prefix}.2.md`, ... |

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| `items_file` not found | Task marked `failed` |
| 0 items | Gate marked `done` immediately |
| N ≤ batch_size | No split, task executes normally |
| Sub-task fails | L0/L0.5/L0.75 handle retries; gate won't pass until all sub-tasks done |

### Example

See [examples/batch-processing/](examples/batch-processing/) — a project that scans files, auto-splits processing into batches, then summarizes results.

## Anti-Stuck Mechanisms

| Level | Trigger | Action |
|-------|---------|--------|
| L0 | Task `in_progress` > 15 min | Reset to `pending`, increment attempts |
| L0.5 | All pending tasks blocked by failed deps | Reset failed deps or trigger planner |
| L0.75 | Task attempts ≥ 5 | Auto-escalate, trigger planner to redesign |
| Circuit Breaker | 5 consecutive failures | Pause 1 hour, notify Discord |

## License

MIT
