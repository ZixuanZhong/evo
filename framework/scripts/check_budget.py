#!/usr/bin/env python3
"""Check if daily task budget allows more executions."""

import json
import sys
from datetime import date


def main():
    if len(sys.argv) < 2:
        print("Usage: check_budget.py <state.json>", file=sys.stderr)
        sys.exit(1)

    state_path = sys.argv[1]
    with open(state_path) as f:
        state = json.load(f)

    today = str(date.today())
    budget_date = state.get("budget_date", "")
    tasks_today = state.get("tasks_today", 0)
    budget_daily = state.get("budget_daily", 50)

    if budget_date != today:
        # New day, budget resets
        sys.exit(0)

    if tasks_today >= budget_daily:
        print(f"Budget exhausted: {tasks_today}/{budget_daily} tasks today", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
