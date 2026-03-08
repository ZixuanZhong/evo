#!/usr/bin/env bash
# Worker Loop: picks and executes tasks in a loop
set -uo pipefail

EVO_ROOT="${EVO_ROOT:-$HOME/.openclaw/evo}"
SCRIPTS_DIR="$EVO_ROOT/framework/scripts"
INSTANCE_NAME="$1"
WORKER_ID="${2:-1}"
INSTANCE_DIR="$EVO_ROOT/instances/$INSTANCE_NAME"
TASKS_FILE="$INSTANCE_DIR/tasks.json"
STATE_FILE="$INSTANCE_DIR/state.json"
SPEC_FILE="$INSTANCE_DIR/SPEC.md"
LOG_FILE="$INSTANCE_DIR/logs/worker.${WORKER_ID}.log"
CLAUDE_MD="$EVO_ROOT/framework/CLAUDE.md"

SLEEP_INTERVAL=10
MAX_IDLE_CYCLES=10
MAX_CONSECUTIVE_FAILURES=5
idle_count=0
consecutive_failures=0
MAX_LOG_SIZE=10485760  # 10MB

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')][W${WORKER_ID}] $*"
}

check_budget() {
  if [[ -f "$SCRIPTS_DIR/check_budget.py" ]]; then
    if ! python3 "$SCRIPTS_DIR/check_budget.py" "$STATE_FILE" 2>/dev/null; then
      log "[Budget] Daily limit reached, sleeping 1h"
      sleep 3600
      return 1
    fi
  fi
  return 0
}

get_worker_model() {
  python3 -c "import json; print(json.load(open('$STATE_FILE')).get('worker_model','sonnet'))" 2>/dev/null || echo "sonnet"
}

get_worker_agent() {
  python3 -c "import json; print(json.load(open('$STATE_FILE')).get('worker_agent','evo'))" 2>/dev/null || echo "evo"
}

# Mark task done/failed after worker execution
verify_task() {
  local task_id="$1"
  local exit_code="$2"

  python3 -c "
import json, tempfile, os, sys
from datetime import datetime, timezone

p = '$TASKS_FILE'
d = json.load(open(p))
for t in d['tasks']:
    if t['id'] == '$task_id' and t['status'] == 'in_progress':
        if $exit_code == 0:
            # Check if output files exist (support both output_files array and legacy output_file string)
            out_files = t.get('output_files', [])
            if not out_files and t.get('output_file'):
                out_files = [t['output_file']]
            all_exist = True
            for of in out_files:
                if of and not os.path.exists(os.path.join('$INSTANCE_DIR', of)):
                    all_exist = False
                    break
            if all_exist or t.get('type') == 'gate':
                t['status'] = 'done'
                t['completed_at'] = datetime.now(timezone.utc).isoformat()
                # If gate done, trigger planner for next phase
                if t.get('type') == 'gate':
                    d['planner_trigger'] = True
            else:
                t['status'] = 'failed'
                t['error'] = 'Output files not found after execution'
        else:
            t['status'] = 'failed'
            t['error'] = f'Worker exited with code $exit_code'
        break

# Update summary
tasks = d['tasks']
d['summary'] = {
    'total': len(tasks),
    'pending': sum(1 for t in tasks if t['status'] == 'pending'),
    'in_progress': sum(1 for t in tasks if t['status'] == 'in_progress'),
    'done': sum(1 for t in tasks if t['status'] == 'done'),
    'failed': sum(1 for t in tasks if t['status'] == 'failed'),
    'escalated': sum(1 for t in tasks if t['status'] == 'escalated'),
}

fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
os.rename(tmp, p)
" 2>>"$LOG_FILE"
}

# Log rotation: if worker.log > 10MB, rotate
if [[ -f "$LOG_FILE" ]]; then
  log_size=$(wc -c < "$LOG_FILE" | tr -d ' ')
  if [[ $log_size -gt $MAX_LOG_SIZE ]]; then
    mv "$LOG_FILE" "${LOG_FILE}.1"
    # Keep only 1 rotated file
    rm -f "${LOG_FILE}.2" 2>/dev/null
  fi
fi

# Trap: on exit, check if all tasks done and archive
cleanup_and_archive() {
  if [[ -f "$TASKS_FILE" ]]; then
    all_done=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
s = d.get('summary', {})
total = s.get('total', 0)
done = s.get('done', 0)
escalated = s.get('escalated', 0)
print('yes' if total > 0 and done + escalated == total else 'no')
" 2>/dev/null || echo "no")
    if [[ "$all_done" == "yes" && ! -f "$INSTANCE_DIR/logs/archived.flag" ]]; then
      log "Trap: completed instance detected"
      echo "{\"event\":\"completed\",\"ts\":\"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",\"instance\":\"$INSTANCE_NAME\"}" > "$INSTANCE_DIR/logs/completed.json"
      bash "$SCRIPTS_DIR/notify-discord.sh" "$INSTANCE_DIR" "all_complete" "" 2>/dev/null || true
      # Skip archive for recurring instances (they get reset, not archived)
      is_recurring=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('recurring', False))" 2>/dev/null || echo "False")
      if [[ "$is_recurring" != "True" ]]; then
        bash "$SCRIPTS_DIR/archive-to-github.sh" "$INSTANCE_DIR" >> "$LOG_FILE" 2>&1 || true
      else
        log "Recurring instance — skipping archive"
      fi
      touch "$INSTANCE_DIR/logs/archived.flag"
    fi
  fi
}
trap cleanup_and_archive EXIT

log "Worker starting for instance: $INSTANCE_NAME"

while true; do
  # Check if still active
  active=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('active', False))" 2>/dev/null || echo "False")
  if [[ "$active" != "True" ]]; then
    log "Instance not active, exiting"
    break
  fi

  # Check planner trigger
  trigger=$(python3 -c "import json; print(json.load(open('$TASKS_FILE')).get('planner_trigger', False))" 2>/dev/null || echo "False")
  if [[ "$trigger" == "True" ]]; then
    log "Planner triggered, running inline..."
    bash "$SCRIPTS_DIR/planner.sh" "$INSTANCE_DIR" 2>>"$LOG_FILE" || log "[WARN] Planner failed"
  fi

  # Check budget
  check_budget || continue

  # Pick next task (includes L0/L0.5/L0.75)
  task_id=$(python3 "$SCRIPTS_DIR/pick_next_task.py" "$TASKS_FILE" 2>>"$LOG_FILE") || true

  if [[ -z "$task_id" ]]; then
    idle_count=$((idle_count + 1))
    log "No task available (idle=$idle_count/$MAX_IDLE_CYCLES)"

    if [[ $idle_count -ge $MAX_IDLE_CYCLES ]]; then
      # Check if all done
      summary=$(python3 -c "import json; d=json.load(open('$TASKS_FILE')); s=d['summary']; print(f\"{s['pending']}:{s['in_progress']}:{s['failed']}\")" 2>/dev/null || echo "0:0:0")
      pending=$(echo "$summary" | cut -d: -f1)
      in_prog=$(echo "$summary" | cut -d: -f2)
      failed=$(echo "$summary" | cut -d: -f3)

      if [[ "$pending" == "0" && "$in_prog" == "0" && "$failed" == "0" ]]; then
        log "All tasks complete, auto-stopping"
        python3 -c "
import json, tempfile, os
p = '$STATE_FILE'
d = json.load(open(p))
d['active'] = False
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
os.rename(tmp, p)
" 2>>"$LOG_FILE"
        break
      fi
    fi

    sleep $SLEEP_INTERVAL
    continue
  fi

  idle_count=0

  # Get task details
  task_json=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
for t in d['tasks']:
    if t['id'] == '$task_id':
        print(json.dumps(t))
        break
" 2>/dev/null)

  task_title=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])" 2>/dev/null)
  task_desc=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['description'])" 2>/dev/null)
  task_type=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('type','task'))" 2>/dev/null)
  task_phase=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('phase',''))" 2>/dev/null)
  spec_file=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('spec_file','') or '')" 2>/dev/null)
  output_files=$(echo "$task_json" | python3 -c "
import json,sys
t=json.load(sys.stdin)
ofs=t.get('output_files', [])
if not ofs and t.get('output_file'):
    ofs=[t['output_file']]
print(', '.join(ofs))
" 2>/dev/null)
  task_runner=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('runner','agent'))" 2>/dev/null)

  log "Executing task $task_id: $task_title"

  # ─── Auto-split check ───
  has_split=$(echo "$task_json" | python3 -c "
import json,sys
t=json.load(sys.stdin)
print('yes' if t.get('auto_split') else 'no')
" 2>/dev/null || echo "no")

  if [[ "$has_split" == "yes" ]]; then
    log "Task $task_id has auto_split, expanding..."
    expand_exit=0
    python3 "$SCRIPTS_DIR/expand_task.py" "$TASKS_FILE" "$task_id" "$INSTANCE_DIR" 2>>"$LOG_FILE" || expand_exit=$?
    if [[ $expand_exit -eq 0 ]]; then
      log "Task $task_id expanded into sub-tasks, continuing loop"
      python3 "$SCRIPTS_DIR/log_task.py" "$INSTANCE_DIR" "$task_id" "expanded" '{}' 2>/dev/null || true
      sleep 1
      continue  # skip execution, next iteration picks sub-tasks
    elif [[ $expand_exit -eq 1 ]]; then
      log "Task $task_id: items within batch_size, executing normally"
    else
      log "Task $task_id: auto_split error (exit=$expand_exit)"
      sleep $SLEEP_INTERVAL
      continue
    fi
  fi

  python3 "$SCRIPTS_DIR/log_task.py" "$INSTANCE_DIR" "$task_id" "started" '{"model":"'"$(get_worker_model)"'"}' 2>/dev/null || true

  # ─── Build prompt: 3-layer context ───

  # Layer 1: SPEC.md (always included)
  PROMPT="You are a research Worker in an Evolution Loop. Execute this task precisely.

You have full OpenClaw tools: web_search, web_fetch, Read, Write, Edit, exec (Bash).
Use web_search actively for research tasks — find papers, blog posts, documentation, benchmarks.
Use exec to run shell commands, create files, and execute code.

## Project SPEC
$(cat "$SPEC_FILE")
"

  # Layer 2: phase spec (if exists)
  phase_spec="$INSTANCE_DIR/specs/phase-${task_phase}.md"
  if [[ -f "$phase_spec" ]]; then
    PROMPT="$PROMPT
## Phase Spec
$(cat "$phase_spec")
"
  fi

  # Layer 3: task spec (if exists)
  if [[ -n "$spec_file" && -f "$INSTANCE_DIR/$spec_file" ]]; then
    PROMPT="$PROMPT
## Task Spec
$(cat "$INSTANCE_DIR/$spec_file")
"
  fi

  # Layer 4: dependency outputs (inject completed task outputs as context)
  dep_context=""
  dep_files=$(echo "$task_json" | python3 -c "
import json, sys, os
t = json.load(sys.stdin)
deps = t.get('depends_on', [])
if not deps:
    sys.exit(0)
# Load tasks to find output files of dependencies
tasks = json.load(open('$TASKS_FILE'))['tasks']
dep_map = {t2['id']: t2 for t2 in tasks}
for dep_id in deps:
    dep = dep_map.get(dep_id)
    if dep and dep.get('status') == 'done':
        dep_ofs = dep.get('output_files', [])
        if not dep_ofs and dep.get('output_file'):
            dep_ofs = [dep['output_file']]
        for of in dep_ofs:
            fp = os.path.join('$INSTANCE_DIR', of)
            if os.path.isfile(fp) and os.path.getsize(fp) < 30000:
                print(fp)
" 2>/dev/null) || true

  if [[ -n "$dep_files" ]]; then
    PROMPT="$PROMPT
## Context from completed dependencies
"
    dep_total_chars=0
    DEP_MAX_TOTAL=40000  # Cap total dependency context at 40KB
    while IFS= read -r dep_file; do
      if [[ -f "$dep_file" ]] && [[ $dep_total_chars -lt $DEP_MAX_TOTAL ]]; then
        fname=$(basename "$dep_file")
        remaining=$((DEP_MAX_TOTAL - dep_total_chars))
        content=$(head -c "$remaining" "$dep_file")
        dep_total_chars=$((dep_total_chars + ${#content}))
        PROMPT="$PROMPT
### $fname
$content
---
"
      fi
    done <<< "$dep_files"
  fi

  # Task details
  PROMPT="$PROMPT
## Your Task

- **ID**: $task_id
- **Title**: $task_title
- **Type**: $task_type
- **Phase**: $task_phase
- **Output files**: $output_files

## Instructions

$task_desc

## Rules

1. Create the output file(s) listed above. All paths relative to: $INSTANCE_DIR
2. After completing the work, mark the task as done:
   \`\`\`bash
   bash $SCRIPTS_DIR/mark-task.sh $INSTANCE_DIR $task_id done
   \`\`\`
3. If you cannot complete the task, mark it as failed:
   \`\`\`bash
   bash $SCRIPTS_DIR/mark-task.sh $INSTANCE_DIR $task_id failed \"reason here\"
   \`\`\`
4. ⛔ **DO NOT edit tasks.json directly.** Only use mark-task.sh. Any direct edits will be reverted.
5. For research tasks: USE web_search to find real papers, products, benchmarks. Do NOT fabricate citations.
6. Write knowledge docs in Chinese (通俗易懂), code in English comments.

Working directory: $INSTANCE_DIR"

  WORKER_MODEL=$(get_worker_model)
  WORKER_AGENT=$(get_worker_agent)
  WORKER_TIMEOUT=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('worker_timeout', 300))" 2>/dev/null || echo "300")

  PROMPT_FILE="$INSTANCE_DIR/logs/.worker-prompt-${task_id}.md"
  echo "$PROMPT" > "$PROMPT_FILE"
  worker_exit=0

  # Snapshot tasks.json before worker runs (for illegal modification guard)
  cp "$TASKS_FILE" "${TASKS_FILE}.pre-task.${task_id}"

  # Hard timeout: WORKER_TIMEOUT + 30s grace for cleanup
  # This kills the process tree if openclaw agent's own timeout doesn't work
  HARD_TIMEOUT=$((WORKER_TIMEOUT + 30))

  # Clean stale session locks before starting (prevents lock contention from prior crashes)
  find "$HOME/.openclaw/agents/${WORKER_AGENT}/sessions/" -name "*.lock" -mmin +5 -delete 2>/dev/null || true

  case "$task_runner" in
    claude)
      # ─── claude -p: local-only, no web, fast, uses Claude subscription ───
      log "Executing via claude -p (runner=claude), model: $WORKER_MODEL, timeout: ${WORKER_TIMEOUT}s (hard: ${HARD_TIMEOUT}s)"
      (
        unset CLAUDECODE 2>/dev/null || true
        cd "$INSTANCE_DIR"
        claude -p "$(cat "$PROMPT_FILE")" \
          --allowedTools "Bash,Read,Write,Edit" \
          --output-format text \
          --max-turns 50 \
          --model "$WORKER_MODEL" 2>&1
      ) >> "$LOG_FILE" 2>&1 &
      WORKER_PID=$!
      ;;

    codex)
      # ─── codex exec: local tools + optional web, uses Codex/OpenAI subscription ───
      # Model override: state.json worker_model applies (e.g. o3, o4-mini, codex-mini)
      CODEX_MODEL="${WORKER_MODEL}"
      # Map common aliases to codex-compatible model names
      case "$CODEX_MODEL" in
        sonnet|opus|haiku) CODEX_MODEL="o4-mini" ;;  # default fallback for non-OpenAI aliases
      esac
      CODEX_EXTRA_FLAGS=""
      # Enable web search if task is agent-like (research)
      if echo "$task_json" | python3 -c "import json,sys; t=json.load(sys.stdin); sys.exit(0 if 'research' in t.get('title','').lower() or 'research' in t.get('description','').lower() else 1)" 2>/dev/null; then
        CODEX_EXTRA_FLAGS="--web-search"
      fi
      log "Executing via codex exec (runner=codex), model: $CODEX_MODEL, timeout: ${WORKER_TIMEOUT}s (hard: ${HARD_TIMEOUT}s)"
      (
        cd "$INSTANCE_DIR"
        codex exec \
          --model "$CODEX_MODEL" \
          --full-auto \
          --sandbox danger-full-access \
          $CODEX_EXTRA_FLAGS \
          "$(cat "$PROMPT_FILE")" 2>&1
      ) >> "$LOG_FILE" 2>&1 &
      WORKER_PID=$!
      ;;

    gemini)
      # ─── gemini -p: local tools, uses Gemini subscription ───
      GEMINI_MODEL="${WORKER_MODEL}"
      # Map common aliases to gemini-compatible model names
      case "$GEMINI_MODEL" in
        sonnet|opus|haiku) GEMINI_MODEL="gemini-2.5-pro" ;;  # default fallback for non-Google aliases
      esac
      log "Executing via gemini -p (runner=gemini), model: $GEMINI_MODEL, timeout: ${WORKER_TIMEOUT}s (hard: ${HARD_TIMEOUT}s)"
      (
        cd "$INSTANCE_DIR"
        gemini \
          --model "$GEMINI_MODEL" \
          --prompt "$(cat "$PROMPT_FILE")" \
          --sandbox \
          --yolo \
          --output-format text 2>&1
      ) >> "$LOG_FILE" 2>&1 &
      WORKER_PID=$!
      ;;

    agent|*)
      # ─── openclaw agent: full tools (web_search, web_fetch, memory, plugins) — uses notac tokens ───
      log "Executing via openclaw agent --agent $WORKER_AGENT (runner=agent), model: $WORKER_MODEL, timeout: ${WORKER_TIMEOUT}s (hard: ${HARD_TIMEOUT}s)"
      SESSION_ID="evo-${INSTANCE_NAME}-${task_id}-$(date +%s)"
      openclaw agent \
        --agent "$WORKER_AGENT" \
        --session-id "$SESSION_ID" \
        --message "You are a research Worker in an Evolution Loop. Read the task prompt file and execute it: $PROMPT_FILE" \
        --timeout "$WORKER_TIMEOUT" \
        2>>"$LOG_FILE" >> "$LOG_FILE" &
      WORKER_PID=$!
      ;;
  esac

  # ─── Hard timeout watchdog ───
  (
    sleep "$HARD_TIMEOUT"
    if kill -0 "$WORKER_PID" 2>/dev/null; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [HARD-TIMEOUT] Killing worker PID $WORKER_PID after ${HARD_TIMEOUT}s" >> "$LOG_FILE"
      # Kill process group to catch child processes too
      kill -TERM "$WORKER_PID" 2>/dev/null
      sleep 5
      kill -9 "$WORKER_PID" 2>/dev/null
    fi
  ) &
  WATCHDOG_PID=$!

  # Wait for worker to finish (or be killed by watchdog)
  wait "$WORKER_PID" 2>/dev/null
  worker_exit=$?

  # Cancel watchdog if worker finished on its own
  kill "$WATCHDOG_PID" 2>/dev/null
  wait "$WATCHDOG_PID" 2>/dev/null

  rm -f "$PROMPT_FILE" 2>/dev/null

  # Guard: restore any tasks the worker illegally modified (only current task may change)
  python3 -c "
import json, tempfile, os
p = '$TASKS_FILE'
task_id = '$task_id'
d = json.load(open(p))
fixed = 0
for t in d['tasks']:
    if t['id'] == task_id:
        continue
    # If worker changed a non-current pending/in_progress task to done, revert it
    # We saved pre_statuses before; compare with snapshot
    pass

# Simpler approach: snapshot was saved as .pre-task file
pre_path = p + '.pre-task.' + task_id
if os.path.exists(pre_path):
    pre = json.load(open(pre_path))
    pre_map = {t['id']: t['status'] for t in pre['tasks']}
    for t in d['tasks']:
        if t['id'] == task_id:
            continue
        old_status = pre_map.get(t['id'])
        if old_status and t['status'] != old_status:
            print(f'[GUARD] Reverting {t[\"id\"]} from {t[\"status\"]} back to {old_status} (worker modified illegally)')
            t['status'] = old_status
            fixed += 1
    if fixed > 0:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
        with os.fdopen(fd, 'w') as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.rename(tmp, p)
        print(f'[GUARD] Fixed {fixed} illegally modified tasks')
    os.remove(pre_path)
" 2>>"$LOG_FILE" || true

  # Verify task was updated (fallback if agent didn't)
  current_status=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
for t in d['tasks']:
    if t['id'] == '$task_id':
        print(t['status'])
        break
" 2>/dev/null || echo "unknown")

  if [[ "$current_status" == "in_progress" ]]; then
    log "Agent didn't update tasks.json, doing it ourselves (exit=$worker_exit)"
    verify_task "$task_id" "$worker_exit"
  fi

  # Increment today's task count
  python3 -c "
import json, tempfile, os
from datetime import date
p = '$STATE_FILE'
d = json.load(open(p))
today = str(date.today())
if d.get('budget_date') != today:
    d['tasks_today'] = 0
    d['budget_date'] = today
d['tasks_today'] = d.get('tasks_today', 0) + 1
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
os.rename(tmp, p)
" 2>>"$LOG_FILE" || true

  # Structured log
  final_status=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
for t in d['tasks']:
    if t['id'] == '$task_id':
        print(t['status'])
        break
" 2>/dev/null || echo "unknown")
  log_event="completed"
  [[ "$final_status" == "failed" ]] && log_event="failed"
  [[ "$final_status" == "escalated" ]] && log_event="escalated"
  python3 "$SCRIPTS_DIR/log_task.py" "$INSTANCE_DIR" "$task_id" "$log_event" '{"exit_code":'"$worker_exit"'}' 2>/dev/null || true

  # Circuit breaker: track consecutive failures
  if [[ "$final_status" == "failed" || "$final_status" == "escalated" ]]; then
    consecutive_failures=$((consecutive_failures + 1))
    log "[Circuit] Consecutive failures: $consecutive_failures/$MAX_CONSECUTIVE_FAILURES"
    if [[ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]]; then
      log "[Circuit] BREAKER TRIPPED — $MAX_CONSECUTIVE_FAILURES consecutive failures. Pausing worker."
      python3 "$SCRIPTS_DIR/log_task.py" "$INSTANCE_DIR" "circuit_breaker" "circuit_breaker" '{"consecutive_failures":'"$consecutive_failures"'}' 2>/dev/null || true
      # Write marker for reporter/inspector to pick up
      echo "{\"event\":\"circuit_breaker\",\"ts\":\"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",\"failures\":$consecutive_failures}" > "$INSTANCE_DIR/logs/circuit-breaker.json"
      bash "$SCRIPTS_DIR/notify-discord.sh" "$INSTANCE_DIR" "circuit_breaker" "$consecutive_failures" &
      sleep 3600  # pause 1 hour
      consecutive_failures=0  # reset after pause
    fi
  else
    consecutive_failures=0
  fi

  log "Task $task_id finished (status: $final_status)"

  # ─── Discord notification hook ───
  # Notify on: gate passed, circuit breaker (all_complete handled below)
  if [[ "$final_status" == "done" && "$task_id" == *".G" ]]; then
    task_title=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('title',''))" 2>/dev/null || echo "$task_id")
    bash "$SCRIPTS_DIR/notify-discord.sh" "$INSTANCE_DIR" "gate_passed" "$task_title" &
  fi

  sleep $SLEEP_INTERVAL
done

# Auto-stop: write completion marker
if [[ -f "$TASKS_FILE" ]]; then
  all_done=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
s = d.get('summary', {})
total = s.get('total', 0)
done = s.get('done', 0)
escalated = s.get('escalated', 0)
print('yes' if total > 0 and done + escalated == total else 'no')
" 2>/dev/null || echo "no")
  if [[ "$all_done" == "yes" ]]; then
    log "All tasks complete. Writing completion marker."
    echo "{\"event\":\"completed\",\"ts\":\"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",\"instance\":\"$INSTANCE_NAME\"}" > "$INSTANCE_DIR/logs/completed.json"
    python3 "$SCRIPTS_DIR/log_task.py" "$INSTANCE_DIR" "worker" "auto_stop" '{"reason":"all_tasks_complete"}' 2>/dev/null || true
    bash "$SCRIPTS_DIR/notify-discord.sh" "$INSTANCE_DIR" "all_complete" "" &
    # Skip archive for recurring instances
    is_recurring=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('recurring', False))" 2>/dev/null || echo "False")
    if [[ "$is_recurring" != "True" ]]; then
      bash "$SCRIPTS_DIR/archive-to-github.sh" "$INSTANCE_DIR" >> "$LOG_FILE" 2>&1 &
    fi
  fi
fi

log "Worker loop exited for $INSTANCE_NAME"
