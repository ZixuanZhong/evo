# OpenClaw 生态扫描 — 2026-03-06

## 版本状态

| 项目 | 值 |
|------|-----|
| 当前安装版本 | **v2026.3.2** |
| 最新发布版本 | **v2026.3.2** (Mar 3) |
| 状态 | ✅ 已是最新 |

v2026.3.2 变更: PDF 分析工具、SecretRef 扩展到 64 目标、150+ fixes。
来源: [gradually.ai](https://www.gradually.ai/en/changelogs/openclaw/)

## 🔴 安全告警 (批量 CVE 披露日)

今日 RedPacket Security 批量披露多个 CVE，全部影响 <2026.2.14/2026.2.15：

| CVE | 严重 | 影响版本 | 描述 | 我们 (v2026.3.2) |
|-----|------|---------|------|-----------------|
| CVE-2026-28479 | HIGH | <2026.2.15 | SHA-1 sandbox cache key 碰撞 → 跨 sandbox 泄漏 | ✅ 不受影响 |
| CVE-2026-28466 | HIGH | <2026.2.14 | node.invoke 绕过 exec approval | ✅ 不受影响 |
| CVE-2026-28468 | HIGH | <2026.2.14 | sandbox browser bridge 无认证 | ✅ 不受影响 |
| CVE-2026-28478 | HIGH | <2026.2.13 | webhook handler DoS | ✅ 不受影响 |
| CVE-2026-28453 | HIGH | <2026.2.14 | TAR archive 路径穿越 | ✅ 不受影响 |
| CVE-2026-28462 | HIGH | 待确认 | 待详情 | ⚠️ 需检查 |
| CVE-2026-28465 | HIGH | voice-call 组件 | 待详情 | ⚠️ 需检查 |

**结论**: 5/7 明确不受影响 (修复版本 <2026.2.15，我们 2026.3.2)。2 个待确认但 "no exploitation known"。

## 📰 社区动态

1. **Google Workspace CLI** — Google 发布 CLI 让 OpenClaw 直接操作 Gmail/Drive/Docs。Gog skill 替代方案。
   来源: [PCWorld](https://www.pcworld.com/article/3079523/google-makes-gmail-drive-and-docs-agent-ready-for-openclaw.html)

2. **Peter Steinberger → OpenAI** — OpenClaw 创始人加入 OpenAI 做 personal agent。项目仍开源。
   来源: [revolutioninai.com](https://www.revolutioninai.com/2026/02/clawdbot-openclaw-peter-steinberger-openai-news.html)

3. **Xiaomi miclaw** — 基于 MiMo 大模型的移动端 AI agent，3/6 限量内测。
   来源: [TechNode](https://technode.com/2026/03/06/xiaomi-begins-limited-closed-beta-of-openclaw-like-mobile-ai-agent-xiaomi-miclaw/)

4. **DataCamp "Best ClawHub Skills"** 指南发布，提及 ClawHavoc 后安全审核加强。

## 📊 行动建议

| 动态 | 优先级 | 建议 |
|------|--------|------|
| Google Workspace CLI | 高 | 评估替代 Gog skill，原生 CLI 更安全 |
| CVE-2026-28462/28465 | 低 | 确认详情，大概率已修复 |

---
*Scanned by nightly-evolution task 3.1*
