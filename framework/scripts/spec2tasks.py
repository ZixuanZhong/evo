#!/usr/bin/env python3
"""Parse SPEC.md ## Tasks section into tasks.json.

Usage:
    spec2tasks.py <instance_dir>              # Generate tasks.json
    spec2tasks.py <instance_dir> --validate   # Validate only, don't write
    spec2tasks.py <instance_dir> --dry-run    # Print tasks.json to stdout

Format: see docs/SPEC-FORMAT.md
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# ─── Parser ──────────────────────────────────────────

# ### 0.1 Task title [codex]
TASK_HEADER_RE = re.compile(
    r"^###\s+"
    r"(?P<id>\d+\.\w+)\s+"      # id: 0.1, 1.G, 2.C
    r"(?P<title>.+?)\s+"        # title (greedy until last [...])
    r"\[(?P<runner>\w+)\]\s*$"  # [codex]
)

# > depends: 0.1, 0.2
DEPENDS_RE = re.compile(r"^>\s*depends:\s*(?P<deps>.+)$", re.IGNORECASE)

# > output: path/to/file.py, path/to/other.py
OUTPUT_RE = re.compile(r"^>\s*output:\s*(?P<paths>.+)$", re.IGNORECASE)

VALID_RUNNERS = {"codex", "claude", "gemini", "agent"}


def parse_spec_tasks(spec_path: str | Path) -> list[dict]:
    """Parse ## Tasks section from SPEC.md into task dicts."""
    spec_path = Path(spec_path)
    text = spec_path.read_text(encoding="utf-8")

    # Find ## Tasks section
    tasks_match = re.search(r"^## Tasks\s*$", text, re.MULTILINE)
    if not tasks_match:
        raise ValueError(f"No '## Tasks' section found in {spec_path}")

    tasks_text = text[tasks_match.end():]

    # Stop at next ## header (if any)
    next_section = re.search(r"^## ", tasks_text, re.MULTILINE)
    if next_section:
        tasks_text = tasks_text[:next_section.start()]

    tasks: list[dict] = []
    current: dict | None = None
    desc_lines: list[str] = []

    def flush():
        nonlocal current, desc_lines
        if current is not None:
            current["description"] = "\n".join(desc_lines).strip()
            tasks.append(current)
            current = None
            desc_lines = []

    for line in tasks_text.splitlines():
        header = TASK_HEADER_RE.match(line)
        if header:
            flush()
            task_id = header.group("id")
            current = {
                "id": task_id,
                "title": header.group("title").strip(),
                "runner": header.group("runner").strip().lower(),
                "depends_on": [],
                "output_files": [],
                "phase": f"Phase {task_id.split('.')[0]}",
                "type": "gate" if task_id.endswith(".G") else "task",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "error": None,
                "attempts": 0,
            }
            continue

        if current is None:
            continue

        # Metadata lines (> depends: ... / > output: ...)
        dep_match = DEPENDS_RE.match(line)
        if dep_match:
            deps_str = dep_match.group("deps").strip()
            if deps_str != "-":
                current["depends_on"] = [
                    d.strip() for d in deps_str.split(",") if d.strip()
                ]
            continue

        out_match = OUTPUT_RE.match(line)
        if out_match:
            current["output_files"] = [
                p.strip() for p in out_match.group("paths").split(",") if p.strip()
            ]
            continue

        # Skip empty blockquote lines that aren't metadata
        if re.match(r"^>\s*$", line):
            continue

        desc_lines.append(line)

    flush()
    return tasks


# ─── Validator ───────────────────────────────────────

def validate_tasks(tasks: list[dict]) -> list[str]:
    """Validate parsed tasks. Returns list of error strings (empty = valid)."""
    errors: list[str] = []

    if not tasks:
        errors.append("No tasks found in ## Tasks section")
        return errors

    ids = {t["id"] for t in tasks}

    for t in tasks:
        tid = t["id"]
        prefix = f"Task {tid}"

        # Required fields
        if not t.get("title"):
            errors.append(f"{prefix}: missing title")
        if not t.get("runner"):
            errors.append(f"{prefix}: missing runner")
        if t.get("runner") and t["runner"] not in VALID_RUNNERS:
            errors.append(f"{prefix}: invalid runner '{t['runner']}' (valid: {VALID_RUNNERS})")
        if not t.get("description"):
            errors.append(f"{prefix}: missing description")

        # Dependency validation
        for dep in t.get("depends_on", []):
            if dep not in ids:
                errors.append(f"{prefix}: depends on unknown task '{dep}'")

        # Gate naming convention
        if t["type"] == "gate" and "gate" not in t.get("title", "").lower():
            errors.append(f"{prefix}: gate task title should contain 'Gate' (convention)")

    # Check for dependency cycles (simple DFS)
    def has_cycle(task_id: str, visited: set, stack: set) -> bool:
        visited.add(task_id)
        stack.add(task_id)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if task:
            for dep in task.get("depends_on", []):
                if dep in stack:
                    return True
                if dep not in visited and has_cycle(dep, visited, stack):
                    return True
        stack.discard(task_id)
        return False

    visited: set[str] = set()
    for t in tasks:
        if t["id"] not in visited:
            if has_cycle(t["id"], visited, set()):
                errors.append(f"Dependency cycle detected involving task {t['id']}")
                break

    return errors


# ─── tasks.json generation ───────────────────────────

def build_tasks_json(tasks: list[dict], version: int = 1) -> dict:
    """Build the full tasks.json structure."""
    pending = sum(1 for t in tasks if t["status"] == "pending")
    done = sum(1 for t in tasks if t["status"] == "done")
    phases = sorted(set(t["phase"] for t in tasks))

    return {
        "tasks": tasks,
        "summary": f"{len(tasks)} tasks ({pending} pending, {done} done), phases: {', '.join(phases)}",
        "plan_version": version,
        "phase": phases[0] if phases else "",
        "planner_trigger": False,
    }


# ─── CLI ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    instance_dir = Path(sys.argv[1])
    validate_only = "--validate" in sys.argv
    dry_run = "--dry-run" in sys.argv

    spec_file = instance_dir / "SPEC.md"
    tasks_file = instance_dir / "tasks.json"

    if not spec_file.exists():
        print(f"ERROR: {spec_file} not found", file=sys.stderr)
        sys.exit(1)

    # Parse
    try:
        tasks = parse_spec_tasks(spec_file)
    except ValueError as e:
        print(f"PARSE ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate
    errors = validate_tasks(tasks)
    if errors:
        print(f"VALIDATION ERRORS ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Parsed {len(tasks)} tasks, 0 errors", file=sys.stderr)

    if validate_only:
        # Print summary
        for t in tasks:
            deps = ", ".join(t["depends_on"]) or "-"
            print(f"  {t['id']} {t['title']} [{t['runner']}] deps={deps}")
        sys.exit(0)

    # Read existing plan_version
    version = 1
    if tasks_file.exists():
        try:
            existing = json.loads(tasks_file.read_text())
            version = existing.get("plan_version", 0) + 1
        except (json.JSONDecodeError, KeyError):
            pass

    result = build_tasks_json(tasks, version)

    if dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Atomic write
    fd, tmp = tempfile.mkstemp(
        dir=str(instance_dir), suffix=".tmp"
    )
    with os.fdopen(fd, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.rename(tmp, str(tasks_file))

    print(f"✓ Written {tasks_file} (v{version}, {len(tasks)} tasks)", file=sys.stderr)


if __name__ == "__main__":
    main()
