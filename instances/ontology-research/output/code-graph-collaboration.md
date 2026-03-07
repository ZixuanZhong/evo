# Code Graph 合作方案：数据接口与集成策略

> 本文设计与 Code Graph 团队的合作方案，包括数据需求清单、API 接口设计、同步策略和备选方案。

---

## 1. 数据需求清单

我们的 Ontology Pipeline 需要从 Code Graph 获取以下 5 类数据：

### 1.1 需求汇总表

| # | 数据类型 | 用途 | 优先级 | 数据量级 | 查询模式 |
|---|---------|------|--------|---------|---------|
| ① | **函数级调用链** | 语义传播算法的核心输入 | 🔴 P0 | ~10亿边 | 按函数/服务查询子图 |
| ② | **API Handler 注册** | 识别 HTTP/RPC 入口 | 🔴 P0 | ~200万条 | 按服务查询 |
| ③ | **函数→DB 读写** | DB 标签回溯的起点 | 🔴 P0 | ~1000万边 | 按函数或按 DB 表查询 |
| ④ | **服务拓扑** | 服务间依赖关系 | 🟡 P1 | ~100万边 | 按服务查询上下游 |
| ⑤ | **代码文件路径** | LLM 分析时获取源代码 | 🟡 P1 | 按需查询 | 按函数定位文件 |

### 1.2 详细数据字段

#### ① 函数级调用链

```
我们需要知道：函数 A 调用了函数 B

字段需求：
- caller_func_id:    调用者函数唯一标识
- caller_func_name:  调用者函数名 (如 "handleSendGift")
- caller_service:    调用者所属服务 PSM
- caller_file_path:  调用者所在文件路径
- callee_func_id:    被调用函数唯一标识
- callee_func_name:  被调用函数名
- callee_service:    被调用者所属服务 PSM
- call_type:         调用类型 (direct | rpc | http | mq)
- confidence:        Code Graph 自身的分析置信度（如有）
```

#### ② API Handler 注册信息

```
我们需要知道：哪个函数是 HTTP/RPC 接口的 handler

字段需求：
- service_psm:       服务 PSM
- handler_func_id:   handler 函数标识
- handler_func_name: 函数名
- api_type:          接口类型 (http | thrift | grpc)
- http_method:       HTTP method (仅 HTTP 类型)
- route:             路由路径 (仅 HTTP 类型)
- thrift_service:    Thrift service 名 (仅 RPC)
- thrift_method:     Thrift method 名 (仅 RPC)
```

#### ③ 函数→DB 读写关系

```
我们需要知道：哪个函数读/写了哪张表的哪些列

字段需求：
- func_id:           函数标识
- func_name:         函数名
- service_psm:       所属服务
- db_type:           数据库类型 (mysql | redis | mongodb)
- db_instance:       数据库实例名
- table_name:        表名
- columns:           涉及的列名列表（如可获取）
- access_type:       读/写 (read | write | readwrite)
- sql_pattern:       SQL 模式摘要（如 "SELECT col1,col2 FROM table WHERE..."）
```

#### ④ 服务拓扑

```
字段需求：
- source_psm:        调用方服务
- target_psm:        被调方服务
- protocol:          协议 (thrift | http | grpc | mq)
- call_count_daily:  日均调用量（如有）
```

#### ⑤ 代码文件定位

```
字段需求：
- func_id:           函数标识
- repo_url:          代码仓库地址
- file_path:         文件路径
- line_start:        函数起始行号
- line_end:          函数结束行号
- git_revision:      对应的 Git 版本
```

---

## 2. API 接口设计

### 2.1 接口总览

| 接口 | 方法 | 路径 | 用途 |
|------|------|------|------|
| 查询调用链 | POST | `/api/v1/callgraph/query` | 按函数/服务查询调用子图 |
| 查询 Handler | GET | `/api/v1/handlers/{service_psm}` | 按服务查询所有 API handler |
| 查询 DB 访问 | POST | `/api/v1/db-access/query` | 按函数或表查询 DB 读写关系 |
| 查询服务拓扑 | GET | `/api/v1/topology/{service_psm}` | 查询服务上下游 |
| 批量导出 | POST | `/api/v1/export/bulk` | 全量或增量导出 |
| 变更订阅 | — | Kafka topic: `codegraph.changes` | 增量变更事件 |

### 2.2 核心接口详情

#### 接口 1: 查询调用链

```
POST /api/v1/callgraph/query

Request:
{
  "root_func_id": "func_12345",        // 起点函数（二选一）
  "root_service_psm": "live.room.api",  // 起点服务（二选一）
  "direction": "downstream",            // downstream | upstream | both
  "max_depth": 5,                       // 最大跳数
  "call_types": ["direct", "rpc"],      // 过滤调用类型
  "page_size": 1000,
  "page_token": ""
}

Response:
{
  "edges": [
    {
      "caller": {
        "func_id": "func_12345",
        "func_name": "handleSendGift",
        "service_psm": "live.gift.api",
        "file_path": "handler/gift.go",
        "line_start": 42,
        "line_end": 78
      },
      "callee": {
        "func_id": "func_67890",
        "func_name": "RecordGift",
        "service_psm": "live.gift.service",
        "file_path": "service/gift.go",
        "line_start": 15,
        "line_end": 45
      },
      "call_type": "rpc",
      "confidence": 0.98
    }
  ],
  "total": 156,
  "next_page_token": "abc123"
}
```

#### 接口 2: 查询 DB 访问

```
POST /api/v1/db-access/query

Request:
{
  "query_by": "table",                   // "function" | "table" | "service"
  "table_name": "users",                 // 按表查
  "db_instance": "live_db",
  "access_types": ["read", "write"],
  "page_size": 500,
  "page_token": ""
}

Response:
{
  "accesses": [
    {
      "func_id": "func_11111",
      "func_name": "GetUserByID",
      "service_psm": "user.core.service",
      "file_path": "dal/user.go",
      "table_name": "users",
      "columns": ["id", "nickname", "phone_number", "balance"],
      "access_type": "read",
      "sql_pattern": "SELECT * FROM users WHERE id = ?"
    }
  ],
  "total": 23,
  "next_page_token": ""
}
```

#### 接口 3: 批量导出

```
POST /api/v1/export/bulk

Request:
{
  "data_types": ["callgraph", "handlers", "db_access"],
  "scope": "full",                       // "full" | "incremental"
  "since": "2026-03-01T00:00:00Z",      // 增量模式的起始时间
  "format": "jsonl",                      // "jsonl" | "parquet"
  "output_path": "s3://ontology-pipeline/codegraph-dump/"
}

Response:
{
  "job_id": "export_20260305_001",
  "status": "submitted",
  "estimated_time_minutes": 30,
  "callback_url": "..."
}
```

---

## 3. 数据同步策略

### 3.1 全量初始化

```
阶段 1 (一次性):
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 全量导出      │────→│ JSONL 文件   │────→│ 导入 Pipeline │
│ /export/bulk │     │ (~100GB)     │     │ 数据库        │
└──────────────┘     └──────────────┘     └──────────────┘

预计耗时: 30-60 分钟（导出）+ 2-4 小时（导入解析）
频率: 初始建设时一次，之后按需（如数据不一致时重跑）
```

### 3.2 增量变更推送

```
日常模式:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Code Graph   │────→│ Kafka Topic  │────→│ Ontology     │
│ 变更检测      │     │ codegraph.   │     │ Pipeline     │
│              │     │ changes      │     │ (消费者)     │
└──────────────┘     └──────────────┘     └──────────────┘

消息格式:
{
  "event_type": "callgraph_edge_added",  // _added | _removed | _modified
  "timestamp": "2026-03-05T10:00:00Z",
  "data": {
    "caller_func_id": "func_12345",
    "callee_func_id": "func_67890",
    "call_type": "rpc"
  }
}

事件类型:
- callgraph_edge_added / removed     → 触发传播路径重算
- handler_registered / deregistered  → 触发 API 层更新
- db_access_added / removed          → 触发 DB 回溯重算
- service_created / deleted          → 触发服务层更新
```

### 3.3 一致性保证

| 策略 | 说明 |
|------|------|
| **At-least-once** | Kafka 消费用 at-least-once，Pipeline 写入幂等 |
| **定期对账** | 每周全量快照对比，修复增量遗漏 |
| **版本戳** | 每条数据带 `code_graph_version` 字段，检测陈旧数据 |
| **延迟容忍** | 增量延迟 < 1 小时可接受（非实时场景） |

---

## 4. 权限和安全

### 4.1 权限模型

```
┌─────────────────────────────────────────────┐
│ 权限分级                                     │
│                                               │
│ Level 1: 元数据（调用链、服务拓扑）            │
│   → 风险低，申请标准数据权限即可               │
│                                               │
│ Level 2: 代码路径（文件位置、函数签名）         │
│   → 风险中，需要代码仓库读取权限               │
│                                               │
│ Level 3: 源代码内容（完整函数体）              │
│   → 风险高，按服务粒度申请，审批流程            │
│   → 仅在 LLM 分析时按需拉取，不持久化          │
│                                               │
│ Level 4: SQL 内容（具体查询语句）              │
│   → 风险中高，可能包含业务逻辑                  │
│   → 仅解析结构，不存储原始 SQL                  │
└─────────────────────────────────────────────┘
```

### 4.2 安全措施

| 措施 | 说明 |
|------|------|
| 最小权限 | 只申请需要的服务/仓库权限，不申请全量 |
| 传输加密 | API 调用全部 HTTPS/mTLS |
| 代码不落盘 | LLM 分析用的代码片段在内存中处理，不写入磁盘 |
| 审计日志 | 记录所有代码访问请求（谁/何时/访问了哪个服务的代码） |
| LLM 数据安全 | 如使用外部 LLM API，确保代码不出公司网络 → 优先自部署模型 |

---

## 5. 合作沟通：一页纸说明

> **给 Code Graph 团队的合作提案**

---

### 我们是谁

**数据治理-Ontology 项目组**，正在探索用 LLM + Code Graph 自动构建全公司字段级 ontology graph。

### 我们要解决什么问题

传统数据治理依赖人工标注和代码规范，覆盖率低、维护成本高。我们希望通过分析代码语义，**自动发现**数据字段的含义、敏感性和传播路径。

### 我们需要什么

从 Code Graph 获取 **3 类核心数据**：
1. **函数调用链**（谁调用了谁）→ 用于追踪字段传播路径
2. **API Handler 信息**（哪个函数是 HTTP/RPC 入口）→ 用于识别外部暴露点
3. **DB 访问关系**（哪个函数读写了哪张表）→ 用于 DB 标签回溯

**接入方式**：REST API 按需查询 + Kafka 增量推送（或定期全量 dump）。

### 我们能给什么

1. **字段语义标注数据**：每个 API 字段的中文语义描述、敏感性分类
2. **PII 暴露面报告**：哪些外部 API 暴露了敏感数据库列
3. **服务数据流全景图**：可视化的数据流向（比调用链更上层的语义视图）
4. **数据质量反馈**：在使用 Code Graph 数据过程中发现的不准确/缺失情况

### 合作节奏

| 阶段 | 时间 | 我们的需求 |
|------|------|-----------|
| **PoC** | 第 1-2 周 | 用 mock 数据验证，不需要真实接口 |
| **试点** | 第 3-8 周 | 接入 5-10 个服务的 Code Graph 数据 |
| **规模化** | 第 3-6 月 | 全量 API + 增量推送 |

### 联系人

项目负责人: [TBD]  
技术对接: [TBD]

---

## 6. 备选方案：无 Code Graph 自建调用链

如果 Code Graph 团队暂时无法对接，我们可以用开源工具自行构建部分调用链。

### 6.1 自建方案

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Git Clone    │────→│ Go AST 分析   │────→│ 构建局部      │
│ 目标服务代码  │     │ + 静态分析    │     │ 调用图        │
└──────────────┘     └──────────────┘     └──────────────┘

工具链：
- go/parser + go/ast: 解析函数定义和函数调用
- golang.org/x/tools/go/callgraph: Go 官方静态调用图分析
- golang.org/x/tools/go/ssa: SSA 中间表示，更精确的调用分析
```

### 6.2 自建 vs Code Graph 对比

| 维度 | 自建方案 | Code Graph |
|------|---------|------------|
| **服务内调用链** | ✅ AST 可分析 | ✅ |
| **跨服务 RPC 调用** | ⚠️ 需要解析 IDL + 配置 | ✅ 已有 |
| **动态调用/反射** | ❌ 静态分析无法覆盖 | ⚠️ 可能有运行时采集 |
| **覆盖率** | 60-70%（仅静态可分析） | 90%+（含运行时数据） |
| **维护成本** | 高（自己维护解析工具） | 低（团队维护） |
| **数据新鲜度** | 按需拉取 | 持续更新 |

### 6.3 推荐策略

```
Phase 1 (PoC):        自建（mock + AST），不依赖外部团队
Phase 2 (试点):        对接 Code Graph API，逐步替换自建数据
Phase 3 (规模化):      完全依赖 Code Graph，自建作为降级方案
```

**关键原则**：Pipeline 设计不硬依赖 Code Graph——数据采集层做适配，上层逻辑不感知数据来源。

---

## 7. 集成里程碑

```
Week 1-2:  ┌──────────────────────────────────┐
           │ 完成接口设计文档                    │
           │ 双方确认数据字段和接口 schema       │
           └──────────────────────────────────┘
                          │
Week 3-4:  ┌──────────────┴───────────────────┐
           │ Code Graph 提供 Sandbox 环境      │
           │ 接入 5 个服务的调用链数据            │
           │ 验证数据质量和完整性                │
           └──────────────────────────────────┘
                          │
Week 5-6:  ┌──────────────┴───────────────────┐
           │ 接入增量推送（Kafka）               │
           │ 端到端 Pipeline 跑通                │
           └──────────────────────────────────┘
                          │
Week 7-8:  ┌──────────────┴───────────────────┐
           │ 扩展到 100 个服务                   │
           │ 性能和稳定性验证                    │
           │ 产出第一批 ontology 数据            │
           └──────────────────────────────────┘
                          │
Month 3+:  ┌──────────────┴───────────────────┐
           │ 全量接入                            │
           │ 全量导出 + 增量推送双模式            │
           └──────────────────────────────────┘
```

---

## 8. 小结

| 维度 | 方案 |
|------|------|
| **核心数据需求** | 3 类 P0（调用链、Handler、DB 访问）+ 2 类 P1（拓扑、代码路径） |
| **接口方式** | REST API 按需查询 + Kafka 增量 + 定期全量 dump |
| **权限策略** | 4 级权限，代码不落盘，优先自部署 LLM |
| **合作模式** | 一页纸提案 + 分阶段接入（PoC → 试点 → 规模化） |
| **备选方案** | Go AST 静态分析自建，覆盖率 60-70%，作为降级 |
| **双向价值** | 我们消费调用链 → 回馈语义标注和 PII 暴露报告 |

---

*最后更新: 2026-03-05*
