# alpha-inspector — SPEC

## Background

Alpha Trading 运营期每日巡检。检查系统健康、交易状态、策略表现。
原 cron `alpha-daily-inspector` 因超时失败（180s timeout, 实际 599s），拆分为独立任务。

## Iron Rules

- 用中文输出
- 每个任务产出一个输出文件
- 不要编造数据——API 不通就报错
- Gate task 必须发 Discord V2 卡片

## 环境

```bash
export $(grep -v '^#' ~/alpha-trading/.env | xargs)
ALPACA_BASE="https://paper-api.alpaca.markets/v2"
ALPACA_HEADERS="-H 'APCA-API-KEY-ID: $ALPACA_API_KEY' -H 'APCA-API-SECRET-KEY: $ALPACA_API_SECRET'"
```

## Phase 0: 巡检

| ID  | Title              | Depends On | Output                      |
|-----|--------------------|------------|-----------------------------|
| 0.1 | L1 系统健康        | —          | `output/l1-system.md`       |
| 0.2 | L2 交易健康        | —          | `output/l2-trading.md`      |
| 0.3 | L3 策略复盘        | —          | `output/l3-strategy.md`     |
| 0.G | Gate: 汇总报告     | 0.1, 0.2, 0.3 | —                        |

### 0.1 L1 系统健康

```
1. Alpaca API 可达性: curl -s -o /dev/null -w '%{http_code}' -H "APCA-API-KEY-ID: $ALPACA_API_KEY" -H "APCA-API-SECRET-KEY: $ALPACA_API_SECRET" "https://paper-api.alpaca.markets/v2/account"
2. 账户余额: 解析 account JSON → equity, cash, buying_power
3. alpha.db 完整性: ls -la ~/alpha-trading/alpha.db
4. 磁盘空间: df -h /Users/clawz
```

输出到 `output/l1-system.md`

### 0.2 L2 交易健康

```
1. 当前持仓: curl -s -H ... "https://paper-api.alpaca.markets/v2/positions"
2. 今日订单: curl -s -H ... "https://paper-api.alpaca.markets/v2/orders?status=all&after=$(date -u +%Y-%m-%dT00:00:00Z)"
3. 风控检查:
   - 单票仓位 >20% → 警告
   - 总回撤 >10% → 严重
   - rejected orders → 警告
```

输出到 `output/l2-trading.md`

### 0.3 L3 策略复盘

```
条件执行：
- 如果今天是周日 → 执行完整策略复盘
- 否则 → 写 "非周日，跳过 L3 策略复盘" 到输出文件

周日执行内容：
1. 读取 ~/alpha-trading/reports/ 下本周报告
2. 各策略信号频率 + 胜率统计
3. 回测 vs 实盘偏差
```

输出到 `output/l3-strategy.md`

### 0.G Gate: 汇总报告

```
1. 读取 output/l1-system.md、output/l2-trading.md、output/l3-strategy.md
2. 导出持久报告: cp 综合结果到 ~/alpha-trading/reports/inspection-$(date +%Y-%m-%d).md
3. 发送 Discord V2 卡片到 #alpha:
   - action=send, channel=discord, target=1478298029772771449
   - container accentColor=#9b59b6 (正常) / #e74c3c (有严重问题)
   - blocks: type='text' + type='separator'
   - 包含: L1/L2/L3 各段摘要
   - 有严重问题时 @mention <@803422039977099284>
   - 末尾: <@803422039977099284> 模型：{model}
4. 发完后返回 NO_REPLY
```
