# SPEC.md Task Format

## Overview

SPEC.md 的 `## Tasks` section 使用结构化 markdown 定义 tasks，可被 `spec2tasks.py` 直接解析为 tasks.json，不需要 LLM。

## Format

```markdown
## Tasks

### 0.1 Task title [runner]
> depends: -
> output: path/to/output.py

Description text. Can be multiple lines/paragraphs.
This is ALL the worker sees — must be self-contained.

### 0.2 Another task [runner]
> depends: 0.1
> output: path/to/file1.py, path/to/file2.py

Description for task 0.2.

### 0.G Gate: Phase 0 verification [runner]
> depends: 0.1, 0.2

Gate tasks have no output files. They verify phase completion.

### 0.C Git commit Phase 0 [runner]
> depends: 0.G

Commit tasks.
```

## Rules

1. **Task header**: `### {id} {title} [{runner}]`
   - `id`: `{phase}.{number}` (e.g. `0.1`, `1.2`, `2.G`, `3.C`)
   - `title`: free text
   - `runner`: one of `codex`, `claude`, `gemini`, `agent`
   - IDs ending in `.G` are gates, `.C` are commits

2. **Metadata lines** (immediately after header, `>` blockquote):
   - `> depends: {id}, {id}, ...` or `> depends: -` for no dependencies
   - `> output: {path}, {path}, ...` (optional, omit for gates/commits)

3. **Description**: everything after metadata until next `###` header

4. **Phase grouping**: inferred from task id prefix (all `0.x` = Phase 0)

## Required Fields

- id ✓ (from header)
- title ✓ (from header)  
- runner ✓ (from header)
- depends ✓ (from metadata)
- description ✓ (body text)

## Validation

Run `spec2tasks.py --validate` to check format without writing tasks.json.
