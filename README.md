# Evo — Evolution Loop Framework for OpenClaw

A task orchestration framework that breaks complex projects into phased, dependency-tracked tasks executed by AI agents. Built for [OpenClaw](https://github.com/openclaw/openclaw).

## How It Works

```
SPEC.md → Parser/Planner → tasks.json → Worker Loop → Output Files
                ↑                            ↓
                └────── Gate Pass ───────────┘
```

1. **You** write a `SPEC.md` defining phases, tasks, and gates
2. **Parser** deterministically converts structured `## Tasks` section into `tasks.json` — no LLM, instant. Falls back to AI planner for unstructured specs.
3. **Worker Loop** picks tasks by dependency order, executes them via configurable runners (codex, claude, gemini, or OpenClaw agent)
4. **Gates** validate phase completion before unlocking the next phase
5. **Circuit breaker** pauses after consecutive failures; **auto-escalation** after repeated task failures

## Features

- 🔄 **Phased execution** — tasks organized by phase, gates control progression
- 🔀 **Multiple runner types** — `agent` (full tools, API tokens), `claude` / `codex` / `gemini` (coding CLIs, subscription plans)
- ⚡ **Parallel workers** — run multiple worker loops concurrently to speed up independent tasks
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

### Install the OpenClaw Agent Skill

Evo ships with an OpenClaw agent skill at `framework/skills/evo/`. To let your agent discover and use evo commands in conversation, symlink it into the agent's workspace:

```bash
# Symlink the skill into your OpenClaw workspace skills directory
ln -sf ~/.openclaw/evo/framework/skills/evo \
       "$(openclaw config get workspace 2>/dev/null || echo ~/.openclaw/workspace)/skills/evo"
```

Or if you know your workspace path:

```bash
ln -sf ~/.openclaw/evo/framework/skills/evo ~/.openclaw/workspace/skills/evo
```

After symlinking, the agent will automatically discover the `evo` skill and can create instances, run plans, start workers, and monitor progress through natural conversation.

> **For agents reading this README**: to install the skill programmatically, run the symlink command above. The skill source lives in this repo and stays in sync — no manual updates needed.

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

> **💡 Best Practice: Let your agent write the SPEC for you.**
>
> Instead of writing `SPEC.md` from scratch, describe your goal to your OpenClaw agent (or any AI assistant) and let it generate the SPEC. A good workflow:
>
> 1. Tell your agent: *"I want to research X"* or *"Build me an evo instance for Y"*
> 2. The agent asks clarifying questions — scope, depth, constraints, output format preferences
> 3. The agent generates a complete `SPEC.md` with phases, tasks, dependencies, and gates
> 4. You review and adjust (manually or via the agent) until it looks right
> 5. Run `evo plan` to convert the SPEC into `tasks.json`
>
> This is faster, produces better-structured SPECs, and catches missing dependencies early.

Edit `~/.openclaw/evo/instances/my-research/SPEC.md`. Use the **structured task format** (recommended — deterministic, instant parsing, no LLM cost):

```markdown
# my-research — SPEC

## Background
Researching the feasibility of using LLMs for code analysis.

## Goals
1. Survey existing tools and approaches
2. Design a prototype architecture
3. Estimate costs and timelines

## Tasks

### 0.1 Survey LLM tools [agent]
> depends: -
> output: knowledge/llm-tools.md

Survey existing LLM-based code analysis tools. Cover:
- GitHub Copilot, Cursor, Cody, etc.
- Research papers on LLM + static analysis
Write findings to knowledge/llm-tools.md.

### 0.2 Survey code analyzers [agent]
> depends: -
> output: knowledge/analyzers.md

Survey traditional code analysis tools (Semgrep, CodeQL, tree-sitter).
Write findings to knowledge/analyzers.md.

### 0.G Gate: Phase 0 done [claude]
> depends: 0.1, 0.2

Verify knowledge/llm-tools.md and knowledge/analyzers.md exist and have >500 bytes each.

### 1.1 Architecture design [claude]
> depends: 0.G
> output: output/architecture.md

Read knowledge/*.md files. Design a prototype architecture.
Write to output/architecture.md.

### 1.G Gate: Phase 1 done [claude]
> depends: 1.1

Verify output/architecture.md exists and is well-structured.
```

See [framework/docs/SPEC-FORMAT.md](framework/docs/SPEC-FORMAT.md) for the full format specification.

### 3. Plan & Start

```bash
# Parse SPEC.md → tasks.json (instant, deterministic — no LLM)
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
| `evo start <name> [-w N]` | Start worker loop(s) (N=parallel workers) |
| `evo stop <name>` | Stop all worker loops |
| `evo status [name]` | Show status (all instances or one) |
| `evo status --json` | Machine-readable status output |
| `evo logs <name> [--follow] [--worker ID]` | View worker logs |
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
| `worker_model` | `sonnet` | Default model for all runners (fallback) |
| `claude_model` | _(none)_ | Model override for `claude` runner |
| `codex_model` | _(none)_ | Model override for `codex` runner |
| `gemini_model` | _(none)_ | Model override for `gemini` runner |
| `planner_model` | `opus` | Model for planner |
| `worker_agent` | `evo` | OpenClaw agent ID for `agent` runner |
| `worker_timeout` | `600` | Timeout per task (seconds) |
| `codex_workdir` | _(none)_ | Working directory for `codex` runner (project root) |
| `workers` | `1` | Number of parallel worker loops |
| `budget_daily` | `50` | Max tasks per day |
| `recurring` | `false` | Whether instance supports `evo reset` from template |

### Task Runner Selection

Each task has a `runner` field:

- **`agent`** — Runs via `openclaw agent`. Full tools: web_search, web_fetch, plugins. Uses API tokens. Best for research tasks needing internet or plugins.
- **`claude`** — Runs via `claude -p`. Local tools (Bash, Read, Write, Edit). Uses Claude subscription. Faster, cheaper. Good for code generation, gates.
- **`codex`** — Runs via `codex exec`. Local tools + optional web search (auto-enabled for research tasks). Uses OpenAI/Codex subscription. Full-auto, full disk access. Good for code generation, refactoring. Note: the `--model` flag is only passed for recognized OpenAI model names (e.g. `o3`, `o4-mini`, `gpt-4.1`); subscription aliases like `codex` omit it to avoid auth errors.
- **`gemini`** — Runs via `gemini -p`. Local tools in sandbox. Uses Gemini subscription. Yolo (auto-approve) mode. Good for code generation, analysis, writing.

> **Cost tip**: Prefer `claude`/`codex`/`gemini` over `agent` when the task doesn't need web access or OpenClaw plugins — they use subscription plans instead of API tokens.

#### Runner-Specific Model Override

Each runner can have its own model via `{runner}_model` in `state.json`:

```json
{
  "worker_model": "sonnet",
  "claude_model": "opus",
  "codex_model": "gpt-5.4",
  "gemini_model": "gemini-2.5-pro"
}
```

The resolution order is: `{runner}_model` → `worker_model` → `"sonnet"`. This prevents model name conflicts (e.g., Claude CLI doesn't recognize `codex` as a model name).

#### Runner-Aware Task Completion

Sandboxed runners (`codex`, `gemini`) cannot write back to the evo instance directory, so they don't receive `mark-task.sh` instructions. Instead, the worker loop's `verify_task` automatically detects completion by checking whether the task's output files exist — regardless of the worker's exit code. This handles edge cases like watchdog timeouts (SIGTERM/exit 143) where the work completed but the process was killed before status could be written back.

## Directory Structure

```
~/.openclaw/evo/
├── .env                          # Your local config (gitignored)
├── .gitignore
├── framework/
│   ├── evo                       # CLI entry point
│   ├── CLAUDE.md                 # Worker context instructions
│   ├── .env.example              # Config template
│   ├── docs/
│   │   └── SPEC-FORMAT.md        # Structured SPEC.md task format spec
│   ├── scripts/
│   │   ├── worker-loop.sh        # Main execution loop
│   │   ├── planner.sh            # AI planner (with deterministic fallback)
│   │   ├── spec2tasks.py         # Deterministic SPEC → tasks.json parser
│   │   ├── pick_next_task.py     # Task selection + anti-stuck
│   │   ├── expand_task.py        # Auto-split task expansion
│   │   ├── check_budget.py       # Daily budget enforcement
│   │   ├── log_task.py           # Structured JSONL logging
│   │   ├── reporter.sh           # Status reporting
│   │   ├── health_check.sh       # System health (JSON)
│   │   ├── integrate.sh          # Output routing suggestions
│   │   ├── notify-discord.sh     # Discord notifications
│   │   └── archive-to-github.sh  # GitHub archiving
│   ├── skills/
│   │   └── evo/
│   │       └── SKILL.md          # OpenClaw agent skill (auto-discovered)
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

## Parallel Workers

By default, each instance runs a single worker loop. For instances with many independent tasks, you can run multiple workers in parallel:

```bash
# Start with 3 parallel workers
evo start my-research --workers 3

# Or set default in state.json
# "workers": 3
```

Each worker independently picks tasks from the queue (`pick_next_task.py` uses file locking for safe concurrent access). Workers are fully crash-isolated — if one hangs or fails, others keep running.

```bash
# View status — shows all workers
evo status my-research
# Worker 1: running (PID 12345)
# Worker 2: running (PID 12346)
# Worker 3: running (PID 12347)

# View logs per worker
evo logs my-research --worker 2

# Follow all worker logs
evo logs my-research --follow

# Stop all workers
evo stop my-research
```

### When to Use

| Workers | Best for |
|---------|----------|
| 1 (default) | Sequential workflows, low-cost, simple |
| 2-3 | Instances with many independent tasks in the same phase |
| 4+ | Large batch processing with `auto_split` |

> **Note**: More workers doesn't help if tasks are strictly sequential (each depends on the previous). The speedup comes from independent tasks that can run in parallel.

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

## Deterministic Planner

`evo plan` now supports two modes:

1. **Deterministic parser** (default, recommended): If your `SPEC.md` contains a `## Tasks` section using the [structured format](framework/docs/SPEC-FORMAT.md), `spec2tasks.py` parses it directly into `tasks.json`. Instant, zero LLM cost, fully reproducible.

2. **AI planner** (fallback): If no `## Tasks` section is found, falls back to LLM-based planning. Slower (30s–5min) and costs tokens, but handles unstructured specs.

```bash
# Deterministic (instant) — requires structured ## Tasks in SPEC.md
evo plan my-instance

# Validate format without writing tasks.json
python3 ~/.openclaw/evo/framework/scripts/spec2tasks.py \
  ~/.openclaw/evo/instances/my-instance/SPEC.md --validate
```

## Anti-Stuck Mechanisms

| Level | Trigger | Action |
|-------|---------|--------|
| L0 | Task `in_progress` > 15 min | Reset to `pending`, increment attempts |
| L0.5 | All pending tasks blocked by failed deps | Reset failed deps or trigger planner |
| L0.75 | Task attempts ≥ 5 | Auto-escalate, trigger planner to redesign |
| Circuit Breaker | 5 consecutive failures | Pause 1 hour, notify Discord |

## License

MIT
