---
name: evo
description: "Evolution Loop — 创建和管理 evo instance（SPEC → tasks → worker 执行）"
version: 1.0.0
---

# Evo — Evolution Loop

## Scope

创建、规划、启动、监控 evo instance。当用户要求：
- 创建新的 evo instance（项目、任务集）
- 规划 tasks / 写 SPEC.md
- 启动、停止、查看 evo worker
- 调试 evo 问题

## Location

- Framework: `~/.openclaw/evo/framework/`
- Instances: `~/.openclaw/evo/instances/<name>/`
- CLI: `evo` (in PATH via `~/.zshrc`)

## Key Commands

```bash
evo create <name> "<description>"   # 创建 instance
evo plan <name>                     # SPEC.md → tasks.json（确定性 parser，不用 LLM）
evo start <name>                    # 启动 worker
evo stop <name>                     # 停止 worker
evo status [name]                   # 查看进度
evo logs <name> --follow            # 跟踪日志
evo reset <name>                    # 重置 recurring instance
evo health                          # 健康检查
evo destroy <name>                  # 停止 + 清理
```

## SPEC.md 格式（必须遵循）

每个 instance 的 `SPEC.md` 必须包含 `## Tasks` section，格式如下：

```markdown
## Tasks

### {id} {title} [{runner}]
> depends: {dep1}, {dep2}
> output: path/to/file.py

Task description. Must be self-contained — worker has no memory of other tasks.
Worker will ONLY see this description, so include all necessary context:
- Which files to read first (CLAUDE.md, DISTILL.md, etc.)
- Exact test command to run
- What to update after completion

### {id} Gate: {title} [{runner}]
> depends: {dep1}

Gate description. Verifies phase completion.

### {id} Git commit {title} [{runner}]
> depends: {gate_id}

Git commit command.
```

### Task ID 规则

- `{phase}.{number}` — 普通 task（如 `0.1`, `1.2`）
- `{phase}.G` — Gate（验证 phase 完成）
- `{phase}.C` — Git commit

### Metadata 规则

- `> depends: -` — 无依赖
- `> depends: 0.1, 0.2` — 依赖多个 task
- `> output: path/to/file.py` — 可选，gate/commit 通常省略

### Runner 选择

| Runner | 何时使用 | 计费 |
|--------|---------|------|
| `codex` | 代码生成、重构 | OpenAI 订阅 |
| `claude` | 代码/文档、gate 验证 | Claude 订阅 |
| `gemini` | 分析、生成 | Gemini 订阅 |
| `agent` | 需要 web/飞书等工具 | API token |

优先 codex/claude/gemini（订阅），避免 agent（API token）。

### Description 要求

每个 task 的 description 必须**完全自包含**，worker 没有跨 task 记忆。包含：
1. 需要先读哪些文件（完整路径）
2. 具体要做什么（步骤）
3. 测试命令（完整命令）
4. 完成后需要更新的文档

## 创建 Instance 流程

1. `evo create <name> "<description>"`
2. 编写 `SPEC.md`（包含 `## Tasks` section，格式见上）
3. `evo plan <name>` — 确定性解析 SPEC.md → tasks.json（瞬间完成）
4. 检查 `evo status <name>` 确认 tasks 正确
5. `evo start <name>` — 启动 worker

## state.json 配置

```json
{
  "worker_model": "codex",
  "codex_model": "gpt-5.4",
  "codex_workdir": "/path/to/project",
  "fallback_runner": "claude",
  "claude_model": "opus",
  "worker_timeout": 300
}
```

## 注意事项

- `evo plan` 是确定性 parser，不调用 LLM。格式错误会直接报错。
- Gate 条件用 `>=` 不用 `==`
- Worker timeout 默认 300s，大 task 要拆分
- `evo reset` 只清 task 状态，不删 output 文件
- 每个 phase 结束后应有 Git commit task
