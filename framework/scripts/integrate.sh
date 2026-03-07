#!/usr/bin/env bash
# Phase 5: Knowledge Integration — route evo outputs to memory system
# Usage: integrate.sh <instance_name>
set -uo pipefail

EVO_ROOT="${EVO_ROOT:-$HOME/.openclaw/evo}"
INSTANCE_NAME="${1:-}"
[[ -n "$INSTANCE_NAME" ]] || { echo "Usage: integrate.sh <instance_name>" >&2; exit 1; }

INSTANCE_DIR="$EVO_ROOT/instances/$INSTANCE_NAME"
TASKS_FILE="$INSTANCE_DIR/tasks.json"
OUTPUT_DIR="$INSTANCE_DIR/output"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"

[[ -d "$INSTANCE_DIR" ]] || { echo "Instance '$INSTANCE_NAME' not found" >&2; exit 1; }
[[ -d "$OUTPUT_DIR" ]] || { echo "No output/ directory in $INSTANCE_NAME" >&2; exit 0; }

echo "Phase 5: Knowledge Integration for '$INSTANCE_NAME'"
echo ""

# List outputs with sizes
total_size=0
file_count=0
for f in "$OUTPUT_DIR"/*; do
  [[ -f "$f" ]] || continue
  size=$(wc -c < "$f" | tr -d ' ')
  total_size=$((total_size + size))
  file_count=$((file_count + 1))
  fname=$(basename "$f")

  # Determine integration mode
  if [[ $size -lt 5120 ]]; then
    mode="merge"
  elif [[ $size -lt 20480 ]]; then
    mode="create"
  else
    mode="extract+reference"
  fi

  echo "  $fname ($size bytes) → mode: $mode"
done

if [[ $file_count -eq 0 ]]; then
  echo "No output files to integrate."
  exit 0
fi

echo ""
echo "Total: $file_count files, $total_size bytes"
echo ""
echo "Integration requires human review. Suggested routing:"
echo ""

# Generate routing suggestions based on filename patterns
for f in "$OUTPUT_DIR"/*; do
  [[ -f "$f" ]] || continue
  fname=$(basename "$f")
  size=$(wc -c < "$f" | tr -d ' ')

  # Guess target based on name
  target="(review needed)"
  case "$fname" in
    *lesson* | *learning*)  target="append → memory/semantic/lessons.md" ;;
    *sql* | *query*)        target="append → memory/procedures/sql_patterns.md" ;;
    *procedure* | *sop* | *howto*) target="→ memory/procedures/" ;;
    *reference* | *links*)  target="→ memory/semantic/${fname%.md}_references.md" ;;
    *)
      if [[ $size -lt 5120 ]]; then
        target="merge → memory/semantic/$fname"
      else
        target="→ memory/semantic/$fname (or extract key facts)"
      fi
      ;;
  esac

  echo "  $fname → $target"
done

echo ""
echo "Run 'evo plan $INSTANCE_NAME' to trigger Planner for integration tasks,"
echo "or manually move files to the appropriate memory/ location."
