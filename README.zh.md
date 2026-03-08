# Evo — OpenClaw 进化循环框架

一个任务编排框架，将复杂项目拆分为分阶段、依赖追踪的任务，由 AI agent 自动执行。基于 [OpenClaw](https://github.com/openclaw/openclaw) 构建。

## 工作原理

```
SPEC.md → 规划器 → tasks.json → Worker 循环 → 输出文件
              ↑                        ↓
              └─── Gate 通过 ──────────┘
```

1. **你**编写 `SPEC.md`，定义阶段、任务和关卡
2. **规划器**（AI）将规格转化为结构化的 `tasks.json`
3. **Worker 循环**按依赖顺序选取任务，通过 OpenClaw agent 或 Claude CLI 执行
4. **Gate**（关卡）验证阶段完成后才解锁下一阶段
5. **熔断器**在连续失败后暂停；**自动升级**在任务反复失败后触发

## 特性

- 🔄 **分阶段执行** — 任务按阶段组织，Gate 控制推进
- 🔀 **多 Runner** — `agent`（完整工具）、`claude` / `codex` / `gemini`（本地 CLI，用订阅）
- 🧩 **自动拆分** — `auto_split` 运行时按上游产出动态拆分子任务，避免超时
- 🛡️ **防卡死机制** — L0 超时重置、L0.5 死锁破解、L0.75 自动升级
- 📊 **预算控制** — 每日任务限额，防止失控
- 🔔 **Discord 通知** — Gate 通过、完成、熔断（可选）
- 📦 **GitHub 归档** — 自动归档已完成实例（可选）
- 🔁 **循环实例** — 基于模板重置，适合定时/周期任务
- 📋 **结构化日志** — JSONL 任务日志 + Worker 日志自动轮转

## 系统要求

- [OpenClaw](https://github.com/openclaw/openclaw) 已安装并运行
- Python 3.8+
- Bash 4+
- （可选）`gh` CLI — 用于 GitHub 归档
- （可选）`claude` CLI — 用于双 Runner 模式

## 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USER/evo.git ~/.openclaw/evo

# 给 CLI 加执行权限
chmod +x ~/.openclaw/evo/framework/evo

# 加入 PATH（添加到 ~/.zshrc 或 ~/.bashrc）
export PATH="$HOME/.openclaw/evo/framework:$PATH"

# （可选）配置环境变量
cp ~/.openclaw/evo/framework/.env.example ~/.openclaw/evo/.env
# 编辑 .env 填入你的设置
```

## 快速开始

### 1. 创建实例

```bash
evo create my-research "关于某个主题的调研项目"
```

会在 `~/.openclaw/evo/instances/my-research/` 下创建：
- `SPEC.md` — 项目规格书（编辑它！）
- `tasks.json` — 任务注册表（自动管理）
- `state.json` — 运行时状态

### 2. 编写 SPEC

编辑 `SPEC.md`：

```markdown
# my-research — SPEC

## 背景
调研用 LLM 做代码分析的可行性。

## 目标
1. 调研现有工具和方案
2. 设计原型架构
3. 估算成本和时间线

## 阶段 0：知识构建
| ID  | 标题             | 依赖   | 输出                      |
|-----|------------------|--------|---------------------------|
| 0.1 | 调研 LLM 工具    | —      | `knowledge/llm-tools.md`  |
| 0.2 | 调研代码分析器   | —      | `knowledge/analyzers.md`  |
| 0.G | Gate：阶段 0 完成 | 0.1, 0.2 | —                       |

## 阶段 1：设计
| ID  | 标题             | 依赖   | 输出                      |
|-----|------------------|--------|---------------------------|
| 1.1 | 架构设计         | 0.G    | `output/architecture.md`  |
| 1.G | Gate：阶段 1 完成 | 1.1   | —                         |
```

### 3. 规划 & 启动

```bash
# 从 SPEC 生成任务（调用 AI 规划器）
evo plan my-research

# 启动 Worker 循环
evo start my-research

# 查看进度
evo status my-research

# 跟踪日志
evo logs my-research --follow
```

### 4. 查看结果

```bash
evo status my-research
# ✅ 0.1 调研 LLM 工具
# ✅ 0.2 调研代码分析器
# ✅ 0.G Gate：阶段 0 完成 [GATE]
# 🔵 1.1 架构设计
# ⬜ 1.G Gate：阶段 1 完成 [GATE]
```

输出文件在 `instances/my-research/knowledge/` 和 `instances/my-research/output/`。

## 示例

### 示例 1：调研项目（一次性）

见 [examples/research-project/](examples/research-project/) — 一个一次性调研实例：调研课题、综合发现、产出报告。

```bash
# 从示例创建
cp -r examples/research-project ~/.openclaw/evo/instances/my-research
evo plan my-research
evo start my-research
```

**SPEC.md 概要：**

```markdown
# 阶段 0：知识构建
| 0.1 | 技术调研       | — | knowledge/tech-survey.md |
| 0.2 | 竞品分析       | — | knowledge/competitors.md |
| 0.G | Gate：阶段 0   | 0.1, 0.2 | — |

# 阶段 1：综合分析
| 1.1 | 架构设计       | 0.G | output/architecture.md |
| 1.2 | 成本估算       | 0.G | output/cost-model.md |
| 1.G | Gate：阶段 1   | 1.1, 1.2 | — |

# 阶段 2：报告
| 2.1 | 最终报告       | 1.G | output/final-report.md |
| 2.G | Gate：完成     | 2.1 | — |
```

### 示例 2：循环夜间任务（Nightly Evolution）

见 [examples/nightly-evolution/](examples/nightly-evolution/) — 每晚定时运行的循环实例：扫描工作区、审查配置、蒸馏记忆、社区调研。

```bash
# 安装模板（用于 evo reset 重建）
mkdir -p ~/.openclaw/evo/framework/templates/nightly-evolution
cp examples/nightly-evolution/tasks.json \
   ~/.openclaw/evo/framework/templates/nightly-evolution/tasks.json

# 创建实例
cp -r examples/nightly-evolution ~/.openclaw/evo/instances/nightly-evolution

# 配置 cron（每天凌晨 2:30 运行）
# 在 OpenClaw cron 中设置：
#   evo reset nightly-evolution && evo start nightly-evolution
```

**循环实例的工作方式：**

```bash
# evo reset 从模板重建 tasks.json，所有任务回到 pending
evo reset nightly-evolution

# 如果 worker 还在跑，reset 会拒绝（除非超过 1 小时视为 stale）
evo reset nightly-evolution --force  # 强制重置
```

**tasks.json 示例（5 阶段 12 任务）：**

```
P0: 工作区扫描
P1: 核心文件审查 / Playbook 审查 / Symlink 检查 / 脚本健康
P2: 记忆蒸馏 / 共享事实同步
P3: 社区调研 × 3
P4: Git 推送 + 总结报告
```

### 示例 3：批量处理（auto_split）

见 [examples/batch-processing/](examples/batch-processing/) — 展示 `auto_split` 运行时动态拆分。任务 0.1 扫描文件列表，任务 1.1 根据列表大小自动拆分子任务。

```bash
cp -r examples/batch-processing ~/.openclaw/evo/instances/my-batch
# 编辑 SPEC.md 适配你的场景
evo start my-batch
```

**tasks.json 关键任务：**

```json
{
  "id": "1.1",
  "title": "处理所有文件",
  "auto_split": {
    "items_file": "output/file-list.txt",
    "batch_size": 5,
    "output_prefix": "output/processed"
  }
}
```

如果 `file-list.txt` 有 12 条，`batch_size: 5`，worker 自动创建：
- `1.1.1` — 第 1-5 条 → `output/processed.1.md`
- `1.1.2` — 第 6-10 条 → `output/processed.2.md`
- `1.1.3` — 第 11-12 条 → `output/processed.3.md`
- `1.1` 变成 gate，等待所有子任务完成

## Runner 选择

每个任务有 `runner` 字段：

- **`agent`** — `openclaw agent`，完整工具（网搜、插件）。消耗 API token。适合需要联网的调研任务。
- **`claude`** — `claude -p`，纯本地工具。使用 Claude 订阅。快、省。适合代码生成、文档编写。
- **`codex`** — `codex exec`，本地工具 + 可选网搜。使用 OpenAI 订阅。全自动模式。适合代码生成、重构。
- **`gemini`** — `gemini -p`，沙盒本地工具。使用 Gemini 订阅。Yolo 模式。适合分析、写作。

> **省钱建议**：不需要网搜或 OpenClaw 插件时，优先用 `claude`/`codex`/`gemini`（订阅制）。

## CLI 参考

| 命令 | 说明 |
|------|------|
| `evo create <name> "<desc>"` | 创建新实例 |
| `evo start <name>` | 启动 Worker 循环（后台） |
| `evo stop <name>` | 停止 Worker 循环 |
| `evo status [name]` | 查看状态（全部或单个） |
| `evo status --json` | 机器可读 JSON 状态 |
| `evo logs <name> [--follow]` | 查看 Worker 日志 |
| `evo plan <name>` | 运行 AI 规划器 |
| `evo reset <name> [--force]` | 重置任务为 pending |
| `evo integrate <name>` | 显示输出路由建议 |
| `evo health` | 系统健康检查（JSON） |
| `evo destroy <name>` | 停止 + 移到废纸篓 |
| `evo bootstrap` | 重启后恢复活跃实例 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EVO_ROOT` | `~/.openclaw/evo` | 基目录 |
| `EVO_DISCORD_CHANNEL` | _(无)_ | Discord 频道 ID，用于通知 |
| `EVO_MENTION` | _(无)_ | Discord @ 提及，如 `<@USER_ID>` |
| `EVO_ARCHIVE_REPO` | _(无)_ | GitHub 归档仓库，如 `user/repo` |
| `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace` | OpenClaw 工作区路径 |

在 `~/.openclaw/evo/.env` 中设置（CLI 自动加载）。

## state.json 字段

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `worker_model` | `sonnet` | Worker 任务使用的模型 |
| `planner_model` | `opus` | 规划器使用的模型 |
| `worker_agent` | `evo` | `agent` runner 使用的 OpenClaw agent ID |
| `worker_timeout` | `600` | 每个任务的超时（秒） |
| `budget_daily` | `50` | 每日最大任务数 |
| `recurring` | `false` | 是否支持从模板 `evo reset` |

## 自动拆分（auto_split）

当任务的工作量取决于上游任务的输出（比如「处理 N 个文档」，N 在规划时未知），使用 `auto_split` 在运行时自动拆分子任务。

### 工作流程

```
任务 0.1 产出 file-list.txt（N 条）
    ↓
任务 1.1 带 auto_split → worker 读 file-list.txt
    ↓ N > batch_size?
    ├── 是 → 拆成 1.1.1, 1.1.2, ... 子任务
    │        1.1 变成 gate，依赖所有子任务
    └── 否 → 正常执行 1.1（不拆）
    ↓
任务 2.1 依赖 1.1（gate）→ 所有子任务完成后执行
```

### 配置方式

在 `tasks.json` 的任务上添加 `auto_split` 字段：

```json
{
  "id": "1.1",
  "title": "处理所有文档",
  "depends_on": ["0.1"],
  "auto_split": {
    "items_file": "output/file-list.txt",
    "batch_size": 5,
    "output_prefix": "output/processed"
  }
}
```

| 字段 | 说明 |
|------|------|
| `items_file` | 待处理项清单（一行一条），由上游任务产出 |
| `batch_size` | 每个子任务处理的条目数（调整以不超时） |
| `output_prefix` | 子任务输出文件前缀：`{prefix}.1.md`, `{prefix}.2.md`, ... |

### 边界情况

| 场景 | 行为 |
|------|------|
| `items_file` 不存在 | 任务标记 `failed` |
| 0 条 | Gate 直接标记 `done` |
| N ≤ batch_size | 不拆，正常执行 |
| 子任务失败 | L0/L0.5/L0.75 正常处理重试 |

### 示例

见 [examples/batch-processing/](examples/batch-processing/) — 扫描文件 → 自动拆分批处理 → 汇总结果。

## 防卡死机制

| 层级 | 触发条件 | 动作 |
|------|----------|------|
| L0 | 任务 `in_progress` 超过 15 分钟 | 重置为 `pending`，累加 attempts |
| L0.5 | 所有 pending 任务被 failed 依赖阻塞 | 重置 failed 依赖，或触发规划器 |
| L0.75 | 任务 attempts ≥ 5 | 自动升级为 `escalated`，触发规划器重新设计 |
| 熔断器 | 连续 5 次失败 | 暂停 1 小时，Discord 通知 |

## 目录结构

```
~/.openclaw/evo/
├── .env                          # 本地配置（gitignore）
├── .gitignore
├── framework/
│   ├── evo                       # CLI 入口
│   ├── CLAUDE.md                 # Worker 上下文指令
│   ├── .env.example              # 配置模板
│   ├── scripts/                  # 核心脚本
│   └── templates/                # 实例模板
├── instances/                    # 运行实例（gitignore）
└── examples/                     # 示例项目
    ├── research-project/         # 一次性调研
    ├── nightly-evolution/        # 循环夜间任务
    └── batch-processing/         # auto_split 示例
```

## 许可证

MIT
