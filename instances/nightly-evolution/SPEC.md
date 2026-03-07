# Nightly Evolution

每夜自动执行的 workspace 维护 + 社区调研 + memory 蒸馏。

## 设计

Recurring evo instance — 每晚由 cron reset + start。

## Phases

- Phase 0: Workspace 扫描
- Phase 1: Workspace 维护（核心文件、playbooks、symlinks、cron 健康）
- Phase 2: Memory 蒸馏（daily notes → MEMORY.md + SHARED-FACTS.md）
- Phase 3: 社区调研（OpenClaw、AI/LLM、垂直领域）— 每天
- Phase 4: 产出（git push + Discord 摘要）

## 约束

- worker_timeout: 180s per task
- worker_agent: evo（轻量 agent）
- 不允许修改 openclaw.json 或任何系统配置
- 编辑 symlink 文件前必须 readlink -f
- Discord 报告必须用 Components V2 卡片
