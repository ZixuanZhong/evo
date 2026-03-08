#!/usr/bin/env bash
# Planner: reads SPEC.md + tasks.json, generates/updates tasks via claude -p
set -euo pipefail

INSTANCE_DIR="$1"
SPEC_FILE="$INSTANCE_DIR/SPEC.md"
TASKS_FILE="$INSTANCE_DIR/tasks.json"
STATE_FILE="$INSTANCE_DIR/state.json"

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "[Planner] ERROR: $SPEC_FILE not found" >&2
  exit 1
fi

SPEC_CONTENT=$(cat "$SPEC_FILE")
TASKS_CONTENT=$(cat "$TASKS_FILE")

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

PROMPT="You are the Planner for an Evolution Loop project.

Your job: read the SPEC and current tasks.json, then CREATE or UPDATE tasks in tasks.json.

## SPEC.md
$SPEC_CONTENT

## Current tasks.json
$TASKS_CONTENT

## Instructions

1. Read the SPEC carefully. Understand the phases, goals, and constraints.
2. Look at the current tasks.json:
   - If tasks is empty (plan_version=0): create ALL tasks for the first phase based on SPEC.
   - If a gate task is 'done': plan the NEXT phase's tasks.
   - If tasks are 'escalated': redesign those tasks (break into smaller pieces, change approach).
3. For each task, set:
   - id: phase.number (e.g. '1.1', '1.2', '1.G' for gates)
   - phase: phase name
   - title: short description
   - description: detailed instructions (this is ALL the worker sees)
   - spec_file: path to detailed spec if needed, or null
   - status: 'pending'
   - priority: 'high'/'medium'/'low'
   - depends_on: array of task IDs
   - output_files: array of expected output file paths
   - type: 'task' or 'gate'
   - runner: 'agent', 'claude', 'codex', or 'gemini'
     • 'agent' — OpenClaw agent with full tools (web_search, web_fetch, memory, plugins). Uses notac API tokens. Best for research, fetching URLs, checking latest info.
     • 'claude' — Claude Code CLI (claude -p). Local tools only (Bash, Read, Write, Edit). Uses Claude subscription. Fast, no session overhead. Good for code generation, writing docs, gates.
     • 'codex' — Codex CLI (codex exec). Local tools + optional web search. Uses OpenAI/Codex subscription. Good for code generation, refactoring, code review.
     • 'gemini' — Gemini CLI (gemini -p). Local tools. Uses Gemini subscription. Good for code generation, analysis, writing.
     Prefer 'claude'/'codex'/'gemini' over 'agent' when the task doesn't need web access or OpenClaw plugins — they use subscription plans instead of API tokens.
   - started_at: null, completed_at: null, error: null, attempts: 0
4. Update plan_version (increment by 1).
5. Update the phase field to the current phase name.
6. Set planner_trigger to false.
7. Update the summary counts.
8. Write the updated tasks.json to: $TASKS_FILE

IMPORTANT:
- Tasks must be ATOMIC: 1 task = 1 output file.
- Gate conditions must use >= not ==.
- Worker runs via OpenClaw agent with FULL tools: web_search, web_fetch, exec, Read, Write, Edit.
- Worker CAN access the internet via web_search/web_fetch — design research tasks accordingly.
- Each task description must be self-contained — worker has no memory of other tasks.
- Include the full file path in output_files (relative to instance dir).
- Worker timeout is ${WORKER_TIMEOUT}s. If any task is likely to exceed ~70% of this timeout, SPLIT it into smaller tasks (e.g., 4.1a/4.1b, 5.1a/5.1b).
- If a task repeatedly fails due to timeout or oversized scope, re-plan by decomposing it and rewiring dependencies.

Write the updated tasks.json now. Also create any phase spec files in specs/ if needed."

# Read planner agent from state.json (default: evo)
PLANNER_AGENT="evo"
if [[ -f "$STATE_FILE" ]]; then
  agent=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('worker_agent','evo'))" 2>/dev/null || echo "evo")
  PLANNER_AGENT="$agent"
fi

echo "[Planner] Running planner for $(basename "$INSTANCE_DIR") via openclaw agent --agent $PLANNER_AGENT ($PLANNER_MODEL)..." >&2

# Write prompt to temp file to avoid command-line length limits
PLANNER_SESSION_ID="evo-planner-$(basename "$INSTANCE_DIR")-$(date +%s)"
PROMPT_FILE="$INSTANCE_DIR/logs/.planner-prompt.md"
echo "$PROMPT" > "$PROMPT_FILE"

(
  cd "$INSTANCE_DIR"
  openclaw agent \
    --agent "$PLANNER_AGENT" \
    --session-id "$PLANNER_SESSION_ID" \
    --message "You are the Planner for an Evolution Loop. Read the prompt file and execute it: $PROMPT_FILE" \
    --timeout 300 \
    2>&1
) | tail -5 >&2

rm -f "$PROMPT_FILE" 2>/dev/null

# Reset planner_trigger
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
