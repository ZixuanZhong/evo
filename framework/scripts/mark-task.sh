#!/usr/bin/env bash
# mark-task.sh — Worker 标记当前 task 状态的唯一入口
# 用法: mark-task.sh <instance-dir> <task-id> <done|failed> [error-message]
#
# 只允许修改指定 task 的状态，其他 task 不受影响。
# Worker prompt 中应调用: bash /path/to/mark-task.sh "$INSTANCE_DIR" "0.1" done

set -euo pipefail

INSTANCE_DIR="${1:-}"
TASK_ID="${2:-}"
STATUS="${3:-}"
ERROR_MSG="${4:-}"

[[ -n "$INSTANCE_DIR" && -n "$TASK_ID" && -n "$STATUS" ]] || {
  echo "Usage: mark-task.sh <instance-dir> <task-id> <done|failed> [error-message]" >&2
  exit 1
}

[[ "$STATUS" == "done" || "$STATUS" == "failed" ]] || {
  echo "Error: status must be 'done' or 'failed', got '$STATUS'" >&2
  exit 1
}

TASKS_FILE="$INSTANCE_DIR/tasks.json"
[[ -f "$TASKS_FILE" ]] || { echo "Error: $TASKS_FILE not found" >&2; exit 1; }

python3 -c "
import json, tempfile, os, sys

p = '$TASKS_FILE'
task_id = '$TASK_ID'
status = '$STATUS'
error_msg = '''$ERROR_MSG'''

d = json.load(open(p))
found = False
for t in d['tasks']:
    if t['id'] == task_id:
        t['status'] = status
        if status == 'failed' and error_msg:
            t['error'] = error_msg
        elif status == 'done':
            t.pop('error', None)
        found = True
        break

if not found:
    print(f'Error: task {task_id} not found in tasks.json', file=sys.stderr)
    sys.exit(1)

# Update summary
statuses = [t['status'] for t in d['tasks']]
d['summary'] = {
    'total': len(statuses),
    'pending': statuses.count('pending'),
    'in_progress': statuses.count('in_progress'),
    'done': statuses.count('done'),
    'failed': statuses.count('failed'),
    'escalated': statuses.count('escalated'),
}

fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
os.rename(tmp, p)
print(f'✅ Task {task_id} → {status}')
"
