# 📖 Ontology Research 阅读指南

> 25 个文件，~300KB 文字 + PoC 代码。本指南帮你用最短时间获取最大信息量。

---

## ⏱ 按时间预算选择路径

### 🚀 15 分钟：只看结论
1. **`output/final-report-part1.md`** (9KB) — 执行摘要、核心发现、ROI 分析
2. **`output/roadmap.md`** (12KB) — 分阶段落地计划，直接可用于立项

### 🏃 1 小时：理解全貌
在 15 分钟路径基础上，加：
3. **`output/architecture.md`** (26KB) — E2E pipeline 架构，最重要的技术文档
4. **`output/cost-model.md`** (12KB) — 全公司规模成本估算
5. **`output/code-graph-collaboration.md`** (16KB) — 跟 Code Graph 团队怎么合作

### 📚 半天：深入技术细节
在 1 小时路径基础上，加：
6. **`knowledge/go-api-extraction.md`** (19KB) — LLM 从 Go-Kitex 代码提取语义的具体方案
7. **`knowledge/semantic-propagation.md`** (23KB) — 调用链语义传播算法（核心创新点）
8. **`knowledge/field-ontology-model.md`** (18KB) — 字段级 ontology 的 schema 设计
9. **`output/final-report-part2.md`** (12KB) — 技术方案、风险、参考文献

### 🔬 完整阅读：全部消化
按下面「推荐阅读顺序」从头到尾读。

---

## 📋 推荐阅读顺序

研究产物分三层，建议**自上而下**读：

### 第一层：决策层（给老板/总监看）

| # | 文件 | 大小 | 核心内容 |
|---|------|------|----------|
| 1 | `output/final-report-part1.md` | 9KB | 执行摘要、问题定义、方案概述、6 大创新点、7 个落地场景、ROI |
| 2 | `output/roadmap.md` | 12KB | PoC→试点→规模化 三阶段路线图，资源需求，里程碑 |
| 3 | `output/value-proposition.md` | 11KB | 7 个落地价值场景详解 |
| 4 | `output/comparison.md` | 10KB | 与 OpenLineage/DataHub/Atlas/DLP 等 5 类方案对比 |

### 第二层：架构层（给技术 lead 看）

| # | 文件 | 大小 | 核心内容 |
|---|------|------|----------|
| 5 | `output/architecture.md` | 26KB | **最重要** — 5 层 pipeline 设计、数据流、组件交互 |
| 6 | `output/code-graph-collaboration.md` | 16KB | 与 Code Graph 团队的 API 接口设计、合作模式 |
| 7 | `output/storage-selection.md` | 13KB | Neo4j/TigerGraph/NebulaGraph/ByteGraph 选型对比 |
| 8 | `output/cost-model.md` | 12KB | LLM 调用成本 × 服务规模，分阶段估算 |
| 9 | `output/final-report-part2.md` | 12KB | 风险分析、缓解措施、技术细节补充 |

### 第三层：知识层（给实现工程师看）

按依赖关系排序，每篇都自成体系：

| # | 文件 | 大小 | 你会学到 |
|---|------|------|----------|
| 10 | `knowledge/ontology-101.md` | 15KB | Ontology 是什么，和 taxonomy/KG 的区别（入门必读） |
| 11 | `knowledge/kg-tech-stack.md` | 14KB | RDF/OWL/Property Graph 技术栈选型 |
| 12 | `knowledge/llm-code-understanding.md` | 16KB | LLM 理解代码的能力边界（学术+工业） |
| 13 | `knowledge/data-governance-landscape.md` | 15KB | 数据治理行业现状，6 家公司案例 |
| 14 | `knowledge/go-api-extraction.md` | 19KB | Go-Hertz/Kitex 代码结构 + LLM 提取 prompt 设计 |
| 15 | `knowledge/field-ontology-model.md` | 18KB | 字段级 ontology schema（YAML 定义，可直接用） |
| 16 | `knowledge/semantic-propagation.md` | 23KB | **核心算法** — 调用链语义传播、置信度、冲突解决 |
| 17 | `knowledge/db-label-backtrack.md` | 24KB | 已有 DB 标签反向关联到 API 字段 |
| 18 | `knowledge/llm-limitations.md` | 18KB | LLM hallucination、成本、上下文窗口限制 |

### 第四层：PoC 代码（想动手验证的）

| # | 文件 | 大小 | 说明 |
|---|------|------|------|
| 19 | `output/poc/mock-services-idl.md` | 10KB | 3 个模拟 Go 微服务的 Thrift IDL |
| 20 | `output/poc/mock-services-impl.md` | 18KB | Kitex Handler 实现 + MySQL Schema |
| 21 | `output/poc/extraction-prompts.py` | 26KB | LLM 提取 prompt 工程（可执行 Python） |
| 22 | `output/poc/propagation.py` | 21KB | 语义传播算法 PoC（可执行 Python） |
| 23 | `output/poc/visualize.py` | 16KB | 图谱可视化（生成 HTML/PNG） |
| 24 | `output/poc/ontology_graph.png` | 493KB | 可视化输出样例 |

---

## 🎯 按角色推荐

| 你是谁 | 必读 | 选读 |
|--------|------|------|
| **老板/总监** | #1, #2, #3 | #4, #8 |
| **架构师/Tech Lead** | #1, #5, #6, #7, #8 | #9, #16 |
| **实现工程师** | #5, #14, #15, #16, #17 | #10, #11, PoC 代码 |
| **数据治理/合规** | #1, #3, #4, #13 | #17 |
| **想了解全貌的人** | 15 分钟路径 → 1 小时路径 | 按兴趣深入 |

---

## 💡 核心结论速览

1. **可行**：LLM 对 Go-Kitex 代码的字段语义提取准确率预估 85-92%
2. **成本可控**：10 万服务全量扫描约 $15K-30K（一次性），增量更新 $500-1K/月
3. **核心创新**：Code Graph 调用链 + LLM 语义提取 + 置信度传播 = 自底向上数据治理
4. **落地路径**：PoC 2 月 → 试点 5 月 → 规模化 12 月
5. **7 个价值场景**：数据分类、API schema 管理、隐私合规、风险分析、架构可视化、变更影响分析、知识沉淀

---

*本指南由 Evo Worker 自动生成的研究产物整理。所有文档为中文（通俗易懂），代码为英文注释。*
