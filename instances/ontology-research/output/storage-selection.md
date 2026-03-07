# 图数据库存储选型：Ontology Graph 用什么存？

> 本文对比 5 款图数据库在字段级 Ontology Graph 场景（~3700 万节点、~1.27 亿边）下的适用性，并给出分阶段推荐。

---

## 1. 候选方案

| 方案 | 类型 | 许可证 | 一句话特点 |
|------|------|--------|-----------|
| **Neo4j** | 原生图 | Community(GPLv3) / Enterprise(商业) | 生态最成熟，Cypher 标准制定者 |
| **NebulaGraph** | 分布式图 | Apache 2.0 | 开源分布式，中文社区活跃 |
| **ByteGraph** | 分布式图 | 字节内部 | 零许可成本，已服务字节所有图场景 |
| **TigerGraph** | 分析型图 | 商业 | GSQL 强大，深度链接分析王者 |
| **JanusGraph** | 开源图 | Apache 2.0 | 可插拔后端(Cassandra/HBase/BerkeleyDB) |

---

## 2. 多维度对比

### 2.1 核心对比表

| 维度 | Neo4j Enterprise | NebulaGraph | ByteGraph | TigerGraph | JanusGraph |
|------|-----------------|-------------|-----------|------------|------------|
| **查询语言** | Cypher ✅ | nGQL (类 Cypher) | Gremlin + 自研 | GSQL | Gremlin |
| **水平扩展** | ⚠️ 读扩展(Causal Cluster) 写单主 | ✅ 原生分布式 | ✅ 原生分布式 | ✅ 分布式 | ✅ 基于后端(Cassandra) |
| **读延迟(1-hop)** | <1ms ⭐ | 1-5ms | 1-3ms | 1-5ms | 5-20ms |
| **写吞吐** | ~50K edges/s | ~200K edges/s | ~500K edges/s ⭐ | ~100K edges/s | ~30K edges/s |
| **深度遍历(5-hop)** | 10-100ms | 50-200ms | 10-50ms ⭐ | 5-30ms ⭐ | 100-500ms |
| **运维复杂度** | 低 ⭐ | 中 | 低(内部运维) | 中 | 高 |
| **成本** | 高(Enterprise 年费$36K+) | 低(开源) | 零 ⭐ | 很高($100K+/年) | 低(开源) |
| **GDS 算法库** | ✅ 最丰富(PageRank, Community Detection等) ⭐ | 基础 | 自研算法 | ✅ 丰富 | 第三方(Spark) |
| **生态工具** | ⭐⭐⭐⭐⭐(Browser, Bloom, Aura) | ⭐⭐⭐(Studio, Dashboard) | ⭐⭐(内部工具) | ⭐⭐⭐(GraphStudio) | ⭐⭐(基础) |
| **中文文档** | 有(翻译) | ✅ 原生中文 ⭐ | ✅ 内部文档 | 少 | 少 |
| **GQL/ISO标准** | 积极推进 | 跟进中 | 未知 | 自有 GSQL | Gremlin(Apache) |

**注**：性能数据为综合估算，参考 NebulaGraph 官方 benchmark ([nebula-graph.io](https://www.nebula-graph.io/posts/performance-comparison-neo4j-janusgraph-nebula-graph)), IEEE 论文 (2024, [IEEE Xplore 10391694](https://ieeexplore.ieee.org/document/10391694/)), Applied Sciences 论文 (2023, [MDPI 2076-3417/13/9/5770](https://www.mdpi.com/2076-3417/13/9/5770))。

### 2.2 我们场景的关键需求匹配

| 需求 | 权重 | Neo4j | NebulaGraph | ByteGraph | TigerGraph | JanusGraph |
|------|------|-------|-------------|-----------|------------|------------|
| 3700 万节点存储 | 高 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 1.27 亿边存储 | 高 | ⚠️(单机极限) | ✅ | ✅ | ✅ | ✅ |
| 5-hop 路径查询 | 高 | ✅ | ✅ | ✅ | ⭐ | ⚠️ |
| 批量写入速度 | 中 | ⚠️ | ✅ | ⭐ | ✅ | ❌ |
| 内部部署零成本 | 高 | ❌ | ✅ | ⭐ | ❌ | ✅ |
| Cypher 查询支持 | 中 | ⭐ | ⚠️(nGQL) | ❌ | ❌(GSQL) | ❌(Gremlin) |
| 图算法(社区发现) | 低 | ⭐ | 基础 | 自研 | ✅ | 第三方 |
| PoC 快速启动 | 高 | ⭐ | ✅ | ❌(需内部申请) | ❌(商业) | ⚠️ |

---

## 3. 存储和内存估算

### 3.1 数据规模回顾

基于 `knowledge/field-ontology-model.md` 的估算：

| 实体 | 数量 | 平均属性大小 |
|------|------|------------|
| 节点总数 | ~37,600,000 | ~200 bytes/节点 |
| 边总数 | ~127,000,000 | ~150 bytes/边 |

### 3.2 存储估算

```
节点存储: 37.6M × 200B = ~7.5 GB
边存储:   127M × 150B  = ~19.1 GB
索引:     ~30% overhead = ~8.0 GB
─────────────────────────────
总存储:   ~34.6 GB（裸数据）

考虑数据库内部开销（2-3x）:
- Neo4j:       ~70-100 GB 磁盘
- NebulaGraph:  ~80-120 GB 磁盘（3 副本）
- ByteGraph:   ~60-90 GB 磁盘（内部存储优化）
```

### 3.3 内存估算

```
图遍历需要热数据在内存中：

最小内存（冷启动查询）:
- 索引 + 频繁访问节点缓存: ~8-16 GB

推荐内存（性能优先）:
- Neo4j: 全图加载内存 ~64 GB（heap 31GB + pagecache 33GB）
- NebulaGraph: 每台 ~16 GB × 3 台 = ~48 GB 集群
- ByteGraph: 由内部集群调度，无需手动规划
```

### 3.4 存储成本

| 方案 | 硬件需求 | 月成本（云） | 月成本（字节内部） |
|------|---------|------------|-----------------|
| Neo4j Enterprise (单机) | 64GB RAM, 200GB SSD | ~$500/月 + 许可证 $3K/月 | N/A |
| NebulaGraph (3 节点) | 3× 16GB RAM, 100GB SSD | ~$450/月 | ~$200/月（内部资源） |
| ByteGraph | 内部集群 | N/A | **~$0**（已有集群分配） |
| TigerGraph | 64GB RAM + | ~$600/月 + 许可证 $8K+/月 | N/A |
| JanusGraph + Cassandra | 3× 16GB RAM | ~$450/月 | ~$200/月 |

---

## 4. 分阶段推荐

### 4.1 PoC 阶段（第 1-2 月）：Neo4j Community + NetworkX

**为什么？**

```
✅ Neo4j Community 免费、安装简单（Docker 一条命令）
✅ Cypher 查询语言直观，学习成本最低
✅ Neo4j Browser 自带可视化，PoC demo 效果好
✅ NetworkX (Python) 适合原型验证图算法
✅ 丰富的教程和社区支持

⚠️ 限制: Community 版没有集群，单机撑到 ~500 万节点
   → PoC 只需 3-5 个服务的数据，完全够用
```

**PoC 部署**：
```bash
# 一条命令启动 Neo4j
docker run -d \
  --name ontology-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/ontology123 \
  -v $HOME/neo4j/data:/data \
  neo4j:5-community
```

### 4.2 试点阶段（第 3-6 月）：NebulaGraph 或 Neo4j Enterprise

**如果选 NebulaGraph**：
```
✅ 开源免费，分布式，扛得住百万级节点
✅ 中文文档齐全，国内社区活跃
✅ nGQL 和 Cypher 语法相似，迁移成本低
⚠️ 生态工具不如 Neo4j 丰富
```

**如果选 Neo4j Enterprise**：
```
✅ GDS 算法库直接可用（社区发现、PageRank 等）
✅ 从 PoC 无缝升级，零迁移成本
⚠️ 许可证费用 ~$36K/年
```

### 4.3 生产阶段（第 6 月+）：ByteGraph

**为什么是 ByteGraph？**

```
✅ 字节内部方案，零许可成本
✅ 已服务字节所有图业务（社交关系、推荐、风控）
✅ 支撑千亿级边（我们只需 1.27 亿，轻松应对）
✅ 内部运维团队支持，无需自行运维
✅ 高性能：写入 ~500K edges/s，5-hop 遍历 10-50ms
✅ VLDB 2022 论文验证（Li et al., "ByteGraph: A High-Performance 
   Distributed Graph Database in ByteDance", VLDB 2022）

⚠️ 查询语言可能不是 Cypher → 需要适配层
⚠️ 需要走内部资源申请流程
```

参考论文：ByteGraph 在字节内部支撑了数百亿节点和数千亿边的图工作负载，OLTP 吞吐量随集群规模近线性增长（275B→550B 边，服务器增加 3.49x，吞吐增加 ~3x）。([VLDB 2022](https://dl.acm.org/doi/10.14778/3554821.3554824))

---

## 5. 迁移路径：PoC → 生产

### 5.1 数据模型层抽象

关键设计：**Pipeline 代码不直接耦合具体图数据库**，通过抽象层隔离。

```python
# graph_store.py - 抽象接口

class GraphStore:
    """图存储抽象层，屏蔽底层数据库差异"""
    
    def upsert_node(self, node_type: str, unique_key: dict, properties: dict):
        """创建或更新节点（幂等）"""
        raise NotImplementedError
    
    def upsert_edge(self, edge_type: str, source: dict, target: dict, properties: dict):
        """创建或更新边（幂等）"""
        raise NotImplementedError
    
    def query_neighbors(self, node_id: str, edge_types: list, direction: str, max_depth: int):
        """图遍历查询"""
        raise NotImplementedError
    
    def query_path(self, source_id: str, target_id: str, max_depth: int):
        """路径查询"""
        raise NotImplementedError


class Neo4jStore(GraphStore):
    """Neo4j 实现（PoC + 试点）"""
    def upsert_node(self, node_type, unique_key, properties):
        cypher = f"MERGE (n:{node_type} {{{format_props(unique_key)}}}) SET n += $props"
        self.driver.execute(cypher, props=properties)


class ByteGraphStore(GraphStore):
    """ByteGraph 实现（生产）"""
    def upsert_node(self, node_type, unique_key, properties):
        # ByteGraph 的原生 API 调用
        self.client.put_vertex(node_type, unique_key, properties)
```

### 5.2 迁移步骤

```
Step 1: 确认 ByteGraph schema（Property Graph 映射）
        ┌──────────────────────────────────────┐
        │ 把 Neo4j 的 Label + Property 映射到   │
        │ ByteGraph 的 Vertex/Edge Type         │
        └──────────────┬───────────────────────┘
                       │
Step 2: 实现 ByteGraphStore 适配器
        ┌──────────────┴───────────────────────┐
        │ 实现 GraphStore 接口的 ByteGraph 版本 │
        │ 主要工作：Cypher → ByteGraph API 翻译 │
        └──────────────┬───────────────────────┘
                       │
Step 3: 数据全量导出/导入
        ┌──────────────┴───────────────────────┐
        │ Neo4j → JSONL 导出 → ByteGraph 导入  │
        │ 3700 万节点 + 1.27 亿边 ≈ 1-2 小时   │
        └──────────────┬───────────────────────┘
                       │
Step 4: 双写验证期（1-2 周）
        ┌──────────────┴───────────────────────┐
        │ Pipeline 同时写 Neo4j + ByteGraph     │
        │ 对比两边数据一致性                     │
        │ 验证查询结果一致                       │
        └──────────────┬───────────────────────┘
                       │
Step 5: 切流
        ┌──────────────┴───────────────────────┐
        │ 读流量切到 ByteGraph                   │
        │ 关闭 Neo4j                             │
        └──────────────────────────────────────┘
```

### 5.3 迁移风险与缓解

| 风险 | 缓解 |
|------|------|
| ByteGraph 不支持 Cypher | 实现查询翻译层，或用 ByteGraph 原生 API |
| 数据导入中断 | 支持断点续传，每批 10K 条，有 checkpoint |
| 双写期性能下降 | 异步双写，ByteGraph 写入不阻塞主流程 |
| ByteGraph 资源申请周期长 | 提前申请，试点期同步进行 |

---

## 6. PoC 技术栈速查

```
PoC 阶段完整技术栈:
─────────────────────
图数据库:     Neo4j 5 Community (Docker)
图算法:       NetworkX (Python, 原型验证)
查询语言:     Cypher
可视化:       Neo4j Browser + pyvis (HTML)
驱动:         neo4j Python driver
数据导入:     LOAD CSV 或 neo4j-admin import
监控:         Neo4j Browser 自带的 metrics

生产阶段完整技术栈:
─────────────────────
图数据库:     ByteGraph (字节内部)
图算法:       ByteGraph 自研 + Spark GraphX
查询语言:     ByteGraph 原生 API
可视化:       自研 Web UI (React + D3.js)
数据导入:     ByteGraph Bulk Loader
监控:         字节内部 Metrics/Grafana
```

---

## 7. 小结

| 阶段 | 推荐方案 | 理由 | 数据量级 |
|------|---------|------|---------|
| **PoC** | Neo4j Community + NetworkX | 免费、快速启动、可视化好 | <500 万节点 |
| **试点** | NebulaGraph 或 Neo4j Enterprise | 开源分布式 / 丰富算法库 | <1000 万节点 |
| **生产** | ByteGraph | 零成本、千亿级验证、内部运维 | ~3700 万节点 |

**迁移保障**：通过 `GraphStore` 抽象层隔离底层数据库，迁移只需实现新的适配器 + 数据全量导入。

---

*最后更新: 2026-03-05*
*参考: ByteGraph VLDB 2022, NebulaGraph Benchmark, IEEE Graph DB Scalability Study 2024, Applied Sciences Graph DB Evaluation 2023*
