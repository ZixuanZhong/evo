#!/usr/bin/env python3
"""Auto-split: expand a task into sub-tasks based on items_file.

Usage: expand_task.py <tasks.json> <task_id> <instance_dir>

Exit codes:
  0 — expanded into sub-tasks (worker should skip execution, continue loop)
  1 — no expansion needed (items <= batch_size, worker should execute normally)
  2 — error (task will be marked failed by worker)
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone


def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.rename(tmp, path)


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
    if len(sys.argv) < 4:
        print("Usage: expand_task.py <tasks.json> <task_id> <instance_dir>", file=sys.stderr)
        sys.exit(2)

    tasks_path = sys.argv[1]
    task_id = sys.argv[2]
    instance_dir = sys.argv[3]

    data = json.load(open(tasks_path))
    tasks = data["tasks"]

    # Find the task
    task = None
    task_idx = None
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            task = t
            task_idx = i
            break

    if not task:
        print(f"[expand] Task {task_id} not found", file=sys.stderr)
        sys.exit(2)

    split_cfg = task.get("auto_split")
    if not split_cfg:
        print(f"[expand] Task {task_id} has no auto_split config", file=sys.stderr)
        sys.exit(1)

    items_file = split_cfg.get("items_file", "")
    batch_size = split_cfg.get("batch_size", 5)
    output_prefix = split_cfg.get("output_prefix", "")

    # Resolve items_file path
    items_path = os.path.join(instance_dir, items_file) if items_file else ""
    if not items_path or not os.path.isfile(items_path):
        print(f"[expand] items_file not found: {items_path}", file=sys.stderr)
        # Mark task failed
        task["status"] = "failed"
        task["error"] = f"auto_split items_file not found: {items_file}"
        update_summary(data)
        atomic_write(tasks_path, data)
        sys.exit(2)

    # Read items (non-empty lines)
    with open(items_path) as f:
        items = [line.rstrip("\n") for line in f if line.strip()]

    n = len(items)
    print(f"[expand] Task {task_id}: {n} items, batch_size={batch_size}", file=sys.stderr)

    # If N=0, mark gate as done immediately
    if n == 0:
        task["status"] = "done"
        task["type"] = "gate"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        update_summary(data)
        atomic_write(tasks_path, data)
        print(f"[expand] Task {task_id}: 0 items, marked gate done", file=sys.stderr)
        sys.exit(0)

    # If N <= batch_size, no split needed — execute normally
    if n <= batch_size:
        print(f"[expand] Task {task_id}: {n} items <= batch_size {batch_size}, no split", file=sys.stderr)
        sys.exit(1)

    # Split into sub-tasks
    import math
    num_batches = math.ceil(n / batch_size)
    sub_task_ids = []

    # Determine output file extension from output_prefix or original output_files
    output_ext = ".md"
    orig_outputs = task.get("output_files", [])
    if not orig_outputs and task.get("output_file"):
        orig_outputs = [task["output_file"]]
    if orig_outputs:
        _, ext = os.path.splitext(orig_outputs[0])
        if ext:
            output_ext = ext
    if not output_prefix:
        if orig_outputs:
            output_prefix = os.path.splitext(orig_outputs[0])[0]
        else:
            output_prefix = f"output/{task_id}"

    for i in range(num_batches):
        start = i * batch_size
        end = min((i + 1) * batch_size, n)
        batch_items = items[start:end]
        sub_id = f"{task_id}.{i + 1}"
        sub_task_ids.append(sub_id)

        batch_text = "\n".join(batch_items)
        sub_output = f"{output_prefix}.{i + 1}{output_ext}"

        sub_task = {
            "id": sub_id,
            "phase": task.get("phase", 0),
            "title": f"{task.get('title', '')} [{start + 1}-{end}/{n}]",
            "description": (
                f"{task.get('description', '')}\n\n"
                f"## 本批待处理项 ({start + 1}-{end}, 共 {n} 条)\n\n"
                f"{batch_text}"
            ),
            "depends_on": list(task.get("depends_on", [])),
            "output_files": [sub_output],
            "status": "pending",
            "type": "task",
            "priority": task.get("priority", "medium"),
            "runner": task.get("runner", "agent"),
            "attempts": 0,
            "started_at": None,
            "completed_at": None,
            "error": None,
        }

        # Copy spec_file if present
        if task.get("spec_file"):
            sub_task["spec_file"] = task["spec_file"]

        tasks.append(sub_task)

    # Convert original task to gate
    task["type"] = "gate"
    task["status"] = "pending"
    task["depends_on"] = sub_task_ids
    task["started_at"] = None
    task["description"] = (
        f"Gate: 等待 {num_batches} 个子任务完成。\n"
        f"原始任务: {task.get('title', '')}\n"
        f"子任务: {', '.join(sub_task_ids)}"
    )
    # Gate output_files = all sub-task outputs (for downstream reference)
    task["output_files"] = [f"{output_prefix}.{i + 1}{output_ext}" for i in range(num_batches)]
    # Clear auto_split so gate doesn't re-expand
    del task["auto_split"]

    update_summary(data)
    atomic_write(tasks_path, data)

    print(f"[expand] Task {task_id} expanded into {num_batches} sub-tasks: {', '.join(sub_task_ids)}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
