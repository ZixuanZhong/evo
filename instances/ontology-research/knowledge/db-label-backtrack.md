# DB 标签回溯：从已标注数据库列反向发现 API 暴露面

> 数据库字段已有分类标签（如 PII），如何自动发现哪些 API 字段最终读写了这些敏感数据？本文设计完整的反向回溯机制。

---

## 1. 核心场景

### 1.1 问题描述

字节跳动内部已经对部分数据库做了数据分类标注，例如：

```
MySQL table: users
  - phone_number  → 标签: PII（个人手机号）
  - id_card       → 标签: PII（身份证号）
  - balance       → 标签: Financial（账户余额）
  - nickname      → 标签: none
```

**问题**：这些已标注的 DB 列被哪些 API 暴露给了外部？哪些 API 字段最终读写了 `users.phone_number`？

**为什么重要**：
- 合规团队需要知道 PII 数据的所有外部暴露点
- 如果某个 API 无意中返回了手机号，这是数据泄露风险
- 手动审查十万个服务不现实——需要自动化

**类比**：把 DB 列想象成银行金库里的保险箱。我们知道哪些保险箱里有贵重物品（已标注），现在要找出所有通向这些保险箱的走廊和大门（API），确保每个入口都有安保（脱敏/权限控制）。

---

## 2. 反向传播算法

### 2.1 整体流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ ① 发现入口   │     │ ② 反向遍历   │     │ ③ API 匹配   │     │ ④ 生成报告   │
│              │     │              │     │              │     │              │
│ DB Column    │────→│ ORM/SQL 层   │────→│ 函数调用链   │────→│ API 暴露面   │
│ (已标注)     │     │ 找到访问函数  │     │ 反向追踪     │     │ 风险评估     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### 2.2 Step 1: 发现 DB 访问入口

首先找到所有直接操作目标 DB 列的函数。

```python
def find_db_accessors(db_column, code_graph):
    """
    找到所有直接读写目标 DB 列的函数。
    
    三种识别方式（按优先级）：
    1. ORM 模型匹配：GORM struct field → DB column 映射
    2. SQL 解析：原生 SQL 中引用的列名
    3. Code Graph 标注：已有的 reads_from/writes_to 边
    """
    accessors = []
    
    # 方式 1: ORM 模型匹配
    # 找到映射到该列的 Go struct field
    orm_models = find_orm_models(db_column.table_name)
    for model in orm_models:
        field = model.get_field_for_column(db_column.name)
        if field:
            # 找到所有使用这个 model field 的函数
            funcs = code_graph.find_field_references(model, field)
            for func, access_type in funcs:
                accessors.append(DBAccessor(
                    function=func,
                    access_type=access_type,  # read / write / readwrite
                    confidence=0.95,          # ORM 映射高可信
                    method="orm_model"
                ))
    
    # 方式 2: SQL 解析
    sql_funcs = code_graph.find_sql_references(db_column.table_name)
    for func, sql_text in sql_funcs:
        if column_referenced_in_sql(sql_text, db_column.name):
            access_type = detect_sql_access_type(sql_text, db_column.name)
            accessors.append(DBAccessor(
                function=func,
                access_type=access_type,
                confidence=0.90,
                method="sql_parse"
            ))
    
    # 方式 3: Code Graph 已有边
    graph_edges = code_graph.get_edges(
        target=db_column,
        edge_types=["reads_from", "writes_to"]
    )
    for edge in graph_edges:
        accessors.append(DBAccessor(
            function=edge.source,
            access_type=edge.type,
            confidence=0.92,
            method="code_graph"
        ))
    
    return deduplicate(accessors)
```

### 2.3 Step 2: 反向遍历调用链

从 DB 访问函数开始，反向追踪到 API handler。

```python
def backtrack_to_api(db_column, accessors, code_graph):
    """
    从 DB 访问函数反向追踪到 API handler。
    返回所有 (API Field, confidence, path) 三元组。
    """
    results = []
    
    for accessor in accessors:
        # 找到访问函数内与 DB 列对应的本地字段
        local_fields = map_column_to_local_fields(accessor.function, db_column)
        
        for field, field_conf in local_fields:
            # 使用 1.3 设计的反向传播算法
            api_fields = backward_propagate(
                start_field=field,
                start_confidence=accessor.confidence * field_conf,
                code_graph=code_graph
            )
            results.extend(api_fields)
    
    # 合并多路径
    merged = merge_by_api_field(results)
    return merged
```

### 2.4 Step 3: ORM/SQL 层的字段映射

这是回溯的关键一环——把 DB 列名映射回代码中的字段名。

#### GORM 模型映射（最常见）

```go
// Go 代码中的 ORM 模型
type User struct {
    ID          int64  `gorm:"column:id;primaryKey"`
    PhoneNumber string `gorm:"column:phone_number"` // ← DB 列 phone_number
    Nickname    string `gorm:"column:nickname"`
    Balance     int64  `gorm:"column:balance"`
}

// DAL 函数
func GetUserByID(ctx context.Context, userID int64) (*User, error) {
    var user User
    err := db.WithContext(ctx).Where("id = ?", userID).First(&user).Error
    return &user, err
}
```

**映射规则**：
- `gorm:"column:phone_number"` → 显式映射，置信度 0.98
- 无 tag 时按 GORM 命名约定：`PhoneNumber` → `phone_number`，置信度 0.90
- 自定义 `TableName()` 方法可能改变表名映射

#### 原生 SQL 映射

```go
func GetUserPhone(ctx context.Context, userID int64) (string, error) {
    var phone string
    err := db.Raw("SELECT phone_number FROM users WHERE id = ?", userID).Scan(&phone).Error
    return phone, err
}
```

**SQL 解析**：用 SQL parser 提取 SELECT 列、WHERE 条件、JOIN 关系，识别哪些列被读取。

---

## 3. 多路径问题

### 3.1 同一 DB 列被多条路径访问

`users.phone_number` 可能被多个服务、多个 API 访问：

```
路径 A: POST /api/v1/user/register → UserService.Register → dal.CreateUser → INSERT users.phone_number
路径 B: GET /api/v1/user/profile → UserService.GetProfile → dal.GetUser → SELECT users.phone_number
路径 C: POST /api/v1/user/verify → SMSService.SendCode → dal.GetUserPhone → SELECT users.phone_number
路径 D: GET /internal/admin/user → AdminService.GetUser → dal.GetUser → SELECT users.phone_number
```

### 3.2 多路径分析和风险评估

```python
def analyze_exposure(db_column, api_paths):
    """
    分析 DB 列的所有 API 暴露路径，生成风险报告。
    """
    report = ExposureReport(db_column=db_column)
    
    for path in api_paths:
        risk = RiskAssessment(
            api=path.api,
            field=path.api_field,
            confidence=path.confidence,
            access_type=path.access_type,       # read / write
            is_external=is_external_api(path.api),  # 外部 vs 内部 API
            has_auth=check_auth_middleware(path.api),
            has_masking=check_field_masking(path.api_field),
        )
        
        # 风险等级计算
        risk.level = compute_risk_level(
            sensitivity=db_column.classification_tag,
            is_external=risk.is_external,
            has_auth=risk.has_auth,
            has_masking=risk.has_masking,
            access_type=risk.access_type
        )
        
        report.add(risk)
    
    return report
```

### 3.3 风险等级矩阵

| DB 标签 | API 类型 | 有鉴权 | 有脱敏 | 风险等级 |
|---------|---------|--------|--------|---------|
| PII | 外部 | ❌ | ❌ | 🔴 **Critical** |
| PII | 外部 | ✅ | ❌ | 🟠 **High** |
| PII | 外部 | ✅ | ✅ | 🟢 **Low** |
| PII | 内部 | ❌ | ❌ | 🟠 **High** |
| PII | 内部 | ✅ | ❌ | 🟡 **Medium** |
| Financial | 外部 | ❌ | ❌ | 🔴 **Critical** |
| Financial | 外部 | ✅ | ❌ | 🟡 **Medium** |
| none | 任何 | 任何 | 任何 | 🟢 **Low** |

---

## 4. 多义性问题

### 4.1 问题描述

不同服务中名为 `user_id` 的字段可能代表不同含义：

```
服务 A (直播间): user_id = 观众的用户 ID → 关联 users.id
服务 B (礼物):   user_id = 送礼者 ID → 关联 users.id  
服务 C (结算):   user_id = 主播 ID → 关联 users.id（但语义不同！）
```

同一个 DB 列 `users.id` 被回溯时，可能找到多个叫 `user_id` 的 API 字段，但它们的语义上下文完全不同。

### 4.2 消歧策略

#### 策略 1: 上下文注入

回溯时把调用链上下文注入到 LLM prompt 中：

```
分析以下调用链，确认 API 字段 `user_id` 在此上下文中代表什么：

调用链：POST /api/v1/gift/send → GiftHandler → RecordGift → dal.InsertGiftRecord
API 字段：SendGiftReq.user_id

这个 user_id 代表的是：
A) 送礼物的观众
B) 收礼物的主播
C) 其他

输出 JSON: {"meaning": "A/B/C", "semantic": "中文描述", "confidence": 0.9}
```

#### 策略 2: 命名模式匹配

```python
NAMING_PATTERNS = {
    "sender_id":    "发送者/操作者",
    "receiver_id":  "接收者",
    "anchor_id":    "主播",
    "viewer_id":    "观众",
    "creator_id":   "创建者",
    "operator_id":  "操作员",
    "target_id":    "操作对象",
}

def disambiguate_by_naming(field_name, context_fields):
    """
    通过字段命名模式和周围字段推断语义。
    如果 struct 中同时有 sender_id 和 receiver_id，
    则 sender_id 是操作者，receiver_id 是对象。
    """
    # 精确匹配
    if field_name in NAMING_PATTERNS:
        return NAMING_PATTERNS[field_name], 0.85
    
    # 上下文推断：看同一 struct 中的其他字段
    for sibling in context_fields:
        if sibling.name in NAMING_PATTERNS:
            # 如果有 sender_id，那 user_id 可能是别的角色
            pass
    
    return None, 0.0
```

#### 策略 3: 回溯路径区分

同一 DB 列的不同回溯路径自然携带不同的上下文，利用路径本身做消歧：

```
路径 A: POST /gift/send → GiftHandler → req.SenderID → dal.from_user_id → users.id
  → 上下文: 送礼场景，sender 角色

路径 B: GET /user/profile → ProfileHandler → req.UserID → dal.GetUser(id) → users.id
  → 上下文: 查询场景，查询主体

路径 C: GET /room/info → RoomHandler → room.AnchorID → dal.GetUser(id) → users.id
  → 上下文: 直播间场景，anchor 角色
```

每条路径产生一个独立的 `same_semantic_as` 边，带不同的 `context` 属性。

---

## 5. 增量更新机制

### 5.1 为什么需要增量更新

代码每天都在变更。全量重新回溯所有 DB 列成本太高（10 万服务级别）。需要增量策略。

### 5.2 变更检测

```python
def detect_affected_columns(code_change):
    """
    给定一个代码变更（Git diff），找到受影响的 DB 列回溯路径。
    """
    affected = set()
    
    # 1. 变更的函数列表
    changed_funcs = extract_changed_functions(code_change)
    
    for func in changed_funcs:
        # 2. 找到经过该函数的所有回溯路径
        paths = graph.get_paths_through(func)
        
        for path in paths:
            # 3. 标记受影响的 DB 列
            affected.add(path.db_column)
    
    return affected
```

### 5.3 增量更新流程

```
代码变更（Git push）
    │
    ▼
┌────────────────────────┐
│ 1. 解析 Git diff       │  识别变更的文件和函数
│    extract changed     │
│    functions           │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│ 2. 查询受影响路径       │  从 ontology graph 中查找
│    经过变更函数的        │  经过这些函数的所有传播路径
│    所有回溯路径          │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│ 3. 重新分析变更函数     │  只重新运行变更函数的
│    的字段映射           │  AST 分析 + LLM 消歧
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│ 4. 更新 ontology graph │  更新受影响的边
│    + 重算置信度         │  重新计算路径置信度
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│ 5. 触发告警（如有）     │  如果新增了高风险暴露
│    新增高风险暴露?       │  通知安全/合规团队
└────────────────────────┘
```

### 5.4 告警条件

| 事件 | 告警级别 | 描述 |
|------|---------|------|
| 新增 PII 暴露 | 🔴 Critical | 新 API 字段关联到 PII 列且无脱敏 |
| 移除鉴权 | 🟠 High | API 的鉴权 middleware 被删除 |
| 新增读取路径 | 🟡 Medium | 新代码读取了已标注敏感列 |
| 置信度大幅变化 | 🟡 Medium | 某条路径置信度变化 > 0.2 |
| 路径断裂 | ℹ️ Info | 代码重构导致原有路径不再存在 |

---

## 6. 完整场景 Walk-Through

### 6.1 场景设定

```
目标：回溯 users.phone_number（PII 标签）的所有 API 暴露面

已知信息：
  - DB: MySQL, table=users, column=phone_number, tag=PII
  - 框架: Go-Kitex (RPC) + Go-Hertz (HTTP)
```

### 6.2 Step 1: 找到 DB 访问入口

```
扫描结果：
├── dal/user.go: GetUserByID()       → SELECT * FROM users WHERE id = ?
│     → 读取 phone_number (conf: 0.95, method: orm_model)
├── dal/user.go: CreateUser()        → INSERT INTO users(...)
│     → 写入 phone_number (conf: 0.95, method: orm_model)
├── dal/user.go: UpdatePhone()       → UPDATE users SET phone_number = ? WHERE id = ?
│     → 写入 phone_number (conf: 0.98, method: sql_parse)
└── dal/sms.go: GetPhoneByUserID()   → SELECT phone_number FROM users WHERE id = ?
      → 读取 phone_number (conf: 0.98, method: sql_parse)
```

### 6.3 Step 2: 反向追踪各入口

#### 路径 A: GetUserByID → 用户资料 API

```
dal.GetUserByID()
  ← called by: service.UserServiceImpl.GetProfile()
    ← called by: handler.GetUserProfile() [Hertz handler]
      ← API: GET /api/v1/user/profile
        ← 响应字段: GetProfileResp.Phone (json:"phone")

路径: users.phone_number → User.PhoneNumber → resp.Phone → API 响应
置信度: 0.95 × 0.92 × 0.90 = 0.787
访问类型: 读取 → 外部 API 响应中返回
```

#### 路径 B: CreateUser → 注册 API

```
dal.CreateUser()
  ← called by: service.UserServiceImpl.Register()
    ← called by: handler.Register() [Hertz handler]
      ← API: POST /api/v1/user/register
        ← 请求字段: RegisterReq.PhoneNumber (json:"phone_number")

路径: users.phone_number ← User.PhoneNumber ← req.PhoneNumber ← API 请求
置信度: 0.95 × 0.95 × 0.92 = 0.832
访问类型: 写入 ← 外部 API 请求传入
```

#### 路径 C: GetPhoneByUserID → 短信验证 API

```
dal.GetPhoneByUserID()
  ← called by: service.SMSServiceImpl.SendVerifyCode()
    ← called by: handler.SendVerifyCode() [Hertz handler]
      ← API: POST /api/v1/sms/send
        ← 请求字段: SendCodeReq.UserID (json:"user_id") — 间接访问

路径: users.phone_number → phone → smsService.SendSMS(phone) → [不在响应中]
置信度: 0.98 × 0.88 × 0.85 = 0.733
访问类型: 读取 → 内部使用（发短信），不暴露给 API 调用者
```

#### 路径 D: GetUserByID → 管理后台 API

```
dal.GetUserByID()
  ← called by: service.AdminServiceImpl.GetUserDetail()
    ← called by: handler.AdminGetUser() [Hertz handler]
      ← API: GET /internal/admin/user/:id
        ← 响应字段: AdminUserResp.PhoneNumber (json:"phone_number")

路径: users.phone_number → User.PhoneNumber → resp.PhoneNumber → API 响应
置信度: 0.95 × 0.92 × 0.95 = 0.808
访问类型: 读取 → 内部管理 API 响应中返回
```

### 6.4 Step 3: 生成暴露报告

```
╔═══════════════════════════════════════════════════════════════════╗
║  DB 列暴露报告: users.phone_number (PII)                        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  🔴 Critical (1):                                                ║
║  ┌─────────────────────────────────────────────────────────┐     ║
║  │ GET /api/v1/user/profile → resp.Phone                   │     ║
║  │ 外部 API, 读取返回, 无脱敏                                │     ║
║  │ 置信度: 0.787 | 建议: 添加手机号脱敏 (138****8888)       │     ║
║  └─────────────────────────────────────────────────────────┘     ║
║                                                                   ║
║  🟡 Medium (2):                                                  ║
║  ┌─────────────────────────────────────────────────────────┐     ║
║  │ POST /api/v1/user/register → req.PhoneNumber             │     ║
║  │ 外部 API, 写入, 有鉴权                                    │     ║
║  │ 置信度: 0.832 | 风险: 用户主动提交，可接受                 │     ║
║  ├─────────────────────────────────────────────────────────┤     ║
║  │ GET /internal/admin/user/:id → resp.PhoneNumber          │     ║
║  │ 内部 API, 读取返回, 有鉴权, 无脱敏                        │     ║
║  │ 置信度: 0.808 | 建议: 添加操作审计日志                     │     ║
║  └─────────────────────────────────────────────────────────┘     ║
║                                                                   ║
║  🟢 Low (1):                                                     ║
║  ┌─────────────────────────────────────────────────────────┐     ║
║  │ POST /api/v1/sms/send (间接)                              │     ║
║  │ 内部使用, 不暴露给调用者                                    │     ║
║  │ 置信度: 0.733 | 风险: 手机号仅用于发送短信                  │     ║
║  └─────────────────────────────────────────────────────────┘     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 7. 与传统 Data Lineage 对比

### 7.1 对比表

| 维度 | 传统 Data Lineage | 我们的 DB 标签回溯 |
|------|-------------------|-------------------|
| **分析粒度** | 表级 / 列级 | 列级 → **API 字段级** |
| **覆盖范围** | 数据仓库内（ETL → 报表） | 代码层（DB ↔ API） |
| **语义理解** | ❌ 只追踪数据流 | ✅ **LLM 理解字段含义** |
| **多义性处理** | ❌ 同名字段无法区分 | ✅ **上下文消歧** |
| **变更感知** | Schema 变更触发 | **代码变更触发** |
| **风险评估** | 有限 | ✅ **结合 API 鉴权/脱敏状态** |
| **跨服务** | 有限（通常单系统） | ✅ **跨微服务调用链** |
| **自动化程度** | 需要手动配置数据流 | ✅ **Code Graph 自动发现** |

### 7.2 我们做得更多的部分

**1. 从代码到 API 的端到端追踪**

传统 lineage 工具（如 Datafold、Tokern、OpenLineage）主要追踪数据在 ETL pipeline 和数据仓库中的流动。我们的方案补齐了"源头"——代码层的 DB 到 API 映射。

参考: [Datafold - How to Trace PII with Column-level Lineage](https://www.datafold.com/blog/how-to-trace-pii-with-column-level-lineage)

**2. 语义消歧**

传统 lineage 追踪数据流但不理解语义。同一个 `user_id` 在不同上下文中代表不同角色（观众/主播/管理员），我们的 LLM 消歧机制可以区分。

**3. 风险评估**

传统 lineage 告诉你"数据流到了这里"。我们还能告诉你"这个暴露是否安全"——通过分析 API 的鉴权、脱敏、访问控制状态。

**4. 代码级增量更新**

传统 lineage 在 schema 变更时重算。我们在每次 Git push 时自动检测受影响的传播路径。

---

## 8. 规模估算

假设 10 万个微服务，已标注 50 万个 DB 列：

| 指标 | 估算 |
|------|------|
| 已标注 DB 列 | 500,000 |
| 每列平均访问函数数 | ~3 |
| 需要回溯的起点 | ~1,500,000 |
| 平均路径长度 | ~4 跳 |
| 需要 LLM 消歧的边 | ~15%（约 900,000 次） |
| LLM 调用成本（GPT-4o-mini, ~500 token/次） | ~$450 |
| 全量回溯耗时 | ~2-3 天（含并行） |
| 增量更新（每日 ~1% 代码变更） | ~30 分钟 |

---

## 9. 小结

| 模块 | 设计 |
|------|------|
| **DB 访问发现** | ORM 模型匹配 + SQL 解析 + Code Graph 边 |
| **反向传播** | 复用 1.3 反向传播算法，BFS + 置信度衰减 |
| **多路径** | 独立分析每条路径，Noisy-OR 合并，生成暴露报告 |
| **多义性** | 上下文注入 LLM + 命名模式 + 路径自然区分 |
| **增量更新** | Git diff → 受影响函数 → 重算受影响路径 |
| **风险评估** | 敏感性 × API 类型 × 鉴权 × 脱敏 → 风险等级 |

核心价值：**把"数据库里哪些列是敏感的"这个已知信息，自动传播到"哪些 API 暴露了敏感数据"这个未知问题**——这是传统数据治理的最大盲区。

---

*最后更新: 2026-03-05*
*参考: Datafold Column-Level Lineage, Tokern/PIICatcher, OpenLineage*
