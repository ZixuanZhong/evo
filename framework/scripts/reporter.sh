#!/usr/bin/env bash
# Reporter: output status summary for all instances (JSON or human-readable)
set -uo pipefail

EVO_ROOT="${EVO_ROOT:-$HOME/.openclaw/evo}"
FORMAT="${1:---text}"

instances_dir="$EVO_ROOT/instances"

if [[ ! -d "$instances_dir" ]]; then
  echo "No instances directory found"
  exit 0
fi

report_json() {
  echo "["
  first=true
  for dir in "$instances_dir"/*/; do
    [[ -d "$dir" ]] || continue
    name=$(basename "$dir")
    tasks_file="$dir/tasks.json"
    state_file="$dir/state.json"
    [[ -f "$tasks_file" && -f "$state_file" ]] || continue

    if [[ "$first" == "true" ]]; then first=false; else echo ","; fi

    python3 -c "
import json
state = json.load(open('$state_file'))
tasks = json.load(open('$tasks_file'))
s = tasks.get('summary', {})
print(json.dumps({
    'name': '$name',
    'active': state.get('active', False),
    'phase': tasks.get('phase', ''),
    'plan_version': tasks.get('plan_version', 0),
    'summary': s,
    'worker_model': state.get('worker_model', 'sonnet'),
    'tasks_today': state.get('tasks_today', 0),
}, indent=2))
"
  done
  echo "]"
}

report_text() {
  found=false
  for dir in "$instances_dir"/*/; do
    [[ -d "$dir" ]] || continue
    name=$(basename "$dir")
    tasks_file="$dir/tasks.json"
    state_file="$dir/state.json"
    [[ -f "$tasks_file" && -f "$state_file" ]] || continue
    found=true

    python3 -c "
import json
state = json.load(open('$state_file'))
tasks = json.load(open('$tasks_file'))
s = tasks.get('summary', {})
active = '🟢' if state.get('active') else '⚫'
phase = tasks.get('phase', '—')
total = s.get('total', 0)
done = s.get('done', 0)
pending = s.get('pending', 0)
in_prog = s.get('in_progress', 0)
failed = s.get('failed', 0)
escalated = s.get('escalated', 0)
pct = int(done / total * 100) if total > 0 else 0

print(f'{active} **{\"$name\"}** (v{tasks.get(\"plan_version\", 0)}) — phase: {phase}')
print(f'   {done}/{total} done ({pct}%) | pending:{pending} running:{in_prog} failed:{failed} escalated:{escalated}')
print(f'   model: {state.get(\"worker_model\", \"sonnet\")} | today: {state.get(\"tasks_today\", 0)} tasks')
print()
"
  done

  if [[ "$found" == "false" ]]; then
    echo "No evo instances found."
  fi
}

report_detail() {
  local name="$1"
  local dir="$instances_dir/$name"
  local tasks_file="$dir/tasks.json"

  if [[ ! -f "$tasks_file" ]]; then
    echo "Instance '$name' not found"
    exit 1
  fi

  python3 -c "
import json
d = json.load(open('$tasks_file'))
phase = d.get('phase', '—')
print(f'**{\"$name\"}** — phase: {phase} (v{d.get(\"plan_version\", 0)})')
print()
for t in d['tasks']:
    status_icon = {'pending': '⬜', 'in_progress': '🔵', 'done': '✅', 'failed': '❌', 'escalated': '🟠'}.get(t['status'], '?')
    gate = ' [GATE]' if t.get('type') == 'gate' else ''
    attempts = f' (x{t[\"attempts\"]})' if t.get('attempts', 0) > 1 else ''
    err = f' — {t[\"error\"]}' if t.get('error') else ''
    print(f'{status_icon} {t[\"id\"]} {t[\"title\"]}{gate}{attempts}{err}')
"
}

case "$FORMAT" in
  --json) report_json ;;
  --text) report_text ;;
  --detail)
    if [[ -n "${2:-}" ]]; then
      report_detail "$2"
    else
      report_text
    fi
    ;;
  *) report_text ;;
esac
