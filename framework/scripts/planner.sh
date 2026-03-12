#!/usr/bin/env bash
# Planner: reads SPEC.md + tasks.json, generates/updates tasks via claude -p
#
# Architecture:
#   - Planner instructions (fixed template) go into --system-prompt
#   - SPEC + tasks are saved to a prompt file
#   - A short user message tells claude to read the prompt file via Read tool
#   - This keeps the stdin/argument small and avoids shell escaping issues
#   - claude -p with Read/Write/Bash tools does the actual planning
set -euo pipefail

INSTANCE_DIR="$1"
SPEC_FILE="$INSTANCE_DIR/SPEC.md"
TASKS_FILE="$INSTANCE_DIR/tasks.json"
STATE_FILE="$INSTANCE_DIR/state.json"

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "[Planner] ERROR: $SPEC_FILE not found" >&2
  exit 1
fi

# Read planner model from state.json (default: opus)
PLANNER_MODEL="opus"
if [[ -f "$STATE_FILE" ]]; then
  model=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('planner_model','opus'))" 2>/dev/null || echo "opus")
  PLANNER_MODEL="$model"
fi

# Read worker timeout from state.json (default: 300)
WORKER_TIMEOUT="300"
if [[ -f "$STATE_FILE" ]]; then
  wt=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('worker_timeout',300))" 2>/dev/null || echo "300")
  WORKER_TIMEOUT="$wt"
fi

# ─── Build planner prompt file ─────────────────────────

PROMPT_FILE="$INSTANCE_DIR/logs/.planner-prompt.md"
cat > "$PROMPT_FILE" <<PROMPT_EOF
# Planner Prompt

## SPEC.md

$(cat "$SPEC_FILE")

## Current tasks.json

$(cat "$TASKS_FILE")

## Instructions

1. Read the SPEC carefully. Understand the phases, goals, and constraints.
2. Look at the current tasks.json:
   - If tasks is empty (plan_version=0): create ALL tasks for ALL phases based on SPEC.
   - If a gate task is 'done': plan the NEXT phase's tasks (append to existing).
   - If tasks are 'escalated': redesign those tasks (break into smaller pieces, change approach).
3. For each task, set:
   - id: phase.number (e.g. '1.1', '1.2', '1.G' for gates)
   - phase: phase name
   - title: short description
   - description: detailed instructions (this is ALL the worker sees — must be self-contained)
   - status: 'pending'
   - depends_on: array of task IDs
   - output_files: array of expected output file paths
   - type: 'task' or 'gate'
   - runner: 'codex', 'claude', 'gemini', or 'agent'
     • codex — Codex CLI. Uses OpenAI subscription. Good for code generation.
     • claude — Claude Code CLI. Uses Claude subscription. Good for code, docs, gates.
     • gemini — Gemini CLI. Uses Gemini subscription. Good for analysis.
     • agent — OpenClaw agent with web tools. Uses API tokens. For research only.
     Prefer codex/claude/gemini over agent (subscription vs API tokens).
   - started_at: null, completed_at: null, error: null, attempts: 0
4. Update plan_version (increment by 1).
5. Update the phase and summary fields.
6. Set planner_trigger to false.
7. Write the updated tasks.json to: $TASKS_FILE

IMPORTANT:
- Tasks must be ATOMIC: 1 task = 1 clear deliverable.
- Gate conditions must use >= not ==.
- Each task description must be SELF-CONTAINED — worker has no memory of other tasks.
- Worker timeout is ${WORKER_TIMEOUT}s. Split large tasks to stay under ~70%.
- Include full file paths in output_files.
PROMPT_EOF

# ─── Build system prompt (short, fixed) ────────────────

SYSTEM_PROMPT="You are the Planner for an Evolution Loop project. Your job is to read a prompt file containing the SPEC and current tasks, then create/update tasks.json. Use the Read tool to read the prompt file, then use the Write tool or Bash tool to update tasks.json. Be precise and thorough."

# ─── Run claude -p ─────────────────────────────────────

echo "[Planner] Running planner for $(basename "$INSTANCE_DIR") via claude -p (model: $PLANNER_MODEL)..." >&2

(
  cd "$INSTANCE_DIR"
  echo "Read the planner prompt file at $PROMPT_FILE and follow its instructions to create/update tasks.json." | \
    claude -p \
      --model "$PLANNER_MODEL" \
      --system-prompt "$SYSTEM_PROMPT" \
      --allowedTools "Read,Write,Edit,Bash" \
      --add-dir "$INSTANCE_DIR" \
      2>&1
) | tail -10 >&2

# ─── Post-run: reset planner_trigger ───────────────────

python3 -c "
import json, tempfile, os
p = '$TASKS_FILE'
d = json.load(open(p))
d['planner_trigger'] = False
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
os.rename(tmp, p)
" 2>/dev/null || true

echo "[Planner] Done." >&2
