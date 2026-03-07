# 字段级 Ontology Graph 研究报告（下）

# 技术方案与落地计划

> 接续上半部分（执行摘要与核心发现），本部分深入技术架构、协同方案、风险分析和落地路线图。

---

## 7. 技术架构详解

> **TL;DR**：5 层 pipeline 处理从代码到图谱的完整链路。批量模式处理全量扫描，增量模式处理每日变更。关键设计点是"AST 先行，LLM 兜底"。

### 7.1 Layer 1 — 数据采集层

| 数据源 | 采集方式 | 频率 | 内容 |
|--------|---------|------|------|
| Git 仓库 | Git clone / webhook | 实时（增量）| Thrift IDL、Go handler、GORM model |
| Code Graph | REST API + Kafka | 实时推送 | 函数调用链、跨服务依赖 |
| 已有 DB 标签 | 批量导入 | 每周 | 存量数据分类标注 |
| 二进制管理平台 | API 查询 | 按需 | 服务 → 仓库映射 |

### 7.2 Layer 2 — 预处理层

**核心理念：能用 AST 确定性解析的，绝不用 LLM。**

AST 预处理的产出（零成本，100% 精度）：
- Thrift IDL → struct 定义、字段类型、required/optional、注释
- Go AST → handler 函数签名、struct 字段、import 路径、GORM tag
- 调用关系 → `rpc.XXXClient.Method()` 的静态提取

这一步将 LLM 需要处理的"未知"信息减少 **60-70%**。

### 7.3 Layer 3 — LLM 语义提取层

**分层调用策略**：

```
输入字段 → 简单判断（名称/类型/注释匹配规则库）
  ├─ 命中规则 → 直接标注（不调 LLM），占 ~35%
  ├─ 低复杂度 → 小模型 GPT-4o-mini ($0.15/M)，占 ~55%
  └─ 高复杂度 → 大模型 GPT-4o ($2.50/M)，占 ~10%
```

**Prompt 设计要点**：
- System Prompt 定义输出 JSON Schema（强制格式化）
- One-Shot 示例保证格式一致性（+800 token，但值得）
- 字段语义描述强制用中文
- 敏感性分类 4 档：none / pii / financial / internal_id

### 7.4 Layer 4 — 语义传播层

**四种字段映射类型**：

| 类型 | 置信度衰减 | 示例 |
|------|-----------|------|
| Pass-Through | 0% | `req.UserID → dal.UserID` |
| Transform | 15% | `price × count → totalAmount` |
| Aggregate | 25% | `firstName + lastName → fullName` |
| Fan-Out | 20% | `address → province, city, zip` |

**传播算法**：
- 正向 BFS：从 API 入口字段沿调用链向下游传播
- 反向 BFS：从已标注 DB 列向上游 API 字段回溯
- 多路径合并：Noisy-OR 公式 `P = 1 - ∏(1 - p_i)`
- 阈值控制：CONFIDENCE_THRESHOLD=0.3，MAX_HOPS=10

### 7.5 Layer 5 — 图存储与查询层

图谱以 Property Graph 模型存储：
- **7 种节点类型**：Service, API, Function, Field, SemanticType, DBTable, DBColumn
- **8 种边类型**：belongs_to, passes_to, maps_to, has_type, same_semantic_as, calls, reads_from, writes_to
- **预估规模**：~3700 万节点，~1.27 亿条边，~34.6GB 原始存储

查询层提供 Cypher 接口 + REST API Gateway，支持常见查询模板化。

---

## 8. Code Graph 协同方案

> **TL;DR**：分 3 阶段接入 Code Graph（API 试点 → 增量推送 → 全量稳定），同时保留 Go AST 降级方案。

### 8.1 Code Graph 提供什么

| 数据类型 | 优先级 | 用途 |
|----------|--------|------|
| 函数调用链 | P0 | 跨服务字段传播的骨架 |
| Import/依赖关系 | P0 | 补全 LLM 上下文 |
| 代码变更事件 | P1 | 触发增量更新 |
| 类型继承关系 | P1 | Struct 嵌套解析 |
| 代码仓库元信息 | P2 | 服务 → 仓库映射 |

### 8.2 接口设计

6 个核心 API 接口：

1. `GET /api/v1/callgraph/{function}` — 查询函数调用链
2. `GET /api/v1/function/{id}/fields` — 查询函数的字段信息
3. `GET /api/v1/service/{name}/apis` — 查询服务的所有 API
4. `GET /api/v1/dependency/{service}` — 查询服务依赖
5. `POST /api/v1/batch/callgraphs` — 批量查询调用链
6. Kafka topic `code_graph.changes` — 增量变更推送

### 8.3 集成时间线

| 阶段 | 时间 | 内容 |
|------|------|------|
| Phase 1 PoC | M1-M2 | 初步沟通，了解 API 能力，5 个服务试调 |
| Phase 2 试点 | M3-M6 | REST API 正式接入 + Kafka 增量推送 |
| Phase 3 全量 | M7+ | 全量 API 稳定运行 |

### 8.4 降级方案

如果 Code Graph 不可用或延迟：
- **Go AST 自建**：用 `go/callgraph` + `go/ssa` 分析调用关系
- 覆盖率从 ~90% 降至 60-70%
- 主要丢失跨仓库调用链（同仓库内 AST 可解析）

---

## 9. 存储选型与迁移路径

> **TL;DR**：3 阶段迁移——Neo4j Community (PoC) → NebulaGraph (试点) → ByteGraph (全量)。GraphStore 抽象层保证无缝切换。

### 9.1 选型对比（Top 3）

| 维度 | Neo4j | NebulaGraph | ByteGraph |
|------|-------|-------------|-----------|
| 许可 | Community 免费 | 开源免费 | 内部免费 |
| 规模上限 | ~1 亿边 | ~千亿边 | ~5500 亿边 |
| 查询语言 | Cypher ✅ | nGQL (类 Cypher) | Gremlin |
| 运维复杂度 | 低 | 中 | 低（内部托管） |
| PoC 适用性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐（需申请） |
| 生产适用性 | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### 9.2 迁移策略

```
Phase 1 (PoC):     Neo4j Community Docker
                    → 快速验证，单机，免配置

Phase 2 (试点):    NebulaGraph 3 节点集群
                    → 100 服务规模，分布式验证

Phase 3 (全量):    ByteGraph（字节内部图数据库）
                    → 零许可费，275B→550B 边验证（VLDB 2022）
                    → 运维由基础架构团队接管
```

**GraphStore 抽象层**：通过 Adapter 模式封装图数据库操作，迁移时只需实现新 Adapter，上层代码零修改。

---

## 10. 风险与缓解

> **TL;DR**：7 大风险，最严重的是"LLM 幻觉"和"方案未经生产验证"。4 层缓解架构将精度提升到 92-97%。

### 10.1 风险矩阵

| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|------|------|------|---------|
| 1 | **LLM 幻觉（瞎编语义）** | 中 | 🔴高 | 4 层验证：AST → LLM → 交叉验证 → 人工审核 |
| 2 | **方案未经生产验证** | — | 🔴高 | 分阶段推进，每阶段有 Go/No-Go 决策点 |
| 3 | **上下文窗口不够** | 中 | 🟠中 | 分层注入（AST 预提取 + 按需补全） |
| 4 | **LLM 非确定性** | 高 | 🟠中 | temperature=0.1 + 多次调用取共识 |
| 5 | **Code Graph 依赖** | 中 | 🟠中 | Go AST 降级方案（60-70% 覆盖） |
| 6 | **LLM 成本波动** | 低 | 🟢低 | 趋势持续降价；可迁移自部署模型 |
| 7 | **语言/框架差异** | 中 | 🟡中 | Go 优先（字节主力），Python/Java 后续 |

### 10.2 四层精度保障架构

```
Layer 1: AST 确定性解析 → 精度 100%，覆盖 ~35% 字段
Layer 2: LLM 语义分析   → 精度 85-90%，覆盖剩余 ~65%
Layer 3: 交叉验证       → 多 LLM 共识 + DB 标签回溯校验
Layer 4: 人工审核       → 高敏感字段（PII）强制人工确认
```

**综合精度**：92-97%（含人工审核兜底），高于传统人工标注（容易过时和遗漏）。

### 10.3 已知学术参考

- **LLMDFA** (Wang et al., NeurIPS 2024)：LLM 做数据流分析，source/sink 提取精度 100%，路径可达性 87-91%。验证了 LLM 用于代码语义分析的可行性。([arxiv.org/abs/2402.10754](https://arxiv.org/abs/2402.10754))
- **CodeHalu** (Tian et al., AAAI 2025)：所有 17 个测试 LLM 均存在代码幻觉。说明纯 LLM 方案不可靠，必须有 AST 兜底。([arxiv.org/abs/2405.00253](https://arxiv.org/abs/2405.00253))
- **ByteGraph** (Li et al., VLDB 2022)：字节内部图数据库，支持 550B 边，3.49x 服务器实现 ~3x 吞吐。([dl.acm.org/doi/10.14778/3554821.3554824](https://dl.acm.org/doi/10.14778/3554821.3554824))

---

## 11. 分阶段落地路线图

> **TL;DR**：3 阶段 12 个月——PoC (2月, 5 服务) → 试点 (4月, 100 服务) → 全量 (6月, 10 万服务)。每阶段结束有 Go/No-Go 决策点。

### 11.1 总览

```
M1──M2──M3──M4──M5──M6──M7──M8──M9──M10──M11──M12
├────────┤                                         Phase 1: PoC
    ▲     ├──────────────────┤                     Phase 2: 试点
Go/No-Go 1                   ▲                     
                         Go/No-Go 2  ├─────────────┤ Phase 3: 全量
                                                    ▲
                                                Go/No-Go 3
```

### 11.2 Go/No-Go 决策标准

| 阶段 | 关键指标 | 通过阈值 |
|------|---------|---------|
| Phase 1 → 2 | 字段语义提取精度 | ≥ 80% |
| Phase 1 → 2 | 端到端 pipeline 可运行 | 5 个服务跑通 |
| Phase 2 → 3 | 提取精度（100 服务） | ≥ 85% |
| Phase 2 → 3 | PII 暴露面发现 | ≥ 10 个真实高风险点 |
| Phase 2 → 3 | 增量更新延迟 | < 10 分钟 |
| Phase 3 完成 | 服务覆盖率 | ≥ 80% |
| Phase 3 完成 | 下游使用团队 | ≥ 3 个 |

### 11.3 资源需求

| 阶段 | 人力 | 基础设施 | LLM | 总计 |
|------|------|---------|-----|------|
| Phase 1 (2月) | 2.5 人 | 1 台开发机 | $50 | ~$43K |
| Phase 2 (4月) | 5.5 人 | 3 节点集群 | $200 | ~$101K |
| Phase 3 (6月) | 4.5 人 | ByteGraph | $5.7K | ~$170K |

### 11.4 团队协调

| 团队 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|
| Code Graph | 初步沟通 | API 试点接入 | 全量 + 增量 |
| 安全 | 介绍方案 | PII 报告反馈 | 正式集成 |
| 合规 | 介绍场景 | 审计报告试点 | 合规系统集成 |
| 基础架构 | — | — | ByteGraph 资源 |

---

## 12. 下一步行动建议

> **TL;DR**：5 个具体 action items，第一步是"2 周内组建 PoC 团队"。

### 立即行动（本月）

| # | Action Item | Owner | 时间 |
|---|-------------|-------|------|
| 1 | **组建 PoC 团队**：2 后端 + 1 算法（兼职） | TL | 2 周内 |
| 2 | **选择 5 个 PoC 服务**：从直播业务线选有 Thrift IDL + GORM 的典型服务 | TL + 业务 | 1 周内 |
| 3 | **申请 Code Graph API 权限**：联系 Code Graph 团队，获取 5 个服务的试用权限 | 工程师 | 2 周内 |
| 4 | **搭建 Neo4j 开发环境**：Docker Compose 一键部署 | 工程师 | 1 天 |
| 5 | **启动 PoC Sprint**：目标是 M2 结束前产出精度评估报告 | TL | M1 第 3 周 |

### Phase 1 结束时的产出

- [ ] 5 个服务的完整 ontology graph（Neo4j 中）
- [ ] 字段语义提取精度报告（vs 人工标注 ground truth）
- [ ] 可视化 demo（给 VP 汇报用）
- [ ] Go/No-Go 决策文档

---

## 13. 附录：参考文献

| 编号 | 参考 | 来源 |
|------|------|------|
| [1] | Wang et al., "LLMDFA: Analyzing Dataflow in Code with Large Language Models", NeurIPS 2024 | [arxiv.org/abs/2402.10754](https://arxiv.org/abs/2402.10754) |
| [2] | Tian et al., "CodeHalu: Code Hallucinations in LLMs", AAAI 2025 | [arxiv.org/abs/2405.00253](https://arxiv.org/abs/2405.00253) |
| [3] | Li et al., "ByteGraph: A High-Performance Distributed Graph Database in ByteDance", VLDB 2022 | [dl.acm.org/doi/10.14778/3554821.3554824](https://dl.acm.org/doi/10.14778/3554821.3554824) |
| [4] | Ding et al., "CrossCodeEval: A Diverse and Multilingual Benchmark for Cross-File Code Completion", NeurIPS 2023 | [arxiv.org/abs/2310.11248](https://arxiv.org/abs/2310.11248) |
| [5] | "Library Hallucinations in LLMs", 2025 | [arxiv.org/pdf/2509.22202](https://arxiv.org/pdf/2509.22202) |
| [6] | Semgrep Dataflow Analysis | [semgrep.dev/docs/writing-rules/data-flow](https://semgrep.dev/docs/writing-rules/data-flow/data-flow-overview) |
| [7] | CloudWeGo Kitex | [github.com/cloudwego/kitex](https://github.com/cloudwego/kitex) |
| [8] | CloudWeGo Hertz | [github.com/cloudwego/hertz](https://github.com/cloudwego/hertz) |
| [9] | OpenLineage Column-Level Lineage | [openlineage.io](https://openlineage.io/docs/integrations/spark/spark_column_lineage/) |
| [10] | Collibra Pricing Analysis | [atlan.com/collibra/pricing](https://atlan.com/collibra/pricing/) |
| [11] | Open-Source Data Governance Frameworks (2025) | [thedataguy.pro](https://thedataguy.pro/blog/2025/08/open-source-data-governance-frameworks/) |

---

*本文为研究报告下半部分。完整报告请同时阅读 final-report-part1.md（执行摘要与核心发现）。*

*最后更新: 2026-03-05*
