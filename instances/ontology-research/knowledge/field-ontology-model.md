# 字段级 Ontology 建模：如何表示 Field 的语义、归属、传递关系

> 本文设计一套 Property Graph 格式的字段级 ontology 数据模型，用于表达微服务生态中字段的语义、归属和传播关系。

---

## 1. 设计目标

我们需要一个数据模型来回答以下问题：

- **这个字段是什么意思？**（语义）
- **这个字段属于哪个服务/API？**（归属）
- **这个字段从哪里来、到哪里去？**（传播）
- **这个字段和其他服务的某个字段是同一个东西吗？**（关联）
- **这个字段有多敏感？**（分类）

---

## 2. 核心实体（Node Types）

### 2.1 实体定义

| Node Type | 说明 | 关键属性 | 比喻 |
|-----------|------|---------|------|
| **Service** | 一个微服务 | `name`, `psm`, `owner_team`, `language`, `framework` | 一栋楼 |
| **API** | 一个 HTTP 接口或 RPC 方法 | `name`, `http_method`, `route`, `protocol` (http/thrift/grpc) | 楼的入口 |
| **Function** | 一个代码函数 | `name`, `file_path`, `package` | 楼内的一个房间 |
| **Field** | 一个请求/响应/内部 struct 的字段 | `name`, `go_type`, `json_name`, `semantic`, `sensitivity`, `context` | 房间里的一件物品 |
| **DBTable** | 一张数据库表 | `name`, `database`, `engine` | 仓库 |
| **DBColumn** | 数据库表的一列 | `name`, `data_type`, `nullable`, `comment`, `classification_tag` | 仓库的一个货架 |
| **SemanticType** | 语义类型（可复用的概念） | `name`, `description`, `parent_type` | 物品的品类标签 |

### 2.2 Node 属性详情

#### Field 节点（最核心的实体）

```
Node: Field
Properties:
  - name: string              # Go struct 字段名，如 "AnchorID"
  - go_type: string           # Go 类型，如 "int64"
  - json_name: string         # JSON 序列化名，如 "anchor_id"
  - semantic: string          # 中文语义描述，如 "创建直播间的主播 ID"
  - sensitivity: enum         # none | pii | financial | internal_id | confidential
  - context: string           # 业务上下文，如 "创建直播间请求"
  - direction: enum           # request | response | internal
  - required: boolean         # 是否必填
  - confidence: float         # LLM 提取的置信度 [0, 1]
  - source: enum              # llm_extracted | idl_parsed | db_tagged | human_reviewed
```

#### SemanticType 节点（语义抽象层）

```
Node: SemanticType
Properties:
  - name: string              # 语义类型名，如 "UserIdentifier"
  - description: string       # "唯一标识一个用户的 ID"
  - parent_type: string       # 父类型，如 "Identifier"
  - sensitivity_default: enum # 默认敏感性
```

**SemanticType 的继承体系**（部分示例）：

```
Identifier (标识符)
├── UserIdentifier (用户标识)
│   ├── AnchorIdentifier (主播标识)
│   └── ViewerIdentifier (观众标识)
├── RoomIdentifier (直播间标识)
├── OrderIdentifier (订单标识)
└── GiftIdentifier (礼物标识)

PersonalInfo (个人信息)
├── PhoneNumber (手机号) → sensitivity: pii
├── Email (邮箱) → sensitivity: pii
├── RealName (真实姓名) → sensitivity: pii
└── IDCardNumber (身份证号) → sensitivity: pii

FinancialData (金融数据)
├── Amount (金额) → sensitivity: financial
├── Balance (余额) → sensitivity: financial
└── Price (价格) → sensitivity: financial

ContentData (内容数据)
├── Title (标题)
├── Description (描述)
└── MediaURL (媒体链接)
```

---

## 3. 核心关系（Edge Types）

### 3.1 关系定义

| Edge Type | 起点 → 终点 | 说明 | 边属性 |
|-----------|-------------|------|--------|
| **belongs_to** | API → Service | API 属于某个服务 | — |
| **belongs_to** | Function → Service | 函数属于某个服务 | — |
| **belongs_to** | Field → API | 字段属于某个 API 的请求/响应 | `direction`: request/response |
| **belongs_to** | DBColumn → DBTable | 列属于某张表 | — |
| **calls** | API → Function | API handler 调用函数 | — |
| **calls** | Function → Function | 函数调用函数 | `call_type`: direct/rpc |
| **calls** | Service → Service | 服务调用服务 | `protocol`: http/thrift/grpc |
| **passes_to** | Field → Field | 字段值传递给另一个字段 | `propagation_type`, `confidence` |
| **reads_from** | Function → DBColumn | 函数读取某 DB 列 | `query_type`: select/join |
| **writes_to** | Function → DBColumn | 函数写入某 DB 列 | `query_type`: insert/update |
| **same_semantic_as** | Field ↔ Field | 两个字段语义相同 | `confidence`, `reason` |
| **maps_to** | Field → DBColumn | API 字段映射到 DB 列 | `confidence`, `path_length` |
| **has_type** | Field → SemanticType | 字段的语义类型 | `confidence` |
| **is_a** | SemanticType → SemanticType | 语义类型继承 | — |

### 3.2 关键边属性

#### passes_to 边（字段传播）

```
Edge: passes_to
Properties:
  - propagation_type: enum    # pass_through | transform | aggregate | filter
  - confidence: float         # 置信度 [0, 1]
  - transform_desc: string    # 转换描述，如 "int64 → string 格式化"
  - hop_count: int            # 从原始 API 字段算起的跳数
```

**传播类型说明**：

| 类型 | 说明 | 例子 | 置信度影响 |
|------|------|------|-----------|
| **pass_through** | 字段值原样传递 | `req.RoomID → rpc.RoomID` | 不衰减 |
| **transform** | 字段值经过转换 | `req.Price * req.Count → totalAmount` | 衰减 10-20% |
| **aggregate** | 多个字段聚合为一个 | `firstName + lastName → fullName` | 衰减 20-30% |
| **filter** | 字段用于过滤条件 | `req.UserID → WHERE user_id = ?` | 不衰减 |

#### same_semantic_as 边（语义等价）

```
Edge: same_semantic_as
Properties:
  - confidence: float         # 置信度 [0, 1]
  - reason: string            # "LLM 判断两者都代表直播间 ID"
  - detected_by: enum         # name_match | llm_inference | db_backtrack | human
```

---

## 4. 完整例子：room_id 在 Ontology Graph 中的旅程

### 4.1 场景描述

一个 `room_id` 从 HTTP API 入口出发，经过多个服务，最终写入数据库。我们追踪它在 ontology graph 中的完整表示。

### 4.2 涉及的服务和字段

```
[live-gateway] HTTP API: POST /api/v1/room/enter
  → 请求字段: EnterRoomReq.RoomID (int64, json:"room_id")
  
    调用 ↓ RPC
    
[room-service] RPC: GetRoomDetail(GetRoomReq)
  → 请求字段: GetRoomReq.RoomID (i64)
  → 响应字段: GetRoomResp.RoomID (i64)
  → 响应字段: GetRoomResp.AnchorID (i64)
  
    读取 ↓ DB
    
[MySQL] table: rooms, column: id (BIGINT)
  → classification_tag: "业务ID-直播间"
```

### 4.3 Graph 表示（ASCII Art）

```
                                    SemanticType
                                   ┌──────────────┐
                                   │ RoomIdentifier│
                                   │ (直播间标识)   │
                                   └──────┬───────┘
                                    is_a  │
                                   ┌──────┴───────┐
                                   │  Identifier   │
                                   └──────────────┘
                                          ▲
                                   has_type│(×3)
                    ┌─────────────────────┼──────────────────────┐
                    │                     │                      │
            ┌───────┴────────┐  ┌─────────┴────────┐  ┌─────────┴────────┐
            │ Field:         │  │ Field:           │  │ DBColumn:        │
            │ EnterRoomReq   │  │ GetRoomReq       │  │ rooms.id         │
            │ .RoomID        │  │ .RoomID          │  │                  │
            │ ctx: "进入直播间"│  │ ctx: "查询直播间" │  │ tag: "业务ID"    │
            │ sensitivity:   │  │ sensitivity:     │  │                  │
            │   internal_id  │  │   internal_id    │  │                  │
            └───────┬────────┘  └────────┬─────────┘  └────────┬─────────┘
                    │                    │                      ▲
                    │ passes_to          │ passes_to            │ reads_from
                    │ (pass_through,     │ (pass_through,       │
                    │  conf: 0.95)       │  conf: 0.95)        │
                    └────────►───────────┘                      │
                              │                                 │
                              └────────────maps_to──────────────┘
                                          (conf: 0.90)

    belongs_to 关系（省略画线）:
    - EnterRoomReq.RoomID  → API: POST /api/v1/room/enter → Service: live-gateway
    - GetRoomReq.RoomID    → API: GetRoomDetail            → Service: room-service  
    - rooms.id             → DBTable: rooms
```

### 4.4 语义差异的捕获

虽然三个位置都代表"直播间 ID"，但上下文不同：

| 位置 | 字段名 | 语义上下文 | 敏感性 |
|------|--------|-----------|--------|
| live-gateway API 请求 | `RoomID` | 观众请求进入直播间 | internal_id |
| room-service RPC 请求 | `RoomID` | 内部服务查询直播间详情 | internal_id |
| MySQL rooms.id | `id` | 数据库主键 | internal_id |

三者通过 `same_semantic_as` 边和共同的 `SemanticType: RoomIdentifier` 关联，但各自保留独立的 `context` 属性。这就是 ontology 比简单标签强的地方——**同一个语义概念在不同位置有不同的上下文**。

### 4.5 反向查询示例

**问题**："数据库 `rooms.id` 列被哪些外部 API 暴露了？"

**查询路径**（Cypher 伪代码）：
```cypher
MATCH (col:DBColumn {name: "id", table: "rooms"})
  <-[:reads_from|writes_to]-(func:Function)
  <-[:calls*1..5]-(api:API)
  -[:belongs_to]->(svc:Service)
RETURN api.name, api.route, svc.name
```

**结果**：`POST /api/v1/room/enter` (live-gateway) — 意味着外部用户可以通过这个 API 间接访问 `rooms.id` 的数据。

---

## 5. Ontology 继承与推理

### 5.1 SemanticType 继承

```
Identifier
├── UserIdentifier
│   ├── AnchorIdentifier    → sensitivity: internal_id
│   └── ViewerIdentifier    → sensitivity: internal_id
├── RoomIdentifier          → sensitivity: internal_id
└── TransactionIdentifier   → sensitivity: financial
```

**继承规则**：子类型继承父类型的默认 `sensitivity`，除非显式覆盖。

**推理示例**：
- `AnchorIdentifier IS-A UserIdentifier IS-A Identifier`
- 如果规则说"所有 UserIdentifier 需要脱敏"，则 AnchorIdentifier 也需要脱敏
- LLM 在标注时只需要标到最具体的类型（如 AnchorIdentifier），系统自动继承上层规则

### 5.2 所有权推理

```
Field: CreateRoomReq.AnchorID
  has_type → AnchorIdentifier
  
AnchorIdentifier
  identifies → EntityType: Anchor（主播实体）
  
Anchor
  has_data_subject → DataSubjectType: ContentCreator（内容创作者）
```

这使得合规团队可以查询："哪些 API 字段涉及内容创作者的个人数据？"

### 5.3 传播推理

**规则**：如果 Field A `passes_to` Field B，且 A `has_type` SemanticType X，则 B 也 `has_type` X（置信度按传播衰减）。

```
EnterRoomReq.RoomID (has_type: RoomIdentifier, conf: 0.95)
  passes_to (conf: 0.95) →
GetRoomReq.RoomID (推断 has_type: RoomIdentifier, conf: 0.95 × 0.95 = 0.90)
  maps_to (conf: 0.90) →
rooms.id (推断 has_type: RoomIdentifier, conf: 0.90 × 0.90 = 0.81)
```

---

## 6. Property Graph Schema 定义（完整版）

### 6.1 Node Schema

```yaml
nodes:
  Service:
    properties:
      name: {type: string, required: true, indexed: true}
      psm: {type: string, required: true, indexed: true}  # 字节内部服务标识
      owner_team: {type: string}
      language: {type: string, enum: [go, java, python]}
      framework: {type: string, enum: [hertz, kitex, spring, flask]}
      repo_url: {type: string}

  API:
    properties:
      name: {type: string, required: true}
      http_method: {type: string, enum: [GET, POST, PUT, DELETE, ""]}
      route: {type: string}
      protocol: {type: string, enum: [http, thrift, grpc, protobuf]}
      idl_path: {type: string}           # Thrift/Proto IDL 文件路径

  Function:
    properties:
      name: {type: string, required: true}
      file_path: {type: string, required: true}
      package: {type: string}
      line_start: {type: int}
      line_end: {type: int}

  Field:
    properties:
      name: {type: string, required: true}
      go_type: {type: string}
      json_name: {type: string, indexed: true}
      semantic: {type: string}            # 中文语义描述
      sensitivity: {type: string, enum: [none, pii, financial, internal_id, confidential]}
      context: {type: string}             # 业务上下文
      direction: {type: string, enum: [request, response, internal]}
      required: {type: boolean}
      confidence: {type: float}
      source: {type: string, enum: [llm_extracted, idl_parsed, db_tagged, human_reviewed]}
      last_updated: {type: datetime}

  DBTable:
    properties:
      name: {type: string, required: true, indexed: true}
      database: {type: string}
      engine: {type: string}
      row_count_estimate: {type: long}

  DBColumn:
    properties:
      name: {type: string, required: true}
      data_type: {type: string}
      nullable: {type: boolean}
      comment: {type: string}
      classification_tag: {type: string}  # 已有的数据分类标签
      is_primary_key: {type: boolean}
      is_indexed: {type: boolean}

  SemanticType:
    properties:
      name: {type: string, required: true, indexed: true}
      description: {type: string}
      sensitivity_default: {type: string, enum: [none, pii, financial, internal_id, confidential]}
```

### 6.2 Edge Schema

```yaml
edges:
  belongs_to:
    from: [API, Function, Field, DBColumn]
    to: [Service, API, Function, DBTable]
    properties:
      direction: {type: string, enum: [request, response]}  # 仅 Field→API

  calls:
    from: [API, Function, Service]
    to: [Function, Service]
    properties:
      call_type: {type: string, enum: [direct, rpc, http, mq]}
      protocol: {type: string}

  passes_to:
    from: [Field]
    to: [Field]
    properties:
      propagation_type: {type: string, enum: [pass_through, transform, aggregate, filter]}
      confidence: {type: float, required: true}
      transform_desc: {type: string}
      hop_count: {type: int}

  reads_from:
    from: [Function]
    to: [DBColumn]
    properties:
      query_type: {type: string, enum: [select, join, subquery]}

  writes_to:
    from: [Function]
    to: [DBColumn]
    properties:
      query_type: {type: string, enum: [insert, update, upsert, delete]}

  same_semantic_as:
    from: [Field]
    to: [Field]
    properties:
      confidence: {type: float, required: true}
      reason: {type: string}
      detected_by: {type: string, enum: [name_match, llm_inference, db_backtrack, human]}

  maps_to:
    from: [Field]
    to: [DBColumn]
    properties:
      confidence: {type: float}
      path_length: {type: int}            # 经过几个函数跳转

  has_type:
    from: [Field, DBColumn]
    to: [SemanticType]
    properties:
      confidence: {type: float}

  is_a:
    from: [SemanticType]
    to: [SemanticType]
    properties: {}
```

---

## 7. 规模估算

以字节 10 万个微服务为基础：

| 实体类型 | 估算数量 | 计算方式 |
|----------|---------|---------|
| Service | 100,000 | 10 万微服务 |
| API | 2,000,000 | 每服务 ~20 个 API |
| Function | 10,000,000 | 每服务 ~100 个函数 |
| Field | 20,000,000 | 每 API ~10 个字段 |
| DBTable | 500,000 | 每服务 ~5 张表 |
| DBColumn | 5,000,000 | 每表 ~10 列 |
| SemanticType | ~500 | 手动 + 自动发现 |
| **总节点数** | **~37,600,000** | |

| 边类型 | 估算数量 |
|--------|---------|
| belongs_to | ~37,000,000 |
| calls | ~20,000,000 |
| passes_to | ~30,000,000 |
| reads_from / writes_to | ~10,000,000 |
| same_semantic_as | ~5,000,000 |
| has_type | ~25,000,000 |
| **总边数** | **~127,000,000** |

约 **3700 万节点、1.27 亿边**——这在 Neo4j 企业版或 ByteGraph 的能力范围内。

---

## 8. 小结

本文设计了一套完整的字段级 ontology 数据模型：

1. **7 种节点类型**：从 Service 到 DBColumn 到 SemanticType，覆盖代码和数据全链路
2. **8 种边类型**：从 belongs_to 到 same_semantic_as，表达归属、调用、传播、映射、语义关联
3. **SemanticType 继承体系**：支持层级化语义分类和自动推理
4. **置信度传播**：每条边都有 confidence，沿传播链自动衰减
5. **完整的 room_id 例子**：展示字段从 API 到 DB 的全链路 ontology 表示

该模型可以直接用于 Neo4j（Cypher）或 ByteGraph 的 Property Graph 实现。

---

*最后更新: 2026-03-05*
