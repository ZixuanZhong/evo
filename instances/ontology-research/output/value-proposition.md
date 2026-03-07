# 落地价值全景：Ontology Graph 能做什么？

> 本文分析字段级 Ontology Graph 的 7 个核心落地场景，每个场景含具体 use case、Cypher 查询示例和 before/after 对比。

---

## 场景 1：数据分类自动化

> **一句话**：自动发现全公司代码中的 PII、金融数据等敏感字段，不依赖人工标注。

**目标用户**：数据治理团队、合规团队

**具体 Use Case**：
合规团队需要知道"全公司有多少 API 字段涉及用户手机号"。传统方式需要每个团队自查上报，覆盖率不到 30%。

**Cypher 查询**：
```cypher
// 查找所有被标注为 PII 的字段
MATCH (f:Field)-[:has_type]->(st:SemanticType)
WHERE st.sensitivity_default = 'pii'
RETURN f.name, f.semantic, f.json_name, f.confidence
ORDER BY f.confidence DESC
LIMIT 100

// 统计各敏感性类型的字段数量
MATCH (f:Field)
WHERE f.sensitivity IS NOT NULL
RETURN f.sensitivity, count(f) AS field_count
ORDER BY field_count DESC
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 发现方式 | 人工审查 + 正则匹配 | LLM 语义分析自动标注 |
| 覆盖率 | ~30% | ~90% |
| 更新频率 | 季度（人工驱动） | 实时（Git push 触发） |
| 成本 | 高（需要每个团队配合） | 低（全自动化 pipeline） |

**预期价值**：从人工标注 30% 覆盖率提升到自动化 90%，每年节省 ~2000 人天的人工审查工作。

---

## 场景 2：API Schema 语义管理

> **一句话**：为每个 API 字段建立统一的语义描述，解决"这个字段到底是什么意思"的问题。

**目标用户**：API 平台团队、前后端开发

**具体 Use Case**：
前端开发调用 `GET /api/v1/user/profile`，看到响应中有 `uid`、`user_id`、`account_id` 三个字段，不确定它们的区别。Ontology Graph 提供每个字段的中文语义描述和语义类型。

**Cypher 查询**：
```cypher
// 查询某个 API 的完整字段语义
MATCH (api:API {route: '/api/v1/user/profile', http_method: 'GET'})
  <-[:belongs_to]-(f:Field)
RETURN f.name, f.json_name, f.go_type, f.semantic, f.sensitivity, f.direction
ORDER BY f.direction, f.name

// 查找语义相同但名字不同的字段（字段标准化候选）
MATCH (f1:Field)-[:same_semantic_as]->(f2:Field)
WHERE f1.name <> f2.name
RETURN f1.name, f2.name, f1.semantic, f1.confidence
ORDER BY f1.confidence DESC
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 字段含义 | 看代码注释（如果有的话） | 统一语义描述 + 语义类型 |
| 跨服务一致性 | 各服务自行命名 | `same_semantic_as` 关联 |
| 文档维护 | 手动写 API 文档 | 自动生成语义化 API 文档 |

**预期价值**：减少 30-50% 的"这个字段什么意思"类跨团队沟通，加速新人 onboarding。

---

## 场景 3：合规与隐私影响分析（GDPR/PIPL）

> **一句话**：快速回答"用户的手机号在哪些系统中被处理"这类合规审计问题。

**目标用户**：法务合规团队、DPO（数据保护官）

**具体 Use Case**：
《个人信息保护法》(PIPL) 要求企业能说明个人信息的处理路径。审计人员问："用户手机号从收集到存储经过了哪些系统？"传统方式需要人工追踪代码，耗时数周。

**Cypher 查询**：
```cypher
// 追踪 phone_number 的完整处理路径
MATCH path = (f:Field)-[:passes_to*1..8]->(target:Field)
WHERE f.name = 'PhoneNumber' AND f.sensitivity = 'pii'
WITH path, [node IN nodes(path) | node.name] AS field_chain
MATCH (f2:Field)-[:belongs_to]->(api:API)-[:belongs_to]->(svc:Service)
WHERE f2 IN nodes(path)
RETURN svc.name, api.name, f2.name, f2.semantic
ORDER BY length(path)

// 查找 PII 数据的所有存储终点
MATCH (f:Field {sensitivity: 'pii'})-[:maps_to]->(col:DBColumn)
  -[:belongs_to]->(tbl:DBTable)
RETURN tbl.name, col.name, f.semantic, f.confidence
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 审计响应时间 | 数周（人工追查） | 分钟级（图查询） |
| 完整性 | 依赖开发者记忆 | 代码级全链路追踪 |
| 可审计性 | 无法证明"已全部发现" | 有置信度和覆盖率指标 |

**预期价值**：合规审计响应时间从数周缩短到小时级，降低合规风险罚款概率。

---

## 场景 4：安全风险发现——敏感数据暴露面

> **一句话**：自动发现哪些外部 API 暴露了数据库中的敏感数据，且缺少脱敏或鉴权保护。

**目标用户**：安全团队、SRE

**具体 Use Case**：
安全团队想知道："有哪些外部 API 直接返回了数据库中的 PII 列，且没有做脱敏？"这是数据泄露的高风险点。

**Cypher 查询**：
```cypher
// 发现高风险暴露：PII 数据通过外部 API 返回且无脱敏
MATCH (col:DBColumn {classification_tag: 'PII'})
  <-[:maps_to]-(f:Field {direction: 'response'})
  -[:belongs_to]->(api:API)
  -[:belongs_to]->(svc:Service)
WHERE api.route STARTS WITH '/api/v1/'  // 外部 API
RETURN svc.name, api.route, api.http_method, 
       f.name, f.semantic, col.name AS db_column,
       f.confidence
ORDER BY f.confidence DESC

// 统计各服务的敏感数据暴露数量
MATCH (col:DBColumn)-[:belongs_to]->(tbl:DBTable),
      (col)<-[:maps_to]-(f:Field)-[:belongs_to]->(api:API)
        -[:belongs_to]->(svc:Service)
WHERE col.classification_tag IN ['PII', 'Financial']
RETURN svc.name, count(DISTINCT f) AS exposed_fields, 
       count(DISTINCT api) AS exposed_apis
ORDER BY exposed_fields DESC
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 发现方式 | 渗透测试 + 代码审查（抽查） | 全量自动扫描 |
| 覆盖率 | ~10%（抽查覆盖） | ~85%+ |
| 发现时间 | 事后（数据泄露后） | 事前（代码提交时） |
| 可操作性 | "有风险"的模糊结论 | 精确到 API + 字段 + DB 列 |

**预期价值**：提前发现敏感数据暴露面，单次发现一个 PII 泄露漏洞即可能避免 ¥100 万-1000 万+ 的合规罚款或声誉损失。

---

## 场景 5：架构可视化——服务数据流全景图

> **一句话**：可视化展示数据（尤其是敏感数据）在微服务网络中的流动路径。

**目标用户**：架构师、技术负责人

**具体 Use Case**：
架构师在做系统改造评审时，需要了解"用户注册流程中，用户数据经过了哪些服务"。传统方式只能看服务调用拓扑（谁调用了谁），看不到数据流（哪些数据在流动）。

**Cypher 查询**：
```cypher
// 可视化某个业务流程的数据流全景
MATCH path = (entry:Field)-[:passes_to*1..6]->(sink:Field)
WHERE entry.context CONTAINS '注册'
WITH path, 
     [n IN nodes(path) | n.name] AS fields,
     [n IN nodes(path) | n.sensitivity] AS sensitivities
MATCH (f:Field)-[:belongs_to]->(api:API)-[:belongs_to]->(svc:Service)
WHERE f IN nodes(path)
RETURN DISTINCT svc.name, api.name, f.name, f.sensitivity
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 可见信息 | 服务拓扑（A 调用 B） | **数据流**（phone_number 从 A 流到 B 再到 DB） |
| 敏感标注 | 无 | 每条数据流标注敏感性 |
| 粒度 | 服务级 | 字段级 |

**预期价值**：架构评审从"猜测数据怎么流动"变成"看到数据怎么流动"，评审效率提升 3-5 倍。

---

## 场景 6：变更影响评估

> **一句话**：代码变更前预测"这次改动会影响哪些下游数据流和敏感数据"。

**目标用户**：开发团队、代码审查者

**具体 Use Case**：
开发者修改了 `user_service` 的 `GetUserProfile` 函数，移除了 `phone_number` 字段的脱敏逻辑。变更影响评估系统自动检测到：这个变更会导致 PII 数据通过 3 个下游 API 以明文形式暴露。

**Cypher 查询**：
```cypher
// 查询某函数变更影响的所有下游路径
MATCH (f:Function {name: 'GetUserProfile', service: 'user-service'})
  -[:calls*1..5]->(downstream:Function)
  <-[:belongs_to]-(field:Field {sensitivity: 'pii'})
  -[:belongs_to]->(api:API)
RETURN api.route, field.name, field.semantic, field.sensitivity
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 影响分析 | 人工 code review | 自动图查询 |
| 覆盖范围 | 直接调用者 | 全链路下游（N 跳） |
| CI/CD 集成 | 无 | PR 自动评论风险提示 |

**预期价值**：在 CI/CD 中自动拦截高风险变更，减少 50%+ 的敏感数据事故。

---

## 场景 7：字段标准化与去重

> **一句话**：发现全公司代码中含义相同但命名不同的字段，推动统一命名规范。

**目标用户**：平台架构团队、API 标准化委员会

**具体 Use Case**：
全公司有 47 种不同命名的"用户 ID"字段：`uid`, `user_id`, `userId`, `account_id`, `member_id`, `creator_id`……通过 `same_semantic_as` 关系，自动发现这些语义等价的字段。

**Cypher 查询**：
```cypher
// 发现语义相同但命名不同的字段簇
MATCH (f1:Field)-[r:same_semantic_as]->(f2:Field)
WHERE f1.name <> f2.name AND r.confidence > 0.8
WITH f1.name AS name1, collect(DISTINCT f2.name) AS aliases, count(*) AS cnt
RETURN name1, aliases, cnt
ORDER BY cnt DESC
LIMIT 20

// 统计最常见的语义类型及其命名变体数
MATCH (f:Field)-[:has_type]->(st:SemanticType)
WITH st.name AS semantic_type, count(DISTINCT f.name) AS name_variants, count(f) AS total
RETURN semantic_type, name_variants, total
ORDER BY name_variants DESC
```

**Before vs After**：

| 维度 | 没有 Ontology | 有 Ontology |
|------|-------------|------------|
| 发现方式 | 无法系统性发现 | 自动聚类 |
| 标准化依据 | 主观制定规范 | 数据驱动（哪个命名最常用） |
| 推行难度 | 高（缺乏数据支撑） | 低（有全景数据） |

**预期价值**：为 API 标准化提供数据基础，长期减少跨团队集成的沟通成本。

---

## 场景价值汇总

| # | 场景 | 目标用户 | 核心价值 | 优先级 |
|---|------|---------|---------|--------|
| 1 | 数据分类自动化 | 数据治理 | 覆盖率 30%→90% | 🔴 P0 |
| 2 | API Schema 语义 | 开发 | 减少 30-50% 沟通成本 | 🟡 P1 |
| 3 | 合规隐私分析 | 法务合规 | 审计响应 周→小时 | 🔴 P0 |
| 4 | 安全风险发现 | 安全 | 提前发现 PII 暴露 | 🔴 P0 |
| 5 | 架构可视化 | 架构师 | 评审效率 3-5x | 🟡 P1 |
| 6 | 变更影响评估 | 开发 | 减少 50%+ 数据事故 | 🟠 P0.5 |
| 7 | 字段标准化 | 平台 | API 命名统一 | 🟡 P1 |

**最大卖点**：场景 1+3+4 直接对应合规和安全——这是企业最愿意为之买单的痛点。

---

*最后更新: 2026-03-05*
