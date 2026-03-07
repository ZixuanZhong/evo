# AI/LLM 工具链新闻 — 2026-03-06

## 🔥 重大发布

### OpenAI GPT-5.4 发布 (Mar 5)
- **三个变体**: GPT-5.4 (标准)、GPT-5.4 Thinking (推理)、GPT-5.4 Pro (高性能)
- **原生 Computer Use**: 通过 API/Codex 直接操控用户电脑，跨应用导航
- **1M token context window**
- **金融插件**: Excel/Google Sheets 原生集成
- **与我们的关系**: OpenClaw 可通过 openai provider 使用；computer use 模式可能影响 browser automation 策略
- 来源: [TechCrunch](https://techcrunch.com/2026/03/05/openai-launches-gpt-5-4-with-pro-and-thinking-versions/), [VentureBeat](https://venturebeat.com/technology/openai-launches-gpt-5-4-with-native-computer-use-mode-financial-plugins-for)

### Apple M5 Pro / M5 Max 发布 (Mar 6)
- MacBook Pro + MacBook Air with M5 发布
- **LLM 性能**: M5 Pro/Max prompt 处理速度比 M4 Pro/Max 快 4x，AI 图像生成快 8x
- **Neural Accelerator in each GPU core** — 对本地 LLM 推理有大影响
- **与我们的关系**: Caton 当前 MacBook Air 14" (Apple Silicon)，M5 Air 是潜在升级路径
- 来源: [Apple Newsroom](https://www.apple.com/newsroom/2026/03/apple-introduces-macbook-pro-with-all-new-m5-pro-and-m5-max/)

## 📊 Coding Agent 生态

### Codex 增长爆发
- GPT-5.3 Codex 发布后用户 3x 增长：**160 万周活用户**，100 万+ 桌面下载
- Codex App for Windows: 并行 agent、隔离 worktree、CLI/IDE 互操作
- 来源: [Fortune](https://fortune.com/2026/03/04/openai-codex-growth-enterprise-ai-agents/)

### Claude Code 主导 + MCP 标准化
- Pragmatic Engineer 调查显示 Claude Code 在开发者中占据主导
- Google 提交重大 MCP 协议贡献
- Agent 标准层次化: NIST 介入安全优先级设定
- 来源: [DEV Community](https://dev.to/alexmercedcoder/ai-weekly-claude-code-dominates-mcp-goes-mainstream-week-of-march-5-2026-15af)

## 🏠 Agentic AI 动态

### 多 Agent 协作实验
- every.to 报道：5 个 AI agent 在群聊中自发构建了审批流程 — agent 在人类想到之前就建立了治理框架
- 来源: [every.to](https://every.to/context-window/five-ai-agents-walk-into-a-group-chat)

### Origen DOMIA
- MWC 2026 发布：智能家居 agentic AI，理解上下文、识别意图、跨设备协调
- 来源: [AI Unplugged](https://aiunplugged.io/blog/origen-unveils-domia-at-mwc-2026-bringing-agentic-intelligence-into-the-home/)

## 📋 与我们的关联

| 动态 | 优先级 | 行动建议 |
|------|--------|---------|
| GPT-5.4 + Computer Use | 高 | 评估是否切换 alpha/tax 任务到 5.4；computer use 模式可替代部分 browser 操作 |
| Codex 160万周活 | 中 | 当前 evo worker 已用 codex 模型别名，关注 5.4 版是否有新 codex 变体 |
| MCP 标准化 + NIST | 中 | 关注 OpenClaw 的 MCP 支持进展 |
| M5 Pro/Max | 低 | Caton 硬件升级参考 |

---
*Scanned by nightly-evolution task 3.2*
