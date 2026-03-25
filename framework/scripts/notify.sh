#!/usr/bin/env bash
# Evo → Generic notification dispatcher
# Reads notify_channel/notify_target from state.json, dispatches to feishu or discord.
# Usage: notify.sh <instance_dir> <event_type> [extra_info]
# Events: gate_passed, all_complete, circuit_breaker, rate_limit_fallback
set -uo pipefail

INSTANCE_DIR="$1"
EVENT="$2"
EXTRA="${3:-}"
INSTANCE_NAME=$(basename "$INSTANCE_DIR")
STATE_FILE="$INSTANCE_DIR/state.json"
TASKS_FILE="$INSTANCE_DIR/tasks.json"

# Read notification config from state.json
NOTIFY_CHANNEL=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('notify_channel',''))" 2>/dev/null || echo "")
NOTIFY_TARGET=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('notify_target',''))" 2>/dev/null || echo "")

# Fallback to discord if no notify_channel set
if [[ -z "$NOTIFY_CHANNEL" ]]; then
  NOTIFY_CHANNEL="discord"
fi

# Build status line from tasks.json
STATUS_LINE=$(python3 -c "
import json
d = json.load(open('$TASKS_FILE'))
s = d.get('summary', {})
print(f\"{s.get('done',0)}/{s.get('total',0)} done · {s.get('in_progress',0)} running · {s.get('pending',0)} pending · {s.get('failed',0)} failed\")
" 2>/dev/null || echo "?")

# Build message based on event type
case "$EVENT" in
  gate_passed)
    EMOJI="🚪"
    TITLE="Gate Passed: $EXTRA"
    ;;
  all_complete)
    EMOJI="🎉"
    TITLE="All Tasks Complete!"
    ;;
  circuit_breaker)
    EMOJI="🚨"
    TITLE="Circuit Breaker ($EXTRA failures)"
    ;;
  rate_limit_fallback)
    EMOJI="⚠️"
    TITLE="Rate Limit Fallback: $EXTRA"
    ;;
  *)
    EMOJI="📊"
    TITLE="$EVENT"
    ;;
esac

MSG="$EMOJI **$INSTANCE_NAME**: $TITLE
Progress: $STATUS_LINE"

# Dispatch based on channel
case "$NOTIFY_CHANNEL" in
  feishu)
    if [[ -n "$NOTIFY_TARGET" ]]; then
      openclaw message send \
        --channel feishu \
        --target "$NOTIFY_TARGET" \
        --message "$MSG" \
        --json 2>/dev/null || echo "[notify] feishu send failed" >&2
    else
      echo "[notify] notify_target not set for feishu, skipping" >&2
    fi
    ;;
  discord)
    # Delegate to existing discord notification script
    SCRIPTS_DIR="$(dirname "$0")"
    bash "$SCRIPTS_DIR/notify-discord.sh" "$INSTANCE_DIR" "$EVENT" "$EXTRA" 2>/dev/null || true
    ;;
  *)
    echo "[notify] Unknown channel: $NOTIFY_CHANNEL" >&2
    ;;
esac
