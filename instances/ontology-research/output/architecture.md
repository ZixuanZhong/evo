# 系统架构设计：从代码扫描到 Ontology Graph 的 E2E Pipeline

> 本文设计从代码仓库到字段级 Ontology Graph 的完整端到端架构，包含 5 层架构、双模式运行（批量+增量）和 Code Graph 集成点。

---

## 1. 架构总览

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                         Ontology Pipeline 五层架构                       ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  Layer 5: 查询与应用层                                               │  ║
║  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │  ║
║  │  │ Cypher   │  │ REST API │  │ 可视化    │  │ 下游消费者       │   │  ║
║  │  │ 查询引擎  │  │ Gateway  │  │ Dashboard │  │ (合规/安全/审计) │   │  ║
║  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │  ║
║  └────────────────────────────────┬────────────────────────────────────┘  ║
║                                   │                                       ║
║  ┌────────────────────────────────┼────────────────────────────────────┐  ║
║  │  Layer 4: 图存储层             │                                    │  ║
║  │  ┌─────────────────────────────┴──────────────────────────────┐    │  ║
║  │  │  Property Graph Store (PoC: Neo4j / Prod: ByteGraph)       │    │  ║
║  │  │  ~3700万 节点 / ~1.27亿 边 / 7 种节点类型 / 8 种边类型     │    │  ║
║  │  └────────────────────────────────────────────────────────────┘    │  ║
║  └────────────────────────────────┬────────────────────────────────────┘  ║
║                                   │                                       ║
║  ┌────────────────────────────────┼────────────────────────────────────┐  ║
║  │  Layer 3: 语义传播层           │                                    │  ║
║  │  ┌──────────────┐  ┌──────────┴───┐  ┌─────────────────────┐      │  ║
║  │  │ 正向传播      │  │ 反向传播      │  │ 置信度计算 +        │      │  ║
║  │  │ (API→DB)     │  │ (DB→API)     │  │ 多路径合并(NoisyOR) │      │  ║
║  │  └──────────────┘  └──────────────┘  └─────────────────────┘      │  ║
║  └────────────────────────────────┬────────────────────────────────────┘  ║
║                                   │                                       ║
║  ┌────────────────────────────────┼────────────────────────────────────┐  ║
║  │  Layer 2: LLM 提取层           │                                    │  ║
║  │  ┌──────────────────┐  ┌──────┴───────────┐  ┌─────────────────┐  │  ║
║  │  │ 小模型粗扫        │  │ 大模型精扫        │  │ 交叉验证 +      │  │  ║
║  │  │ (GPT-4o-mini     │  │ (GPT-4o/Claude   │  │ Confidence      │  │  ║
║  │  │  /DeepSeek-V2)   │  │  仅高敏感字段)    │  │ Scoring         │  │  ║
║  │  └──────────────────┘  └──────────────────┘  └─────────────────┘  │  ║
║  └────────────────────────────────┬────────────────────────────────────┘  ║
║                                   │                                       ║
║  ┌────────────────────────────────┼────────────────────────────────────┐  ║
║  │  Layer 1: 预处理层（免费、高精度）                                   │  ║
║  │  ┌──────────────┐  ┌──────────┴───┐  ┌──────────────┐             │  ║
║  │  │ Go AST 解析   │  │ Thrift IDL   │  │ SQL Parser   │             │  ║
║  │  │ struct/func   │  │ 解析         │  │ 表/列/操作    │             │  ║
║  │  │ /import       │  │ 接口/字段    │  │              │             │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘             │  ║
║  └────────────────────────────────┬────────────────────────────────────┘  ║
║                                   │                                       ║
║  ┌────────────────────────────────┼────────────────────────────────────┐  ║
║  │  Layer 0: 数据采集层                                                │  ║
║  │  ┌──────────────┐  ┌──────────┴───┐  ┌──────────────┐             │  ║
║  │  │ Code Graph   │  │ Git Repo     │  │ DB Metadata  │             │  ║
║  │  │ API ⭐       │  │ 扫描         │  │ + 已有标签    │             │  ║
║  │  │ (调用链/拓扑) │  │ (源代码)     │  │              │             │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────┘             │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

⭐ = Code Graph 团队集成点
```

---

## 2. 各层详细设计

### Layer 0: 数据采集层

| 数据源 | 获取方式 | 数据内容 | 刷新频率 |
|--------|---------|---------|---------|
| **Code Graph** ⭐ | REST/gRPC API | 函数调用链、服务拓扑、API 注册信息 | 实时/每日同步 |
| **Git 仓库** | Git clone + 增量 pull | Go/Java/Python 源代码、Thrift IDL | Git webhook 触发 |
| **DB Metadata** | 数据库 information_schema + 已有标签系统 | 表结构、列类型、已有分类标签 | 每日同步 |

**输出**：统一的 `RawData` 结构，包含：
- `ServiceManifest`：服务列表 + PSM + 语言 + 框架
- `SourceFiles`：按服务组织的源代码文件
- `CallGraph`：函数级调用关系
- `DBSchema`：表结构 + 已有标签

### Layer 1: 预处理层（免费、100% 精度）

这一层完全不用 LLM，用确定性工具提取结构化信息：

```
输入: RawData
│
├── Go AST Parser (go/parser + go/ast)
│   ├── struct 定义（字段名、类型、json tag、注释）
│   ├── 函数签名（参数、返回值）
│   ├── import 关系（包依赖）
│   └── 类型引用关系（哪个 struct 引用了哪个 struct）
│
├── Thrift IDL Parser (kitex 自带工具)
│   ├── service 定义（方法名、参数、返回值）
│   ├── struct 定义（字段 ID、类型、required/optional）
│   └── namespace 和 include 关系
│
├── SQL Parser (vitess/sqlparser)
│   ├── SELECT 的列名
│   ├── INSERT/UPDATE 的目标列
│   ├── WHERE 条件引用的列
│   └── JOIN 关系
│
输出: StructuredExtraction
├── TypeRegistry: 所有 struct/message 定义
├── FunctionRegistry: 所有函数签名 + 引用的类型
├── SQLRegistry: 所有 DB 操作 + 涉及的表/列
└── DependencyGraph: 类型之间的引用关系
```

**关键设计**：预处理层的输出直接用于：
1. 为 Layer 2（LLM）组装精准的上下文（只注入相关 struct，不注入整个文件）
2. 为 Layer 3（传播）提供 pass-through 字段的直接匹配（同名同类型 = 高置信度，无需 LLM）
3. 建立 Service → API → Function → Field 的 `belongs_to` 骨架图

### Layer 2: LLM 提取层

```
输入: StructuredExtraction + 组装好的代码上下文
│
├── 分层模型策略
│   │
│   ├── 批次 1: 小模型全量粗扫 (90% 的任务)
│   │   ├── 模型: GPT-4o-mini / DeepSeek-Coder-V2
│   │   ├── 任务: 字段语义描述、基础敏感性分类
│   │   ├── 上下文: 单函数 + 引用的 struct（< 4K token）
│   │   └── 输出: { field, semantic, sensitivity, confidence }
│   │
│   └── 批次 2: 大模型精扫 (10% 的任务)
│       ├── 触发条件: confidence < 0.7 或 sensitivity ∈ {pii, financial}
│       ├── 模型: GPT-4o / Claude Sonnet
│       ├── 上下文: 函数 + 调用链 + 内部术语表（< 8K token）
│       └── 输出: 精化的 { semantic, sensitivity, confidence }
│
├── 交叉验证（高敏感字段）
│   ├── 3 次独立调用取共识
│   ├── AST 事实核查（类型比对）
│   └── 结果不一致 → 标记人工审核
│
输出: FieldSemantics
├── 每个 Field 的语义描述、敏感性分类、置信度
├── 函数间字段映射（LLM 消歧结果）
└── 人工审核队列（低置信度条目）
```

**成本控制机制**：
- 全量扫描预算上限（如 $1,000）
- Token 消耗实时监控 + 告警
- 热门 struct 缓存（BaseResp、Pagination 等分析一次复用）

### Layer 3: 语义传播层

```
输入: FieldSemantics + CallGraph + SQLRegistry
│
├── 正向传播 (API → DB)
│   ├── 从每个 API 入口字段出发
│   ├── 沿调用链 BFS 遍历
│   ├── 每跳: AST 匹配 → LLM 消歧（仅需时）
│   ├── 置信度按 mapping_type 衰减
│   └── 到达 DB 写入点时记录完整路径
│
├── 反向传播 (DB → API)
│   ├── 从已标注 DB 列出发
│   ├── 反向 BFS 追踪到 API handler
│   ├── 多路径合并（Noisy-OR）
│   └── 生成暴露面报告
│
├── 语义类型推理
│   ├── SemanticType 继承传播
│   ├── 敏感性上提（子类型继承父类型规则）
│   └── same_semantic_as 边的自动发现
│
输出: OntologyEdges
├── passes_to 边（含 propagation_type, confidence）
├── maps_to 边（Field → DBColumn）
├── same_semantic_as 边
└── has_type 边（Field → SemanticType）
```

### Layer 4: 图存储层

| 阶段 | 存储方案 | 适用场景 |
|------|---------|---------|
| **PoC** | Neo4j Community + NetworkX | < 100 万节点，快速验证 |
| **试点** | Neo4j Enterprise 或 NebulaGraph | < 1000 万节点，团队协作 |
| **生产** | ByteGraph（内部方案） | ~3700 万节点，零许可成本 |

**存储内容**（Property Graph 格式）：
- **7 种节点**：Service, API, Function, Field, DBTable, DBColumn, SemanticType
- **8 种边**：belongs_to, calls, passes_to, reads_from, writes_to, same_semantic_as, maps_to, has_type, is_a

**写入策略**：
- 批量写入：每批 10,000 节点/边，事务提交
- 幂等设计：以 (node_type, unique_key) 做 MERGE，重复写入不会创建重复节点
- 版本标记：每个节点/边带 `updated_at` 时间戳和 `pipeline_version`

### Layer 5: 查询与应用层

```
┌─────────────────────────────────────────────────────┐
│                    应用层接口                          │
│                                                       │
│  ┌─────────────┐  ┌────────────────┐                │
│  │ Cypher 查询  │  │ REST/GraphQL   │                │
│  │ 控制台       │  │ API Gateway    │                │
│  │             │  │                │                │
│  │ MATCH (f:   │  │ GET /api/v1/   │                │
│  │ Field)-[:   │  │ field/{id}/    │                │
│  │ maps_to]->  │  │ exposure       │                │
│  │ (c:DBCol)   │  │                │                │
│  └──────┬──────┘  └───────┬────────┘                │
│         │                 │                          │
│  ┌──────┴─────────────────┴────────┐                │
│  │         下游消费者               │                │
│  │                                 │                │
│  │  • 合规团队: PII 暴露面查询      │                │
│  │  • 安全团队: 敏感数据流追踪       │                │
│  │  • 架构团队: 服务依赖可视化       │                │
│  │  • 数据团队: 字段语义搜索        │                │
│  │  • 审计系统: 变更追踪告警        │                │
│  └─────────────────────────────────┘                │
└─────────────────────────────────────────────────────┘
```

---

## 3. 数据流示例：一个字段的完整旅程

追踪 `phone_number` 从代码到 ontology graph：

```
Step 1: 数据采集
  Git repo → 扫描到 user_service/handler.go
  Code Graph → 提供 GetUserProfile() 的调用链
  DB Metadata → users.phone_number 已标注 PII

Step 2: 预处理
  Go AST → 提取 struct GetProfileResp { Phone string `json:"phone"` }
  Go AST → 提取 func GetUserProfile() 引用了 User struct
  SQL Parser → 检测到 SELECT phone_number FROM users

Step 3: LLM 提取
  小模型粗扫 → Phone 字段: "用户手机号" (confidence: 0.88, sensitivity: pii)
  大模型精扫（因 PII 触发）→ "用户注册手机号，11 位" (confidence: 0.94, sensitivity: pii)

Step 4: 语义传播
  正向: API.GetProfileResp.Phone → (pass_through, 0.95) → handler.user.PhoneNumber 
        → (pass_through, 0.92) → dal.GetUser().PhoneNumber
        → (maps_to, 0.90) → users.phone_number
  反向: users.phone_number (PII) → dal → handler → API.Phone
        → 暴露面: GET /api/v1/user/profile (外部 API, 无脱敏 → 🔴 Critical)

Step 5: 写入图存储
  CREATE (f:Field {name:"Phone", semantic:"用户注册手机号", sensitivity:"pii"})
  CREATE (c:DBColumn {name:"phone_number", table:"users", tag:"PII"})
  CREATE (f)-[:maps_to {confidence:0.79, path_length:3}]->(c)
  CREATE (f)-[:has_type]->(st:SemanticType {name:"PhoneNumber"})

Step 6: 查询应用
  合规团队查询: "所有暴露 PII 的外部 API" → 命中 GET /api/v1/user/profile
  → 自动创建 JIRA ticket → 开发团队添加手机号脱敏
```

---

## 4. 双模式运行：批量 + 增量

### 4.1 模式对比

| 维度 | 批量模式 (Batch) | 增量模式 (Incremental) |
|------|-----------------|----------------------|
| **触发条件** | 手动/定期（每周/月） | Git push webhook |
| **扫描范围** | 全部服务 | 仅变更的服务/文件 |
| **耗时** | 2-3 天（10 万服务） | 分钟级（单次变更） |
| **成本** | $500-1,000 | $0.01-0.10/次 |
| **适用场景** | 初始建设、全量刷新 | 日常运维 |

### 4.2 批量模式流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 服务发现  │───→│ 代码下载  │───→│ 预处理   │───→│ LLM 提取 │───→│ 传播+写入│
│ (全量)   │    │ (并行)   │    │ (并行)   │    │ (批量)   │    │ (事务)   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     │ 10万服务       │ 并行度100     │ 并行度200     │ 并行度50      │ 批量10K
     │ ~10分钟        │ ~2小时        │ ~1小时        │ ~24小时       │ ~4小时
     └───────────────┴───────────────┴───────────────┴───────────────┘
                              总计: ~30小时（首次）
```

**编排**：用 Apache Airflow 或字节内部调度平台，DAG 编排 5 层的依赖关系。

参考: 批量 hub-and-spoke 架构是成熟的数据集成模式（[dbt Labs: Data Integration 2025](https://www.getdbt.com/blog/data-integration)）。

### 4.3 增量模式流程

```
Git Push Event (webhook)
    │
    ▼
┌─────────────────────────┐
│ 变更检测                 │
│ 1. 解析 Git diff         │
│ 2. 识别变更的函数/struct  │
│ 3. 查询受影响的传播路径   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ 局部重分析               │
│ 1. 仅预处理变更文件      │
│ 2. 仅 LLM 分析变更函数   │
│ 3. 仅重算受影响路径      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ 图更新 + 告警            │
│ 1. MERGE 更新的节点/边   │
│ 2. 检测新增高风险暴露    │
│ 3. 触发告警（如有）      │
└─────────────────────────┘

耗时: 30秒 - 5分钟（取决于变更范围）
成本: < $0.10/次
```

---

## 5. Code Graph 集成点

```
┌─────────────────────────────────────────────┐
│              Code Graph 平台                  │
│                                               │
│  提供的数据:                                   │
│  ① 函数级调用链 (caller → callee)             │
│  ② 服务拓扑 (service → service, protocol)     │
│  ③ API handler 注册信息 (route, method)       │
│  ④ 函数 → DB 读写关系                         │
│                                               │
│  集成方式:                                     │
│  A. REST API 查询（实时，单服务粒度）           │
│  B. 批量导出（全量，定期 dump）                 │
│  C. MQ 推送（增量变更事件）                     │
└─────────────┬───────────────────────────────┘
              │
    ┌─────────┴─────────┐
    │   集成适配层        │
    │   - 格式转换        │
    │   - 缓存(Redis)    │
    │   - 失败重试        │
    │   - 降级策略        │
    └─────────┬─────────┘
              │
              ▼
         Layer 0 + Layer 3
```

**降级策略**：如果 Code Graph API 不可用，回退到 Git + AST 工具自行构建局部调用链（精度降低但不中断 pipeline）。

---

## 6. 高可用与容错设计

### 6.1 容错策略

| 故障场景 | 影响 | 处理方式 |
|----------|------|---------|
| LLM API 超时/限流 | Layer 2 卡住 | 指数退避重试 + 模型降级（GPT-4o → mini） |
| LLM 返回非法 JSON | 单条提取失败 | JSON 修复尝试 → 重试 → 标记 failed |
| Code Graph 不可用 | 无调用链数据 | 降级到 AST 静态分析，标记为低置信度 |
| 图数据库写入失败 | 数据丢失 | WAL 日志 + 批量重放 |
| Git 仓库无权限 | 无法获取源代码 | 跳过 + 记录，定期重试 |

### 6.2 幂等性保证

```
所有写入操作都是幂等的：
- 节点: MERGE ON (node_type, unique_key)
- 边:   MERGE ON (source, target, edge_type)
- 属性: SET properties（最新值覆盖）

重复运行 pipeline 不会产生重复数据。
```

### 6.3 监控指标

```
Pipeline 健康指标:
├── 采集层: 服务覆盖率、代码新鲜度（最近一次拉取时间）
├── 预处理层: AST 解析成功率（目标 > 99%）
├── LLM 层: 提取成功率、平均 confidence、token 消耗/成本
├── 传播层: 路径覆盖率、平均路径置信度
├── 存储层: 节点/边总数、写入延迟、查询 P99 延迟
└── 业务指标: PII 暴露面数量变化趋势、人工审核队列长度
```

---

## 7. 技术选型汇总

| 组件 | PoC 选型 | 生产选型 | 理由 |
|------|---------|---------|------|
| 调度编排 | Cron / 手动 | Airflow / 内部调度 | 生产需要 DAG 依赖管理 |
| AST 解析 | go/parser + go/ast | 同 | Go 标准库足够 |
| IDL 解析 | kitex 代码生成工具 | 同 | 原生支持 |
| SQL 解析 | vitess/sqlparser | 同 | 开源、支持 MySQL 方言 |
| LLM API | OpenAI API | 自部署 Qwen2.5-Coder | 长期成本降低 5-10x |
| 消息队列 | — | Kafka / RocketMQ | 增量变更事件 |
| 缓存 | dict (内存) | Redis Cluster | struct 分析结果缓存 |
| 图数据库 | Neo4j Community | ByteGraph | 内部方案零许可成本 |
| 可视化 | NetworkX + matplotlib | 自研 Web UI / Grafana | PoC 轻量，生产需交互式 |
| 监控 | print 日志 | Prometheus + Grafana | 全链路可观测 |

---

## 8. 小结

| 设计维度 | 方案 |
|----------|------|
| **架构风格** | 5 层分离，每层可独立扩展和替换 |
| **核心思想** | AST 做重活（免费、确定性）→ LLM 做巧活（语义、消歧）→ Graph 做关联（传播、查询） |
| **运行模式** | 批量（初始建设/全量刷新）+ 增量（日常 Git 变更驱动） |
| **Code Graph** | 核心依赖，提供调用链和服务拓扑；有降级方案 |
| **成本控制** | 分层模型 + AST 先行 + 缓存复用，全量 <$1K |
| **容错** | 重试 + 降级 + 幂等 + WAL，pipeline 不因单点故障中断 |
| **可观测** | 每层有独立监控指标，全链路追踪 |

参考: 数据管道架构模式参见 [Alation: 9 Data Pipeline Architecture Patterns](https://www.alation.com/blog/data-pipeline-architecture-patterns/)，事件驱动增量模式参见 [Landskill: Real-Time Data Pipelines 2025](https://www.landskill.com/blog/real-time-data-pipelines-patterns/)。

---

*最后更新: 2026-03-05*
