# AI/LLM 工具链新闻 — 2026-03-08

## 🔥 March 2026 AI 模型发布潮

来源: [Integrated Cognition](https://integratedcognition.com/blog/march-2026s-ai-launch-wave-what-lawyers-should-make-of-gpt-54-claude-sonnet-46-gemini-31-pro-grok-420-glm-5-minimax-m25-and-the-deepseek-question) (8h ago)

| 模型 | 厂商 | 亮点 |
|------|------|------|
| **GPT-5.4** | OpenAI | "最真实模型"，虚假声明减少 33% vs GPT-5.2，BigLaw Bench 91% |
| **Sonnet 4.6** | Anthropic | OfficeQA 上匹配 Opus 4.6（企业文档/图表/PDF/表格） |
| **Gemini 3.1 Pro** | Google | 已铺开到 Gemini API + Vertex AI + Gemini App + NotebookLM |
| **Grok 4.20** | xAI | 发布中 |
| **GLM-5** | 智谱 | 发布中 |
| **MiniMax M25** | MiniMax | 发布中 |

### 与我们的关系
- **Sonnet 4.6 = Opus 4.6 on OfficeQA** → 对于文档密集型任务，可考虑用更便宜的 Sonnet 替代 Opus
- **GPT-5.4 已通过 OpenAI provider 可用**，上周发布的 computer use 模式

## 📋 Anthropic 更新

- 修复: `ANTHROPIC_BASE_URL` + 第三方 gateway 时 API 400 错误 (tool_reference blocks)
- 修复: Bedrock inference profiles 的 `effort` 参数 400 错误
- **与我们的关系**: 我们用 Anthropic 直连，不受影响，但了解 Bedrock 兼容性

## 🤖 MWC 2026

- Sharp 发布 **Poketomo** AI 伴侣机器人 (Qualcomm 展台)，LLM 驱动，通过 LED 和声音表达

## 行动建议

| 项 | 优先级 | 建议 |
|---|---|---|
| Sonnet 4.6 降本 | 高 | 评估 tax/log 任务是否可从 opus 降到 sonnet |
| GPT-5.4 | 中 | 金融插件对 Alpha agent 有价值 |

---
*Scanned by nightly-evolution task 3.2*
