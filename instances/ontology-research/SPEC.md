# ontology-research — SPEC

## Background

字节跳动拥有数十万个微服务（Go-Hertz/Go-Kitex/Java/Python），传统数据治理路径（taxonomy → capability → sample detection）依赖强约束（代码规范、主动上报），在大型组织中推行困难。

本项目探索一条全新路径：**利用 LLM 理解源代码语义 + 已有的 Code Graph 调用链，自底向上构建全公司字段级 ontology graph**，替代传统 top-down 数据分类方式。

已有基建：
- **Code Graph**（内部平台）：全公司代码库扫描，提供函数级调用链（API → func → func → DB），可 query
- **二进制产物管理平台**：管理服务部署产物
- **数据库已有标签**：部分 DB table/column 已完成数据分类标注

## Iron Rules

- 知识类产出用**中文**，通俗易懂，多用形象例子
- 代码类产出用英文注释，可执行（Go package / Python script / Shell）
- Tasks must be self-contained (Worker is headless: Bash/Read/Write/Edit/web_search/web_fetch only)
- Each task produces exactly ONE output file
- 不做外部 API 调用（web_search 除外）
- 每个文件控制在 50KB 以内

## Goals

1. **建立 ontology 基础知识体系**（通俗易懂，面向工程师而非学术）
2. **论证技术可行性**：LLM 能否从 Go/Java/Python 代码中提取字段级语义？精度、成本、局限
3. **设计系统架构**：从 Code Graph 到 Ontology Graph 的完整 pipeline
4. **成本估算**：全公司规模（10万+服务）的扫描成本、存储成本、维护成本
5. **落地价值分析**：数据分类、API schema 管理、合规/隐私、风险分析、全景图等
6. **Code Graph 团队合作方案**：如何基于已有基建合作，集成策略
7. **技术 PoC 原型**：小规模可执行代码验证关键假设

## Constraints

- 目标公司：字节跳动（Go-Hertz/Go-Kitex 为主，Java/Python 辅助）
- 服务规模：数十万微服务，部分 monorepo
- 研究深度：理论可行性 + 技术方案 + 原型架构 + 成本估算
- 不需要对接真实内部系统，用模拟数据验证
- LLM 选型：考虑 GPT-4 / Claude / 开源模型（成本对比）

## Phase 0: 基础知识建设

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 0.1 | Ontology 入门：什么是 ontology，和 taxonomy/knowledge graph 的区别 | — | `knowledge/ontology-101.md` |
| 0.2 | 知识图谱技术栈：RDF/OWL/Property Graph/Neo4j，怎么选 | — | `knowledge/kg-tech-stack.md` |
| 0.3 | 代码语义分析 SOTA：LLM 理解代码的能力边界（学术+工业界） | — | `knowledge/llm-code-understanding.md` |
| 0.4 | 数据治理现状：传统方法 vs 新方法，业界案例 | — | `knowledge/data-governance-landscape.md` |
| 0.G | Gate: Phase 0 | 0.1–0.4 | — |

Gate: 所有 knowledge/ 文件存在且 >= 2KB。

## Phase 1: 技术可行性深度分析

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 1.1 | Go-Hertz/Kitex API 语义提取：LLM 能从代码提取什么？（含 prompt 设计） | 0.G | `knowledge/go-api-extraction.md` |
| 1.2 | 字段级 ontology 建模：如何表示 field 的语义、归属、传递关系 | 0.G | `knowledge/field-ontology-model.md` |
| 1.3 | 调用链 → 语义传播：从 Code Graph 数据推导字段语义传递 | 0.G | `knowledge/semantic-propagation.md` |
| 1.4 | DB 标签回溯：已有数据库标签如何通过调用链反向关联到 API 字段 | 0.G | `knowledge/db-label-backtrack.md` |
| 1.5 | LLM 精度与局限：hallucination、多义性、上下文窗口限制、成本 | 0.G | `knowledge/llm-limitations.md` |
| 1.G | Gate: Phase 1 | 1.1–1.5 | — |

Gate: 所有 Phase 1 knowledge/ 文件存在且 >= 3KB。

## Phase 2: 系统架构设计

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 2.1 | 整体架构设计：从代码扫描到 Ontology Graph 的 E2E pipeline | 1.G | `output/architecture.md` |
| 2.2 | Code Graph 合作方案：集成策略、数据接口、合作沟通要点 | 1.G | `output/code-graph-collaboration.md` |
| 2.3 | 存储选型：图数据库选型对比（Neo4j/TigerGraph/内部方案） | 1.G | `output/storage-selection.md` |
| 2.4 | 成本估算模型：LLM 调用成本 × 服务数 × 字段数，分阶段估算 | 1.G | `output/cost-model.md` |
| 2.G | Gate: Phase 2 | 2.1–2.4 | — |

Gate: 所有 Phase 2 output/ 文件存在且 >= 3KB。

## Phase 3: 价值论证与落地路径

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 3.1 | 落地价值全景：数据分类/API管理/合规隐私/风险分析/架构可视化等 | 2.G | `output/value-proposition.md` |
| 3.2 | 与现有方案对比：vs OpenLineage / Data Catalog / 传统DLP | 2.G | `output/comparison.md` |
| 3.3 | 落地路线图：分阶段实施计划（PoC → 试点 → 全量） | 2.G | `output/roadmap.md` |
| 3.G | Gate: Phase 3 | 3.1–3.3 | — |

Gate: 所有 Phase 3 output/ 文件存在且 >= 2KB。

## Phase 4: 技术验证 PoC

4.1 拆为两步避免超时（生成 3 个 Go 微服务 + DB schema 内容量大）。

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 4.1a | 模拟微服务：服务定义与 Thrift IDL | 2.G | `output/poc/mock-services-idl.md` |
| 4.1b | 模拟微服务：Kitex Handler + DB Schema | 4.1a | `output/poc/mock-services-impl.md` |
| 4.2 | LLM 提取 prompt 工程 | 1.1, 4.1b | `output/poc/extraction-prompts.py` |
| 4.3 | 调用链语义传播 PoC | 1.3, 4.1b | `output/poc/propagation.py` |
| 4.4 | 图谱可视化 demo | 2.1, 4.3 | `output/poc/visualize.py` |
| 4.G | Gate: Phase 4 | 4.1a–4.4 | — |

Gate: PoC 代码文件存在，extraction-prompts.py 和 propagation.py >= 2KB。

## Phase 5: 最终综合报告

拆为两步避免超时（综合报告需 ≥10KB，要读取所有前序产物）。

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 5.1a | 执行摘要与核心发现 | 3.G, 4.G | `output/final-report-part1.md` |
| 5.1b | 技术方案与落地计划 | 5.1a | `output/final-report-part2.md` |
| 5.G | Gate: Final | 5.1a, 5.1b | — |

Gate: part1 + part2 合计 >= 10KB。

## Phase 6: 飞书文档同步

研究完成后，将所有 .md 研究产物上传为飞书文档（PoC 代码除外），统一放在一个飞书文件夹中。

| ID | Title | Depends On | Output |
|----|-------|------------|--------|
| 6.1 | 上传到飞书文档 | 5.G | `output/feishu-index.md` |
| 6.G | Gate: 飞书完成 | 6.1 | — |

Gate: feishu-index.md 存在且包含飞书文档链接。

## Output Structure

```
knowledge/
├── ontology-101.md              # Ontology 入门
├── kg-tech-stack.md             # 知识图谱技术栈
├── llm-code-understanding.md    # LLM 代码理解能力
├── data-governance-landscape.md # 数据治理现状
├── go-api-extraction.md         # Go API 语义提取
├── field-ontology-model.md      # 字段级 ontology 建模
├── semantic-propagation.md      # 调用链语义传播
├── db-label-backtrack.md        # DB 标签回溯
└── llm-limitations.md           # LLM 局限性分析
output/
├── architecture.md              # 系统架构
├── code-graph-collaboration.md  # Code Graph 合作方案
├── storage-selection.md         # 存储选型
├── cost-model.md                # 成本估算
├── value-proposition.md         # 价值全景
├── comparison.md                # 方案对比
├── roadmap.md                   # 落地路线图
├── final-report-part1.md        # 综合报告（上）
├── final-report-part2.md        # 综合报告（下）
├── feishu-index.md              # 飞书文档索引
└── poc/
    ├── mock-services-idl.md     # 模拟微服务 IDL
    ├── mock-services-impl.md    # 模拟微服务实现
    ├── extraction-prompts.py    # LLM 提取 prompt
    ├── propagation.py           # 语义传播算法
    └── visualize.py             # 图谱可视化
```
