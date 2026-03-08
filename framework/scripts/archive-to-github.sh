#!/usr/bin/env bash
# Archive completed evo instance to GitHub
# Usage: archive-to-github.sh <instance_dir>
set -uo pipefail

INSTANCE_DIR="$1"
INSTANCE_NAME=$(basename "$INSTANCE_DIR")
REPO="${EVO_ARCHIVE_REPO:-}"
[[ -n "$REPO" ]] || { echo "[archive] EVO_ARCHIVE_REPO not set, skipping archive" >&2; exit 0; }
CLONE_DIR="${TMPDIR:-/tmp}/evo-instances-push-$$"

log() { echo "[archive] $*"; }

# Clone
log "Cloning $REPO..."
gh repo clone "$REPO" "$CLONE_DIR" 2>/dev/null || {
  log "ERROR: Failed to clone $REPO"
  exit 1
}

# Sync instance (exclude temp/runtime files)
log "Syncing $INSTANCE_NAME..."
mkdir -p "$CLONE_DIR/$INSTANCE_NAME"
rsync -av --delete \
  --exclude='.pids' \
  --exclude='logs/*.log' \
  --exclude='logs/.worker-prompt-*' \
  --exclude='*.lock' \
  --exclude='*.tmp' \
  "$INSTANCE_DIR/" "$CLONE_DIR/$INSTANCE_NAME/" >/dev/null 2>&1

cd "$CLONE_DIR"
git add -A

# Check if there are changes
if git diff --cached --quiet 2>/dev/null; then
  log "No changes to push for $INSTANCE_NAME"
  rm -rf "$CLONE_DIR"
  exit 0
fi

git commit -m "archive: $INSTANCE_NAME ($(date '+%Y-%m-%d %H:%M'))" >/dev/null 2>&1
git push origin main >/dev/null 2>&1 && {
  log "Pushed $INSTANCE_NAME to $REPO"
} || {
  log "ERROR: Failed to push"
}

rm -rf "$CLONE_DIR"
