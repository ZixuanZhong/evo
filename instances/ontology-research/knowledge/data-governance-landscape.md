# 数据治理现状：传统方法 vs 新方法，业界案例

> 本文面向后端工程师，系统梳理数据治理的传统路径、业界最佳实践、数据血缘工具，以及 LLM 带来的新范式。

---

## 1. 传统数据治理路径：Taxonomy → Capability → Sample Detection

### 1.1 传统流程

大多数公司的数据治理遵循**自顶向下（Top-Down）**路径：

```
第一步：定义分类体系（Taxonomy）
  ↓ 安全/合规团队制定数据分类标准（公开/内部/机密/绝密；PII/财务/健康…）
第二步：建设检测能力（Capability）
  ↓ 开发正则匹配、关键词匹配、采样检测工具
第三步：采样检测（Sample Detection）
  ↓ 对数据库/数仓做采样扫描，匹配手机号/身份证号等已知模式
第四步：标注与治理
  ↓ 发现的敏感数据打标签 → 推动整改
```

**比喻**：像城管先定义"什么是违建"，再派人挨家挨户检查。10 万栋楼（10 万微服务）每天都在改建（每天数千代码提交），人力驱动根本跟不上。

### 1.2 核心痛点

| 痛点 | 具体表现 | 在字节的严重程度 |
|------|---------|----------------|
| **依赖人工定义** | 分类标准需安全专家维护，更新滞后 | ⭐⭐⭐⭐ 业务迭代快 |
| **只看数据层** | 只扫描 DB/数仓，不管 API 和代码层 | ⭐⭐⭐⭐⭐ 数十万 API 是盲区 |
| **模式匹配有限** | 正则只能匹配已知格式（手机号、邮箱） | ⭐⭐⭐⭐ 语义类数据无法识别 |
| **覆盖率低** | 采样≠全量，总有遗漏 | ⭐⭐⭐⭐ 10 万+ 服务，覆盖率 < 30% |
| **依赖主动上报** | 需要业务方主动注册打标签 | ⭐⭐⭐⭐⭐ 工程师不愿做"额外工作" |
| **无语义理解** | 不理解字段含义，只看格式 | ⭐⭐⭐⭐⭐ user_id vs anchor_id 分不清 |
| **无传播追踪** | 不知道敏感数据从哪来到哪去 | ⭐⭐⭐⭐⭐ 泄露路径不可见 |

### 1.3 传统方法的隐含假设——为什么在大公司失效

1. **假设有完善代码规范**：现实是数十万服务注释和文档严重滞后
2. **假设业务方愿意配合**：现实是工程师视数据标注为"额外负担"。AWS 白皮书也指出 over-classification 增加成本、under-classification 留下隐患
3. **假设数据流经有限路径**：现实是微服务架构下数据通过 RPC/HTTP/MQ/Cache 多种路径流转，一个 user_id 可能经过 50 个服务
4. **假设变更频率低**：现实是每天数千代码提交，数据流随时在变

**结论：传统方法本质是"静态检查"，面对微服务时代的"动态数据流"力不从心。**

---

## 2. 业界案例：大厂怎么做数据治理

### 2.1 Google Dataplex Universal Catalog

**来源**: [cloud.google.com/dataplex](https://cloud.google.com/dataplex)

2022 年将 Data Catalog 和 Dataplex 统一为 Dataplex Universal Catalog。

**核心能力**：统一元数据管理（跨 BigQuery/GCS/Dataproc）、数据质量检查、数据血缘、数据画像（Profiling）、业务词汇表（Business Glossary）、数据产品（2025 新增）。

**特点**：集成到 BigQuery 中提供"上下文治理"。

**启示**：Business Glossary 和我们的 ontology 思路相似——统一术语定义。但 Dataplex **只覆盖数据层**（BigQuery/GCS），不覆盖代码层和 API 层。

### 2.2 Meta Privacy Aware Infrastructure (PAI) ⭐ 最相关案例

**来源**: [engineering.fb.com/2024/08/27/security/privacy-aware-infrastructure-purpose-limitation-meta/](https://engineering.fb.com/2024/08/27/security/privacy-aware-infrastructure-purpose-limitation-meta/)

Meta 在 2024 年公开了 PAI 项目——和我们方向**最接近**的业界案例。

**核心思路**：传统"事后审计"跟不上数千微服务。采用**信息流控制（IFC）**模型：

1. **Policy Zones**：不只检查数据访问权限，而是**控制数据在系统间的处理和传递方式**——实时控制而非事后审计
2. **代码扫描**：通过静态代码分析检测个人数据流
3. **基础设施嵌入**：隐私规则直接嵌入基础设施代码，自动遵守
4. **数据血缘**：2025 年扩展到 GenAI 场景（[engineering.fb.com/2025/10/23/security/scaling-privacy-infrastructure-for-genai-product-innovation/](https://engineering.fb.com/2025/10/23/security/scaling-privacy-infrastructure-for-genai-product-innovation/)）

**Privado.ai 的分析**：
> "只有监控所有代码如何处理个人数据，Meta 才能实现完整的实时隐私治理。"

**对我们的意义**：
- Meta 方向和我们一致——从代码层理解数据流
- 他们用传统静态分析（Policy Zones），我们用 **LLM + Code Graph** 做更深语义理解
- PAI 支持数千微服务、多种语言——证明代码级数据治理在大规模下可行
- 我们额外的优势：提取**字段级语义**构建 ontology graph

### 2.3 LinkedIn DataHub

**来源**: [github.com/datahub-project/datahub](https://github.com/datahub-project/datahub), [docs.datahub.com](https://docs.datahub.com)

业界最活跃的开源元数据平台。

**核心能力**：数据发现与搜索、列级血缘追踪、数据观测与质量监控、80+ 连接器（Kafka/Hive/MySQL/Snowflake…）、联邦式元数据服务、实时流式更新（秒级）、2025 年加入 AI Agent（MCP 协议）和 LLM 集成。

**规模**：LinkedIn 内部验证，可扩展到 **1000 万+ 数据资产**。

**启示**：DataHub 管理的是**数据资产**（表/列/ETL 任务），不覆盖**代码资产**（API/函数/struct）。我们的 ontology graph 可以作为 DataHub 的**上游数据源**——把代码层语义信息推送进去。

### 2.4 Uber Databook

**来源**: [uber.com/blog/databook](https://www.uber.com/blog/databook/) (2018), [uber.com/blog/metadata-insights-databook](https://www.uber.com/blog/metadata-insights-databook/) (2020)

Uber 最早的大规模数据发现平台。

**演进**：V1 (~2016) 基础搜索 → V2 (2018) 多存储元数据采集 + RESTful API → V3 (2020) 日志导向架构（log-oriented），支持增量更新和搜索索引重建。

**启示**：证明大规模自动化元数据采集可行，但同样只覆盖数据存储层。

### 2.5 Grab：LLM 驱动的数据分类 ⭐ 工业验证

**来源**: [engineering.grab.com/llm-powered-data-classification](https://engineering.grab.com/llm-powered-data-classification)

东南亚超级应用 Grab 公开了 **LLM 驱动的数据分类方案**——和我们最接近的工业实践。

**背景**：之前用正则分类器做数据分类，精度低、误报多、维护成本高。

**LLM 方案**：用 LLM 扫描数据实体，自动生成列/字段级分类标签，经人工审核。治理团队提供分类规则，LLM 负责理解和应用。

**启示**：验证了 LLM 做字段级数据分类的工业可行性。但 Grab 只用 LLM 看数据内容（更聪明的正则），我们是看**代码**——更深入，不只分类还有语义理解和传播追踪。

### 2.6 Ethyca：LLM 元数据分类器

**来源**: [ethyca.com/news/engineering-llm-data-classifier-metadata-only](https://www.ethyca.com/news/engineering-llm-data-classifier-metadata-only)

**核心思路**：只用**元数据**（列名/表名/schema）而非实际数据内容做分类。LLM 理解列名语义（`phone_number` → PII-电话号码）。

**启示**：证明"只看 metadata 不看数据内容"也能分类——我们看代码结构而非运行时数据，本质一样。

---

## 3. 数据血缘（Data Lineage）工具

### 3.1 OpenLineage + Marquez

**来源**: [openlineage.io](https://openlineage.io), [marquezproject.ai](https://marquezproject.ai)

OpenLineage 是**开放标准**（不是工具），定义血缘元数据采集规范。核心概念：Run（一次执行）、Job（处理任务）、Dataset（数据集）。支持 Airflow/Spark/Flink/dbt/Dagster。

Marquez 是 OpenLineage 的**参考实现**（HTTP API + PostgreSQL + Web UI）。

**局限**：只追踪数据 Pipeline 之间的血缘，**不追踪代码内部数据流**，不覆盖 API 层和微服务层。

### 3.2 Apache Atlas

Hadoop 生态的数据治理框架。支持 Hive/HBase/Kafka/Storm，但**重度绑定 Hadoop 生态**、架构较重、社区活跃度下降（被 DataHub 超越）。

### 3.3 Privado（新兴工具，值得关注）

**来源**: [github.com/Privado-Inc/privado](https://github.com/Privado-Inc/privado)

**开源静态代码分析工具**，专门检测代码中的数据流。从代码中检测 110+ 种个人数据元素，追踪数据从采集到 sink（第三方 API/数据库）的流动。支持 Java/JavaScript/Python/Ruby/Go。

**对我们的启示**：Privado 是目前最接近的现有工具，但用**传统静态分析**（AST + 模式匹配），不用 LLM。只检测已知模式（手机号/邮箱），不能理解业务语义。我们的优势：LLM 理解 `anchor_id` 是"主播 ID"，Privado 做不到。

### 3.4 工具对比

| 工具 | 覆盖层 | 血缘粒度 | 语义理解 | 代码分析 | 开源 |
|------|--------|---------|---------|---------|------|
| OpenLineage/Marquez | 数据 Pipeline | 作业→数据集 | ❌ | ❌ | ✅ |
| Apache Atlas | Hadoop 生态 | 表/列级 | ❌ | ❌ | ✅ |
| DataHub | 多数据源 | 列级 | ❌ (开始加 LLM) | ❌ | ✅ |
| Google Dataplex | Google Cloud | 列级 | 有限 | ❌ | ❌ |
| Privado | 代码层 | 字段级 | ❌（模式匹配） | ✅（静态分析） | ✅ |
| **我们的方案** | **代码+数据层** | **字段级** | **✅（LLM）** | **✅（LLM+Code Graph）** | — |

---

## 4. 传统方法 vs LLM 方法：核心差异

| 维度 | 传统方法（Top-Down） | LLM 方法（Bottom-Up） |
|------|---------------------|----------------------|
| **起点** | 安全团队定义分类标准 | 从代码自动发现字段语义 |
| **方向** | 顶层标准 → 检测 → 扫描 | 代码分析 → 语义提取 → 自动分类 |
| **覆盖范围** | 数据存储层 | API → 函数 → DB 全链路 |
| **依赖** | 代码规范 + 主动上报 + 人工审核 | Code Graph + LLM，不依赖人工 |
| **语义理解** | 正则/关键词匹配 | LLM 理解命名和上下文语义 |
| **维护成本** | 规则库持续人工更新 | 模型自带泛化能力 |
| **实时性** | 定期扫描（天/周级） | 可与 CI/CD 集成（提交级） |
| **规模化能力** | 差（人力线性增长） | 好（LLM 并行处理） |

**比喻**：传统方法 = "城管检查"（派人挨家查）；LLM 方法 = "卫星遥感"（从代码层面扫描全城，不确定的再实地检查）。

---

## 5. LLM-based 新方法的机会

### 5.1 为什么现在是好时机？

1. **LLM 代码理解成熟**：SWE-bench 70%+ 通过率
2. **Code Graph 基建已有**：字节已有全公司级代码调用链数据
3. **DB 标签存量可用**：部分数据库标签可作"种子标签"反向传播
4. **合规压力增大**：GDPR/个保法要求越来越高
5. **成本可控**：开源模型（DeepSeek-Coder/Qwen2.5-Coder）成本已降到可接受范围

### 5.2 LLM 方法解决的独特问题

| 场景 | 传统方法 | LLM 方法 |
|------|---------|---------|
| `anchor_level` 是什么？ | ❌ 不匹配已知模式 | ✅ "主播等级，业务分级标识" |
| `room_id` 从 API 到 DB 经过几个服务？ | ❌ 看不到代码层 | ✅ Code Graph + 语义传播 |
| 新 API 字段自动分类 | ❌ 等下次扫描+人工 | ✅ CI/CD 集成，提交时自动 |
| 字段改名（`uid` → `user_id`） | ❌ 被当新字段 | ✅ LLM 判断语义等价 |
| DB 列被哪些 API 暴露？ | ❌ 无代码血缘 | ✅ 反向传播追踪 |

### 5.3 新范式：Code-First Data Governance

```
传统：  Data → Schema → Classification → Governance（人工定义）
新：    Code → LLM 语义提取 → Ontology Graph → Governance（自动生成）
              + Code Graph
```

**核心理念**：代码是唯一事实来源（Single Source of Truth）；自底向上不需预定义完整分类；图谱驱动而非孤立标签；持续随代码变更自动更新。

### 5.4 定位差异

```
                    语义理解深度
                    ↑
                    |  🔵 我们的方案（LLM + Code Graph + Ontology）
                    |
                    |        🟢 Meta PAI（代码静态分析 + IFC）
                    |
                    |  🟡 Privado（代码静态分析）
                    |
                    |           🟠 DataHub + LLM（元数据 + LLM）
                    |
                    |  🔴 传统 DLP（正则 + 采样）
                    +————————————————————————→ 覆盖范围
                    DB 层        API 层       全链路
```

---

## 6. 核心结论

### 6.1 传统方法的天花板

覆盖率不够（只看数据层）、语义不够（只匹配模式）、跟不上（变更太快）、推不动（依赖主动上报）。

### 6.2 LLM + Code Graph 的独特优势

1. **不依赖主动上报**：从代码自动提取
2. **语义级理解**：LLM 理解业务含义
3. **全链路覆盖**：API → 函数 → DB
4. **可利用存量**：已有 DB 标签 + Code Graph
5. **持续演进**：可与 CI/CD 集成

### 6.3 注意事项

- 不是替代现有方案，是**增强**——DB 标签和 DLP 继续保留
- 人工审核不可少——LLM 有幻觉风险
- 渐进式推进——先 PoC 再扩大
- **Meta PAI 是最好参照**——证明代码级治理大规模可行，我们在此基础上加 LLM 语义

---

## 7. 关键参考资源

| 公司/工具 | 定位 | 链接 |
|-----------|------|------|
| Google Dataplex | 统一数据目录 | [cloud.google.com/dataplex](https://cloud.google.com/dataplex) |
| Meta PAI | 代码级隐私治理 | [engineering.fb.com](https://engineering.fb.com/2024/08/27/security/privacy-aware-infrastructure-purpose-limitation-meta/) |
| LinkedIn DataHub | 开源元数据平台 | [github.com/datahub-project/datahub](https://github.com/datahub-project/datahub) |
| Uber Databook | 数据发现平台 | [uber.com/blog/databook](https://www.uber.com/blog/databook/) |
| Grab LLM 分类 | LLM 数据分类 | [engineering.grab.com](https://engineering.grab.com/llm-powered-data-classification) |
| Ethyca | LLM 元数据分类 | [ethyca.com](https://www.ethyca.com/news/engineering-llm-data-classifier-metadata-only) |
| OpenLineage | 血缘开放标准 | [openlineage.io](https://openlineage.io) |
| Marquez | OpenLineage 实现 | [marquezproject.ai](https://marquezproject.ai) |
| Privado | 代码数据流检测 | [github.com/Privado-Inc/privado](https://github.com/Privado-Inc/privado) |

---

*最后更新: 2026-03-05*
*数据来源: 各公司技术博客、开源项目文档、web_search 搜索结果*
