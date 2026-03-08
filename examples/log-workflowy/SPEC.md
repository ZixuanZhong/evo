# log-workflowy — SPEC

## Background

每日 Workflowy 日记格式检查与修复。确保日记结构完整，无空节点或重复。
原 cron `log-workflowy-check` 有过连续超时。

## Iron Rules

- 用中文输出
- 修复前先确认问题存在
- 不要删除有内容的节点

## 关键 ID

- Journal 根节点: `f6bc305b-4511-345b-fd35-dd0d4875e215`
- 2026 年节点: `f2d64276-a593-d5da-6fcf-a29e2c813638`

## Phase 0: 检查修复

| ID  | Title              | Depends On | Output                    |
|-----|--------------------|------------|---------------------------|
| 0.1 | 结构检查           | —          | `output/check-result.md`  |
| 0.2 | 修复问题           | 0.1        | `output/fix-result.md`    |
| 0.G | Gate: 报告         | 0.2        | —                         |

### 0.1 结构检查

```
1. 用 workflowy CLI 读取年节点:
   workflowy read f2d64276 -f json --depth 1
2. 检查月份节点: 空名称? 重复? 不连续?
3. 读取最新月份内部:
   workflowy read <latest_month_id> -f json --depth 1
4. 检查日节点格式: DD 星期. 格式正确?
5. 检查最新 2-3 个日节点: 子节点有空内容?
6. 写检查结果到 output/check-result.md
```

### 0.2 修复问题

```
1. 读取 output/check-result.md
2. 如果无问题 → 写 "无需修复" 到 output/fix-result.md
3. 如果有问题:
   - 空名称节点 → workflowy delete
   - 重复月份节点 → 合并或删除空的
   - 空内容子节点 → 删除
4. 写修复结果到 output/fix-result.md
```

### 0.G Gate: 报告

```
1. 读取 output/check-result.md 和 output/fix-result.md
2. 用 message tool 发 Discord V2 卡片到 #log:
   - target=1477875298715570186
   - accentColor=#2ecc71 (无问题) / #e67e22 (有修复)
   - 内容: 检查项 + 修复动作
   - 末尾: 模型：{model}
3. 发完后返回 NO_REPLY
```
