#!/usr/bin/env bash
# Evo → Discord notification via openclaw message send
# Usage: notify-discord.sh <instance_dir> <event_type> [extra_info]
# Events: gate_passed, all_complete, circuit_breaker
set -uo pipefail

INSTANCE_DIR="$1"
EVENT="$2"
EXTRA="${3:-}"
INSTANCE_NAME=$(basename "$INSTANCE_DIR")
TASKS_FILE="$INSTANCE_DIR/tasks.json"

DISCORD_CHANNEL="${EVO_DISCORD_CHANNEL:-}"
[[ -n "$DISCORD_CHANNEL" ]] || { echo "[notify] EVO_DISCORD_CHANNEL not set, skipping notification" >&2; exit 0; }

# Build status from tasks.json
STATUS_LINE=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
s = d.get('summary', {})
print(f\"{s.get('done',0)}/{s.get('total',0)} done · {s.get('in_progress',0)} running · {s.get('pending',0)} pending · {s.get('failed',0)} failed\")
" 2>/dev/null || echo "?")

GATE_LINES=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
gates = [t for t in d['tasks'] if t['id'].endswith('.G')]
lines = []
for g in gates:
    icon = '✅' if g['status'] == 'done' else '⏳'
    lines.append(f'{icon} {g[\"id\"]}: {g[\"title\"]}')
print('\n'.join(lines))
" 2>/dev/null || echo "")

case "$EVENT" in
  gate_passed)
    TITLE="🚪 $INSTANCE_NAME: $EXTRA"
    COLOR="#2ecc71"
    ;;
  all_complete)
    TITLE="🎉 $INSTANCE_NAME: All Tasks Complete!"
    COLOR="#2ecc71"
    ;;
  circuit_breaker)
    TITLE="🚨 $INSTANCE_NAME: Circuit Breaker ($EXTRA failures)"
    COLOR="#e74c3c"
    ;;
  *)
    TITLE="📊 $INSTANCE_NAME: $EVENT"
    COLOR="#5865F2"
    ;;
esac

# Build components JSON via python for safe escaping
COMPONENTS_JSON=$(python3 -c "
import json, sys, os
title = sys.argv[1]
status = sys.argv[2]
gates = sys.argv[3]
color = sys.argv[4]
mention = os.environ.get('EVO_MENTION', '')

blocks = [
    {'type': 'text', 'text': title},
    {'type': 'separator'},
    {'type': 'text', 'text': f'**Progress**: {status}'},
    {'type': 'separator'},
    {'type': 'text', 'text': gates},
    {'type': 'separator'},
    {'type': 'text', 'text': mention}
]
comp = {'blocks': blocks, 'container': {'accentColor': color}}
print(json.dumps(comp, ensure_ascii=False))
" "$TITLE" "$STATUS_LINE" "$GATE_LINES" "$COLOR" 2>/dev/null)

if [[ -n "$COMPONENTS_JSON" ]]; then
  openclaw message send \
    --channel discord \
    --account default \
    --target "$DISCORD_CHANNEL" \
    --components "$COMPONENTS_JSON" \
    --json 2>/dev/null || true
fi
