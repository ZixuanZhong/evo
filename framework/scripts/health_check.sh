#!/usr/bin/env bash
# Health check: output system health JSON for all evo instances
set -uo pipefail

EVO_ROOT="${EVO_ROOT:-$HOME/.openclaw/evo}"
INSTANCES_DIR="$EVO_ROOT/instances"

echo "{"
echo "  \"checked_at\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
echo "  \"instances\": ["

first=true
for dir in "$INSTANCES_DIR"/*/; do
  [[ -d "$dir" ]] || continue
  name=$(basename "$dir")
  state_file="$dir/state.json"
  tasks_file="$dir/tasks.json"
  worker_pid_file="$dir/logs/worker.pid"

  [[ -f "$state_file" && -f "$tasks_file" ]] || continue

  if [[ "$first" == "true" ]]; then first=false; else echo ","; fi

  # Worker process alive?
  worker_alive=false
  worker_pid=""
  if [[ -f "$worker_pid_file" ]]; then
    worker_pid=$(cat "$worker_pid_file")
    if kill -0 "$worker_pid" 2>/dev/null; then
      worker_alive=true
    fi
  fi

  # tasks.json valid?
  tasks_valid=false
  if python3 -c "import json; json.load(open('$tasks_file'))" 2>/dev/null; then
    tasks_valid=true
  fi

  # state.json active?
  active=$(python3 -c "import json; print(str(json.load(open('$state_file')).get('active', False)).lower())" 2>/dev/null || echo "false")

  # Task stats
  stats=$(python3 -c "
import json
d = json.load(open('$tasks_file'))
s = d.get('summary', {})
print(json.dumps(s))
" 2>/dev/null || echo "{}")

  # Log file size
  log_size=0
  if [[ -f "$dir/logs/worker.log" ]]; then
    log_size=$(wc -c < "$dir/logs/worker.log" | tr -d ' ')
  fi

  # Stale check: any in_progress > 10min?
  stale_tasks=$(python3 -c "
import json, time
from datetime import datetime, timezone
d = json.load(open('$tasks_file'))
now = time.time()
stale = []
for t in d.get('tasks', []):
    if t['status'] == 'in_progress' and t.get('started_at'):
        try:
            started = datetime.fromisoformat(t['started_at'].replace('Z','+00:00')).timestamp()
            if now - started > 600:
                stale.append(t['id'])
        except: pass
print(json.dumps(stale))
" 2>/dev/null || echo "[]")

  # Issues
  issues="[]"
  python3 -c "
import json
issues = []
if not $worker_alive and '$active' == 'true':
    issues.append('Worker not running but instance is active')
if not $tasks_valid:
    issues.append('tasks.json is invalid/corrupt')
stale = $stale_tasks
if stale:
    issues.append(f'Stale in_progress tasks: {stale}')
if $log_size > 10485760:
    issues.append(f'Worker log is large: {$log_size // 1048576}MB')
print(json.dumps(issues))
" 2>/dev/null | read -r issues || issues="[]"

  cat <<INST
    {
      "name": "$name",
      "active": $active,
      "worker_alive": $worker_alive,
      "worker_pid": "$worker_pid",
      "tasks_valid": $tasks_valid,
      "summary": $stats,
      "stale_tasks": $stale_tasks,
      "log_size_bytes": $log_size,
      "issues": $issues
    }
INST

done

echo "  ]"
echo "}"
