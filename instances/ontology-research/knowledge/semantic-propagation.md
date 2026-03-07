# 调用链语义传播算法：字段如何沿 Code Graph 流动

> 本文设计从 Code Graph 调用链推导字段语义传递的算法，包括正向/反向传播、置信度计算、LLM 消歧机制。

---

## 1. 问题定义

### 1.1 我们要解决什么问题

给定一条函数调用链：

```
API Handler → FuncA → FuncB → FuncC → DB Write
```

一个字段（比如 `user_id`）从 API 入口传入，经过多次函数调用，最终写入数据库。我们需要：

1. **追踪这个字段在调用链上的每一跳**：它在每个函数里叫什么名字？经过了什么变换？
2. **在每一跳上标注传播类型和置信度**：是原样传递还是转换了？我们有多确定？
3. **反向追踪**：如果数据库 `phone_number` 列已标记为 PII，哪些 API 字段最终碰了它？

**类比**：把字段想象成一个包裹在快递网络中流转。每一站（函数）可能重新贴标签、拆分、合并。我们要追踪包裹的完整旅程。

### 1.2 与传统 Taint Analysis 的关系

我们的方法本质上是 **field-level taint propagation**——类似安全领域的污点分析，但目标不同：

| 维度 | 安全 Taint Analysis | 我们的语义传播 |
|------|---------------------|---------------|
| **目标** | 检测不安全数据流 | 追踪字段语义和分类 |
| **精度要求** | 宁可误报不可漏报 | 需要平衡精度和成本 |
| **分析粒度** | 变量级 | 字段级（struct field） |
| **跨服务** | 通常单进程 | 跨微服务（通过 Code Graph） |
| **消歧手段** | 类型系统 | **LLM 语义理解** ← 核心差异 |

**参考**：Semgrep 的 dataflow analysis 引擎支持有限的 field-sensitivity taint tracking（参见 [Semgrep Dataflow Docs](https://semgrep.dev/docs/writing-rules/data-flow/data-flow-overview)）。Column-Level Lineage (CLL) 是数据治理领域的对应概念（参见 [Alation: 4 Pillars of Data Lineage](https://www.alation.com/blog/data-lineage-pillars-end-to-end-journey/)）。

---

## 2. 字段映射类型

字段在函数间传递时，有四种基本映射类型：

### 2.1 四种映射类型

```
┌─────────────────────────────────────────────────────────┐
│  Pass-Through（直传）                                    │
│  req.UserID ──────────→ dal.UserID                      │
│  字段值原样传递，语义不变                                  │
│  置信度衰减：0%                                          │
├─────────────────────────────────────────────────────────┤
│  Transform（转换）                                       │
│  req.Price × req.Count ─→ order.TotalAmount             │
│  字段值经过计算/格式化                                     │
│  置信度衰减：10-20%                                      │
├─────────────────────────────────────────────────────────┤
│  Aggregate（聚合）                                       │
│  req.FirstName + req.LastName ─→ user.FullName          │
│  多个字段合并为一个                                       │
│  置信度衰减：20-30%                                      │
├─────────────────────────────────────────────────────────┤
│  Fan-Out（分支）                                         │
│  req.Address ─→ order.Province, order.City, order.Zip   │
│  一个字段拆分为多个                                       │
│  置信度衰减：15-25%                                      │
└─────────────────────────────────────────────────────────┘
```

### 2.2 检测策略

| 映射类型 | AST 检测特征 | LLM 需要介入？ |
|----------|-------------|---------------|
| Pass-Through | `b.X = a.X` 或 `b.X = a.Y`（同类型直接赋值） | 同名: No; 改名: Yes |
| Transform | 赋值右侧有运算符或函数调用 | Yes（理解转换语义） |
| Aggregate | 赋值右侧引用多个源字段 | Yes（理解合并语义） |
| Fan-Out | 同一源字段出现在多个赋值左侧 | Yes（理解拆分语义） |

---

## 3. 传播算法设计

### 3.1 正向传播（API → DB）

从 API 入口字段出发，沿调用链向下追踪字段到达数据库的路径。

```python
def forward_propagate(api_field, call_chain, graph):
    """
    正向传播：从 API 字段出发，沿调用链追踪到 DB。
    
    Args:
        api_field: 起始字段 (Field node)
        call_chain: 调用链 [FuncA, FuncB, FuncC, ...]
        graph: Ontology Graph 实例
    
    Returns:
        propagation_paths: List[PropagationPath] 所有传播路径
    """
    queue = [(api_field, 1.0, [])]  # (当前字段, 累计置信度, 路径)
    results = []
    visited = set()
    
    while queue:
        current_field, confidence, path = queue.pop(0)
        
        if confidence < CONFIDENCE_THRESHOLD:  # 低于阈值停止（默认 0.3）
            continue
        if current_field.id in visited:
            continue
        visited.add(current_field.id)
        
        # 获取当前字段所在函数的下游调用
        current_func = graph.get_parent_function(current_field)
        callees = graph.get_callees(current_func)
        
        for callee in callees:
            # Step 1: AST 级匹配（快速、免费）
            mappings = ast_match_fields(current_func, callee, current_field)
            
            if mappings:
                for target_field, mapping_type, ast_conf in mappings:
                    edge_conf = compute_confidence(mapping_type, ast_conf)
                    new_conf = confidence * edge_conf
                    new_path = path + [(current_field, target_field, mapping_type, edge_conf)]
                    
                    # 如果目标是 DB 写入，记录完整路径
                    if graph.is_db_write(callee):
                        db_column = graph.resolve_db_column(callee, target_field)
                        results.append(PropagationPath(
                            source=api_field,
                            sink=db_column,
                            path=new_path,
                            total_confidence=new_conf
                        ))
                    else:
                        queue.append((target_field, new_conf, new_path))
            
            else:
                # Step 2: AST 无法匹配时，调用 LLM 消歧
                if confidence > LLM_INVOKE_THRESHOLD:  # 仅高置信度路径触发 LLM
                    llm_mappings = llm_resolve_mapping(
                        source_func=current_func,
                        target_func=callee,
                        source_field=current_field
                    )
                    for target_field, mapping_type, llm_conf in llm_mappings:
                        edge_conf = llm_conf * LLM_DISCOUNT  # LLM 结果打折
                        new_conf = confidence * edge_conf
                        new_path = path + [(current_field, target_field, mapping_type, edge_conf)]
                        queue.append((target_field, new_conf, new_path))
    
    return results
```

### 3.2 反向传播（DB → API）

从已标注的数据库列出发，反向追踪到哪些 API 字段。

```python
def backward_propagate(db_column, graph):
    """
    反向传播：从 DB 列出发，反向追踪到 API 字段。
    
    Args:
        db_column: 已标注的 DB 列 (DBColumn node)
        graph: Ontology Graph 实例
    
    Returns:
        api_fields: List[(Field, confidence, path)] 所有关联的 API 字段
    """
    # 找到所有读写该列的函数
    accessor_funcs = graph.get_accessors(db_column)  # reads_from + writes_to
    
    queue = []
    for func in accessor_funcs:
        # 找到函数内与该 DB 列对应的字段
        local_fields = resolve_local_fields(func, db_column)
        for field, conf in local_fields:
            queue.append((field, conf, []))
    
    results = []
    visited = set()
    
    while queue:
        current_field, confidence, path = queue.pop(0)
        
        if confidence < CONFIDENCE_THRESHOLD:
            continue
        if current_field.id in visited:
            continue
        visited.add(current_field.id)
        
        current_func = graph.get_parent_function(current_field)
        
        # 获取谁调用了当前函数（反向）
        callers = graph.get_callers(current_func)
        
        for caller in callers:
            # 反向匹配：当前函数的参数字段 ← 调用者传入的字段
            mappings = reverse_match_fields(caller, current_func, current_field)
            
            for source_field, mapping_type, match_conf in mappings:
                edge_conf = compute_confidence(mapping_type, match_conf)
                new_conf = confidence * edge_conf
                new_path = path + [(current_field, source_field, mapping_type, edge_conf)]
                
                # 如果 caller 是 API handler，记录结果
                if graph.is_api_handler(caller):
                    api = graph.get_parent_api(caller)
                    results.append((source_field, new_conf, new_path, api))
                else:
                    queue.append((source_field, new_conf, new_path))
    
    return results
```

### 3.3 分支处理（Fan-Out & Fan-In）

**Fan-Out（一对多）**：一个字段传播到多个目标

```python
def handle_fan_out(source_field, target_fields):
    """
    一个源字段映射到多个目标字段。
    每条边独立计算置信度。
    """
    edges = []
    for target in target_fields:
        mapping_type = detect_mapping_type(source_field, target)
        conf = compute_confidence(mapping_type, base_conf=0.85)
        # Fan-out 额外惩罚：目标越多，每条边置信度越低
        fan_penalty = 1.0 / (1.0 + 0.1 * len(target_fields))
        edges.append(PropagationEdge(
            source=source_field,
            target=target,
            mapping_type=mapping_type,
            confidence=conf * fan_penalty
        ))
    return edges
```

**Fan-In（多对一）**：多个字段聚合为一个

```python
def handle_fan_in(source_fields, target_field):
    """
    多个源字段聚合为一个目标字段。
    目标字段继承所有源字段的最高敏感性。
    """
    # 聚合语义：目标字段 = f(source_1, source_2, ...)
    max_sensitivity = max(f.sensitivity for f in source_fields)
    
    edges = []
    for source in source_fields:
        edges.append(PropagationEdge(
            source=source,
            target=target_field,
            mapping_type="aggregate",
            confidence=0.80  # 聚合默认较低置信度
        ))
    
    # 目标字段的敏感性取最高（保守策略）
    target_field.sensitivity = max_sensitivity
    return edges
```

---

## 4. LLM 辅助消歧

### 4.1 何时需要 LLM

AST 级分析能处理大部分 pass-through 场景（字段名相同或直接赋值），但以下情况需要 LLM：

| 场景 | 例子 | AST 能力 | LLM 能力 |
|------|------|---------|---------|
| **字段改名** | `req.UserID → param.uid` | ❌ 名字不同 | ✅ 语义理解 |
| **类型转换** | `strconv.FormatInt(req.ID, 10)` | ❌ 不理解语义 | ✅ 理解是格式化 |
| **条件传播** | `if req.Type == 1 { ... }` | ❌ 不追踪分支 | ✅ 理解条件逻辑 |
| **间接传播** | `map[key] = req.Val; ... use(map[key])` | ❌ 别名分析 | ⚠️ 部分能力 |
| **跨 goroutine** | `go func() { ch <- req.ID }()` | ❌ | ⚠️ 有限 |

### 4.2 LLM 消歧 Prompt

```
你是代码语义分析助手。分析以下两个函数之间的字段传递关系。

## 调用者函数
```go
{caller_code}
```

## 被调用函数
```go
{callee_code}
```

## 源字段
{source_field_name} ({source_field_type}) - 语义：{source_semantic}

## 任务
1. 源字段的值传递给了被调用函数的哪个参数/字段？
2. 传递类型是什么？(pass_through / transform / aggregate / filter)
3. 置信度多少？(0-1)

输出 JSON:
{
  "mappings": [
    {
      "target_field": "目标字段名",
      "mapping_type": "pass_through|transform|aggregate|filter",
      "confidence": 0.9,
      "reasoning": "一句话解释"
    }
  ]
}
```

### 4.3 LLM 调用策略

```
优先级和成本控制：

1. AST 精确匹配 → 免费，置信度 0.95+
2. AST 模糊匹配（类型相同+位置对应）→ 免费，置信度 0.80
3. LLM 消歧（仅当路径累计置信度 > 0.5）→ ~500 token/次
4. 多次 LLM 投票（敏感字段，3 次调用取共识）→ ~1500 token/次

成本控制阈值：
- CONFIDENCE_THRESHOLD = 0.3    # 低于此值停止传播
- LLM_INVOKE_THRESHOLD = 0.5    # 低于此值不调用 LLM
- LLM_DISCOUNT = 0.85           # LLM 结果的置信度折扣
- MAX_HOPS = 10                 # 最大传播跳数
- MAX_FAN_OUT = 20              # 最大分支数
```

---

## 5. Confidence Scoring 机制

### 5.1 边置信度计算

```python
def compute_confidence(mapping_type, base_conf, source="ast"):
    """
    计算一条传播边的置信度。
    
    base_conf: AST 或 LLM 给出的初始匹配置信度
    """
    # 映射类型衰减系数
    type_decay = {
        "pass_through": 1.0,    # 直传不衰减
        "transform":    0.85,   # 转换衰减 15%
        "aggregate":    0.75,   # 聚合衰减 25%
        "fan_out":      0.80,   # 分支衰减 20%
        "filter":       0.95,   # 过滤条件小幅衰减
    }
    
    # 来源折扣
    source_discount = {
        "ast_exact":   1.0,     # AST 精确匹配
        "ast_fuzzy":   0.90,    # AST 模糊匹配
        "llm_single":  0.85,    # 单次 LLM
        "llm_vote":    0.92,    # 多次 LLM 投票
        "human":       1.0,     # 人工确认
    }
    
    decay = type_decay.get(mapping_type, 0.80)
    discount = source_discount.get(source, 0.85)
    
    return base_conf * decay * discount
```

### 5.2 路径置信度

路径置信度 = 所有边置信度的乘积：

```
path_confidence = edge_1.conf × edge_2.conf × ... × edge_n.conf
```

**示例**：
```
API.RoomID → (pass_through, 0.95) → FuncA.roomID → (pass_through, 0.92) 
→ FuncB.room_id → (transform, 0.78) → DB.room_id

路径置信度 = 0.95 × 0.92 × 0.78 = 0.681
```

### 5.3 多路径合并

同一对 (API Field, DB Column) 之间可能有多条路径。合并策略：

```python
def merge_paths(paths):
    """
    多条路径合并为最终置信度。
    采用 noisy-OR 模型：至少一条路径正确的概率。
    
    P(correct) = 1 - ∏(1 - p_i) for all paths i
    """
    if not paths:
        return 0.0
    prob_all_wrong = 1.0
    for path in paths:
        prob_all_wrong *= (1.0 - path.confidence)
    return 1.0 - prob_all_wrong

# 例：两条路径置信度分别为 0.68 和 0.55
# 合并置信度 = 1 - (1-0.68)(1-0.55) = 1 - 0.32×0.45 = 1 - 0.144 = 0.856
```

---

## 6. 完整 Walk-Through：5 节点调用链

### 6.1 场景

直播间送礼物：用户通过 API 送礼物，经过 gateway → gift service → payment service → DB。

### 6.2 调用链图

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│ ① API       │    │ ② GiftHandler│    │ ③ RecordGift │    │ ④ DeductBal  │    │ ⑤ DB Write  │
│ POST /gift  │───→│ handleSend() │───→│ recordGift() │───→│ deduct()     │───→│ INSERT INTO │
│ send        │    │              │    │              │    │              │    │ gift_records│
│             │    │              │    │              │    │              │    │ + UPDATE    │
│             │    │              │    │              │    │              │    │   wallets   │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
```

### 6.3 逐跳追踪

**追踪字段：`sender_id`**

#### 跳 1: API → GiftHandler

```go
// ① API 层
type SendGiftReq struct {
    SenderID int64 `json:"sender_id"`  // 送礼观众 ID
}

// ② GiftHandler
func handleSend(ctx context.Context, c *app.RequestContext) {
    var req SendGiftReq
    c.BindAndValidate(&req)
    recordGift(ctx, req.SenderID, req.AnchorID, req.GiftID)
}
```

**分析**：
- 匹配方式：AST 精确匹配（`req.SenderID` 直接作为参数传入）
- 映射类型：pass_through
- 边置信度：0.95（AST 精确，pass_through）

#### 跳 2: GiftHandler → RecordGift

```go
// ③ RecordGift
func recordGift(ctx context.Context, uid int64, anchorID int64, giftID int32) {
    record := &GiftRecord{
        FromUserID: uid,       // ← 字段改名了！sender_id → uid → FromUserID
        ToUserID:   anchorID,
        GiftType:   giftID,
    }
    dal.InsertGiftRecord(ctx, record)
    deduct(ctx, uid, getGiftPrice(giftID))
}
```

**分析**：
- `req.SenderID` → 参数 `uid` → `record.FromUserID`
- 匹配方式：AST 可以追踪参数位置（第一个 int64 参数），但 `uid → FromUserID` 需要 LLM
- 映射类型：pass_through（值没变，只是改名）
- LLM 消歧：{"target_field": "FromUserID", "mapping_type": "pass_through", "confidence": 0.88, "reasoning": "uid 是 sender_id 的简写，赋值给 FromUserID 表示送礼者"}
- 边置信度：0.88 × 0.85 (LLM 折扣) = **0.748**

#### 跳 3: RecordGift → DB Insert (gift_records)

```go
// dal.InsertGiftRecord
func InsertGiftRecord(ctx context.Context, record *GiftRecord) error {
    return db.Table("gift_records").Create(record).Error
}
```

**分析**：
- `record.FromUserID` → DB column `gift_records.from_user_id`
- 匹配方式：ORM 自动映射（Go struct tag 或 naming convention）
- 映射类型：pass_through
- 边置信度：0.92（ORM 映射高可信度）

#### 跳 4: GiftHandler → Deduct → DB Update (wallets)

```go
// ④ deduct
func deduct(ctx context.Context, userID int64, amount int64) {
    db.Table("wallets").Where("user_id = ?", userID).
        Update("balance", gorm.Expr("balance - ?", amount))
}
```

**分析**：
- `uid` → `deduct.userID` → `wallets.user_id`（WHERE 条件）
- 映射类型：filter（用于查询条件而非写入值）
- 边置信度：0.90

### 6.4 完整传播路径表

```
路径 A: sender_id → gift_records.from_user_id
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① API.SenderID ──pass_through(0.95)──→ ② handleSend.req.SenderID
② req.SenderID ──pass_through(0.748)──→ ③ record.FromUserID
③ FromUserID   ──pass_through(0.92)──→ ⑤ gift_records.from_user_id

路径置信度 = 0.95 × 0.748 × 0.92 = 0.654 ✅ (> 0.3 阈值)

路径 B: sender_id → wallets.user_id (WHERE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① API.SenderID ──pass_through(0.95)──→ ② handleSend.req.SenderID
② req.SenderID ──pass_through(0.748)──→ ③ recordGift.uid
③ uid          ──pass_through(0.92)──→ ④ deduct.userID
④ userID       ──filter(0.90)───────→ ⑤ wallets.user_id

路径置信度 = 0.95 × 0.748 × 0.92 × 0.90 = 0.588 ✅
```

### 6.5 最终结论

```json
{
  "source_field": "SendGiftReq.SenderID",
  "semantic_type": "UserIdentifier",
  "sensitivity": "internal_id",
  "db_mappings": [
    {
      "table": "gift_records",
      "column": "from_user_id",
      "relationship": "写入值",
      "confidence": 0.654,
      "hops": 3
    },
    {
      "table": "wallets",
      "column": "user_id",
      "relationship": "查询条件",
      "confidence": 0.588,
      "hops": 4
    }
  ]
}
```

---

## 7. 算法复杂度与优化

### 7.1 复杂度分析

| 操作 | 复杂度 | 说明 |
|------|--------|------|
| 单条调用链遍历 | O(L × F) | L=链长度, F=每函数平均字段数 |
| 全图正向传播 | O(N × L × F) | N=API 字段总数 |
| 全图反向传播 | O(M × L × F) | M=DB 列总数 |
| LLM 调用 | O(K) | K=无法 AST 匹配的边数 |

### 7.2 优化策略

```
1. 批量处理：同一函数对的所有字段映射合并为一次 LLM 调用
2. 缓存：相同函数对的映射结果缓存复用
3. 剪枝：置信度 < 0.3 的路径立即停止
4. 优先级：从已知高敏感 DB 列开始反向传播（ROI 更高）
5. 增量更新：代码变更只重新分析受影响的调用链
6. 并行化：不同调用链的传播可以并行执行
```

### 7.3 增量更新机制

```
当函数 F 的代码变更时：
1. 找到所有经过 F 的传播路径
2. 仅重新分析 F 和相邻函数的字段映射
3. 重新计算受影响路径的置信度
4. 如果置信度变化 > 0.1，触发下游通知
```

---

## 8. 小结

| 模块 | 设计 |
|------|------|
| **映射类型** | 4 种：pass_through / transform / aggregate / fan_out |
| **正向传播** | BFS 遍历调用链，AST 优先 + LLM 兜底 |
| **反向传播** | 从 DB 列反向 BFS，追踪到 API 字段 |
| **置信度** | 边级计算（类型衰减 × 来源折扣），路径级乘积 |
| **多路径合并** | Noisy-OR 模型 |
| **LLM 调用** | 仅在 AST 失败 + 置信度 > 0.5 时触发 |
| **分支处理** | Fan-out 惩罚 + Fan-in 敏感性上提 |
| **增量更新** | 仅重算受影响路径 |

核心思想：**AST 做重活（免费、快），LLM 做巧活（消歧、语义），置信度做裁判（控制传播质量）**。

---

*最后更新: 2026-03-05*
*参考: Semgrep Dataflow Analysis, Alation Column-Level Lineage, Noisy-OR Probabilistic Model*
