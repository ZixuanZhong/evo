#!/usr/bin/env python3
"""Append structured JSONL log entry for task execution."""

import json
import sys
import os
from datetime import datetime, timezone


def main():
    if len(sys.argv) < 4:
        print("Usage: log_task.py <instance_dir> <task_id> <event> [extra_json]", file=sys.stderr)
        print("  event: started | completed | failed | escalated | planner_run", file=sys.stderr)
        sys.exit(1)

    instance_dir = sys.argv[1]
    task_id = sys.argv[2]
    event = sys.argv[3]
    extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}

    log_file = os.path.join(instance_dir, "logs", "task-log.jsonl")
    tasks_file = os.path.join(instance_dir, "tasks.json")

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "event": event,
    }

    # Enrich from tasks.json if available
    if os.path.exists(tasks_file):
        try:
            with open(tasks_file) as f:
                data = json.load(f)
            for t in data.get("tasks", []):
                if t["id"] == task_id:
                    entry["title"] = t.get("title", "")
                    entry["phase"] = t.get("phase", "")
                    entry["status"] = t.get("status", "")
                    entry["attempts"] = t.get("attempts", 0)
                    if t.get("error"):
                        entry["error"] = t["error"]
                    break
            entry["plan_version"] = data.get("plan_version", 0)
        except (json.JSONDecodeError, KeyError):
            pass

    entry.update(extra)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
