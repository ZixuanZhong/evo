#!/usr/bin/env python3
"""Pick next executable task from tasks.json with anti-stuck mechanisms (L0/L0.5/L0.75)."""

import json
import sys
import os
import tempfile
import time
import fcntl
from datetime import datetime, timezone

STALE_THRESHOLD = 900  # 15 minutes (accounts for openclaw agent startup overhead)
MAX_ATTEMPTS = 5
FAILED_RETRY_COOLDOWN = 120  # 2 minutes before auto-retrying a failed task


def load_tasks(path):
    with open(path) as f:
        return json.load(f)


def save_tasks(path, data):
    """Atomic write: tmpfile + rename."""
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.rename(tmp_path, path)


def now_ts():
    return datetime.now(timezone.utc).isoformat()


def parse_ts(ts_str):
    if not ts_str:
        return 0
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0


def l0_stale_reset(tasks):
    """L0: Reset tasks stuck in_progress for >10 minutes."""
    now = time.time()
    changed = False
    for t in tasks:
        if t["status"] == "in_progress":
            started = parse_ts(t.get("started_at"))
            if started > 0 and (now - started) > STALE_THRESHOLD:
                t["status"] = "pending"
                t["attempts"] = t.get("attempts", 0) + 1
                t["error"] = f"L0: stale reset after {STALE_THRESHOLD}s"
                t["started_at"] = None
                changed = True
                print(f"[L0] Reset stale task {t['id']}: {t['title']}", file=sys.stderr)
    return changed


def l0_75_auto_escalate(tasks):
    """L0.75: Escalate pending tasks with attempts >= MAX_ATTEMPTS."""
    changed = False
    trigger_planner = False
    for t in tasks:
        if t["status"] == "pending" and t.get("attempts", 0) >= MAX_ATTEMPTS:
            t["status"] = "escalated"
            t["error"] = f"L0.75: auto-escalated after {t['attempts']} attempts"
            changed = True
            trigger_planner = True
            print(f"[L0.75] Escalated task {t['id']}: {t['title']} (attempts={t['attempts']})", file=sys.stderr)
    return changed, trigger_planner


def l0_25_failed_retry(tasks):
    """L0.25: Auto-retry failed tasks after cooldown if attempts < MAX_ATTEMPTS.

    Without this, a single failed gate blocks all downstream tasks and workers
    idle forever because L0.5 only fires when *all* pending tasks are directly
    blocked by a failed dep (transitive blocks are missed).

    This mechanism simply resets any failed task back to pending after a short
    cooldown, giving it another chance.  MAX_ATTEMPTS still caps total retries.
    """
    now = time.time()
    changed = False
    for t in tasks:
        if t["status"] != "failed":
            continue
        if t.get("attempts", 0) >= MAX_ATTEMPTS:
            continue
        # Use started_at (last attempt start) or fall back to a short cooldown
        last_attempt = parse_ts(t.get("started_at")) or parse_ts(t.get("failed_at"))
        if last_attempt > 0 and (now - last_attempt) < FAILED_RETRY_COOLDOWN:
            continue
        t["status"] = "pending"
        t["error"] = f"L0.25: auto-retry after cooldown (attempt {t.get('attempts', 0)}/{MAX_ATTEMPTS})"
        t["started_at"] = None
        changed = True
        print(f"[L0.25] Auto-retry failed task {t['id']}: {t['title']} (attempt {t.get('attempts', 0)})", file=sys.stderr)
    return changed


def l0_5_dependency_deadlock(tasks):
    """L0.5: Detect and break dependency deadlocks."""
    task_map = {t["id"]: t for t in tasks}
    pending = [t for t in tasks if t["status"] == "pending"]
    if not pending:
        return False, False

    # Check if ALL pending tasks are blocked
    all_blocked = True
    for t in pending:
        deps = t.get("depends_on", [])
        if not deps:
            all_blocked = False
            break
        blocked = False
        for dep_id in deps:
            dep = task_map.get(dep_id)
            if dep and dep["status"] in ("failed", "escalated"):
                blocked = True
                break
        if not blocked:
            all_blocked = False
            break

    if not all_blocked:
        return False, False

    # All pending tasks are blocked by failed/escalated deps
    changed = False
    trigger_planner = False
    failed_deps = set()
    for t in pending:
        for dep_id in t.get("depends_on", []):
            dep = task_map.get(dep_id)
            if dep and dep["status"] == "failed":
                failed_deps.add(dep_id)

    # Try to reset failed deps
    all_exhausted = True
    for dep_id in failed_deps:
        dep = task_map[dep_id]
        if dep.get("attempts", 0) < MAX_ATTEMPTS:
            dep["status"] = "pending"
            dep["error"] = "L0.5: reset by deadlock breaker"
            changed = True
            all_exhausted = False
            print(f"[L0.5] Reset failed dep {dep_id}", file=sys.stderr)

    if all_exhausted and failed_deps:
        trigger_planner = True
        print("[L0.5] All failed deps exhausted, triggering planner", file=sys.stderr)

    return changed, trigger_planner


def pick_next(tasks):
    """Pick next executable pending task."""
    task_map = {t["id"]: t for t in tasks}

    candidates = []
    for t in tasks:
        if t["status"] != "pending":
            continue
        if t.get("attempts", 0) >= MAX_ATTEMPTS:
            continue

        # Check dependencies
        deps_met = True
        for dep_id in t.get("depends_on", []):
            dep = task_map.get(dep_id)
            if not dep or dep["status"] != "done":
                deps_met = False
                break
        if not deps_met:
            continue

        candidates.append(t)

    if not candidates:
        return None

    # Priority order: high > medium > low, then by ID
    priority_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda t: (priority_order.get(t.get("priority", "medium"), 1), t["id"]))
    return candidates[0]


def update_summary(data):
    tasks = data["tasks"]
    data["summary"] = {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t["status"] == "pending"),
        "in_progress": sum(1 for t in tasks if t["status"] == "in_progress"),
        "done": sum(1 for t in tasks if t["status"] == "done"),
        "failed": sum(1 for t in tasks if t["status"] == "failed"),
        "escalated": sum(1 for t in tasks if t["status"] == "escalated"),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: pick_next_task.py <tasks.json>", file=sys.stderr)
        sys.exit(1)

    tasks_path = sys.argv[1]
    lock_path = tasks_path + ".lock"

    # Acquire exclusive lock to prevent concurrent picks
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[pick] Lock held by another process, skipping", file=sys.stderr)
        sys.exit(1)

    try:
        data = load_tasks(tasks_path)
        tasks = data["tasks"]

        changed = False
        trigger_planner = False

        # L0: stale reset
        if l0_stale_reset(tasks):
            changed = True

        # L0.25: auto-retry failed tasks after cooldown
        if l0_25_failed_retry(tasks):
            changed = True

        # L0.5: dependency deadlock
        c, tp = l0_5_dependency_deadlock(tasks)
        if c:
            changed = True
        if tp:
            trigger_planner = True

        # L0.75: auto-escalate
        c, tp = l0_75_auto_escalate(tasks)
        if c:
            changed = True
        if tp:
            trigger_planner = True

        if trigger_planner:
            data["planner_trigger"] = True

        # Pick next task
        task = pick_next(tasks)

        if task:
            task["status"] = "in_progress"
            task["started_at"] = now_ts()
            task["attempts"] = task.get("attempts", 0) + 1
            changed = True

        if changed:
            update_summary(data)
            save_tasks(tasks_path, data)

        if task:
            # Output task ID for worker to use
            print(task["id"])
        else:
            # No task available
            sys.exit(1)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()
