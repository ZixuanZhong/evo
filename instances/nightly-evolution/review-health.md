# 健康检查 — 2026-03-08

## 脚本验证

| Workspace | 结果 |
|---|---|
| workspace-core | ✅ All valid |
| workspace-alpha | ✅ All valid |
| workspace-log | ✅ All valid |
| workspace-tax | ⚠️ `2026-03-01.md` 缺 `##` headers (低优先级，持续存在) |

## Cron 健康 (16 jobs)

### ❌ 异常

| Job | Agent | consErrors | 问题 |
|-----|-------|-----------|------|
| **log-hourly-location** | log | 0 ✅ | **已恢复！** 上次 OK (34s)，此前连续 6 次超时 |
| **log-daily-expense** | log | 1 🟡 | 超时 (1033s)，新问题 |
| **tax-daily-irs-study** | tax | 1 🟡 | 超时 (1050s) |
| **alpha-daily-inspector** | alpha | 1 🟡 | 超时 (599s) |
| **alpha-pre-market-check** | alpha | 1 🟡 | Message failed (历史，周末无新运行) |

### ✅ 正常 (11 jobs)

log-workflowy-check, log-nightly-diary, log-monthly-expense, Nightly Evolution, alpha-monitor, alpha-daily-scan, alpha-eod-status, alpha-weekly-report, tax-weekly-irs-summary, 驾照续期提醒, 取消欧元Uber One提醒

### 📊 趋势

- ✅ **log-hourly-location 恢复**: 从 6 次连续超时降到 0，34s 完成
- 🟡 **log-daily-expense 新超时**: 首次出现 1033s 超时
- 超时 jobs 的 lastDurationMs 都远超 timeout 设定（timeout 在 180-300s，实际 600-1050s），说明 gateway timeout 执行不严格

## 变更

**未修改。**

---
*Review by nightly-evolution task 1.4*
