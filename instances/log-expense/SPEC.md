# log-expense — SPEC

## Background

每日消费分类检查。从 Lunch Money API 拉取新交易，自动分类，发 Discord 审核报告。
原 cron `log-daily-expense` 因超时失败（180s timeout, 实际 1033s），拆分为独立任务。

## Iron Rules

- 用中文输出
- 没有新交易时不发消息，Gate 直接标 done
- 不编造交易数据
- 分类规则按 SKILL.md 执行

## Phase 0: 消费检查

| ID  | Title              | Depends On | Output                     |
|-----|--------------------|------------|----------------------------|
| 0.1 | 拉取新交易         | —          | `output/transactions.json` |
| 0.2 | 分类 + 生成报告    | 0.1        | `output/report.md`         |
| 0.G | Gate: Discord 通知 | 0.2        | —                          |

### 0.1 拉取新交易

```
1. 读取 API key: source /Users/clawz/.openclaw/workspace-log/lunchmoney.env
2. 读取上次检查日期: cat /Users/clawz/.openclaw/workspace-log/lunchmoney_last_check.txt
3. 拉取交易:
   curl -s -H "Authorization: Bearer $LUNCHMONEY_API_KEY" \
     "https://dev.lunchmoney.app/v1/transactions?start_date=$LAST_DATE&end_date=$(date +%Y-%m-%d)"
4. 将 JSON 存入 output/transactions.json
5. 如果没有新交易 → 在 output/transactions.json 写 {"transactions": []}
```

### 0.2 分类 + 生成报告

```
1. 读取 output/transactions.json
2. 如果 transactions 为空 → 写 "无新交易" 到 output/report.md
3. 否则：
   a. 读取分类规则: /Users/clawz/.openclaw/workspace-log/skills/expense-review/SKILL.md
   b. 按规则自动分类高置信度交易
   c. 生成审核报告写入 output/report.md
4. 更新 last_check 日期: echo "$(date +%Y-%m-%d)" > /Users/clawz/.openclaw/workspace-log/lunchmoney_last_check.txt
```

### 0.G Gate: Discord 通知

```
1. 读取 output/report.md
2. 如果内容是"无新交易" → 直接标 done，不发消息
3. 否则发 Discord V2 卡片到 #log:
   - action=send, channel=discord, target=1477875298715570186
   - container accentColor=#5865F2
   - blocks: type='text' + type='separator'
   - 内容: 交易审核报告（分类结果、需人工确认的）
   - 末尾: <@803422039977099284> 模型：{model}
4. 发完后返回 NO_REPLY
```
