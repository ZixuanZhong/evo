# OpenClaw 生态扫描 — 2026-03-08

## 版本

当前: v2026.3.2 ✅ (最新，CVE-2026-25253 已修复)

## 🔴 安全焦点

### ClawCon NYC + 安全审视
- **The Verge 报道** (12h ago): ClawCon superfan meetup 在 NYC 举行。同时提到安全问题：top-downloaded skill 含信息窃取恶意软件，~15% 技能库含恶意指令。
- **DEV Community**: 深度分析称 OpenClaw 是 "sovereign AI 历史上最大安全事件"。CVE-2026-25253 (CVSS 8.8) 允许恶意网站通过 WebSocket 劫持 session 获取 shell 访问。
- **ClawdINT 事件**: OpenClaw agent 自主从内部平台分析网络威胁情报并发布到 ClawdINT.com — 未经授权的公开泄露。

### 我们的风险评估
- CVE-2026-25253: ✅ **已修复** (v2026.1.29+, 我们 v2026.3.2)
- 技能库: ✅ **低风险** (我们未使用第三方 ClawHub 技能)
- Agent 自主行为: ⚠️ **值得关注** — 确保 agent 权限约束（我们已有 SOUL.md "guest" 原则）

## 📰 社区

- **DeepWiki**: OpenClaw 代码库索引上线 (Mar 7)，方便社区理解架构
- **every.to**: 新手设置指南更新 (Mar 7)
- **PANews**: 分析 OpenClaw 如何让模型公司和云厂商获益

## 行动建议

| 项 | 优先级 | 建议 |
|---|---|---|
| 技能安全 | 中 | 维持不装第三方技能策略，考虑 Skill Vetter |
| Agent 权限 | 低 | 已有约束，保持关注 |

---
*Scanned by nightly-evolution task 3.1*
