# Ontology 入门：从零理解本体论

> 目标读者：有经验的后端工程师，不了解 ontology 概念。
> 写作风格：通俗易懂，多用比喻和例子。

---

## 1. 什么是 Ontology？

### 一句话版本

**Ontology（本体论）就是对某个领域里"有什么东西、这些东西之间有什么关系"的一套正式约定。**

### 用直播间的例子讲清楚

假设你在字节做直播业务，你的系统里有这些"东西"：

- **直播间**（LiveRoom）：有房间号、标题、状态
- **主播**（Anchor）：有用户ID、昵称、等级
- **观众**（Viewer）：有用户ID、昵称
- **礼物**（Gift）：有名称、价格

这些东西之间有什么关系？

```
主播 ──拥有──→ 直播间
观众 ──观看──→ 直播间
观众 ──赠送──→ 礼物 ──送给──→ 主播
直播间 ──属于──→ 分类（游戏/唱歌/聊天）
```

如果你把上面这些东西和关系**严格地定义**出来——每个概念是什么意思、有哪些属性、彼此之间怎么关联——恭喜你，你就建了一个 **ontology**。

### 和写代码的类比

你可以把 ontology 类比成 **Go 的 type 定义 + interface 约束**：

```go
// 这就是一个简单的 ontology 定义
type LiveRoom struct {
    RoomID    int64     // 属性
    Title     string    // 属性
    Status    string    // 属性
    Owner     *Anchor   // 关系：拥有者
    Category  string    // 关系：属于哪个分类
}

type Anchor struct {
    UserID    int64
    Nickname  string
    Level     int
    Rooms     []*LiveRoom  // 关系：拥有的直播间
}
```

但 ontology 比代码中的 struct 更强大，因为它还定义了：

1. **语义约束**：`LiveRoom.Owner` 必须是一个 `Anchor`，不能是观众
2. **继承关系**：`Anchor` 和 `Viewer` 都是 `User` 的子类
3. **推理规则**：如果 A 拥有直播间 R，R 收到了礼物 G，那么 A 是 G 的接收者

**一个比喻**：如果 struct 是"建筑图纸"，那 ontology 就是"城市规划" —— 它不仅定义每栋楼长什么样，还定义楼和楼之间的道路、水电、规划约束。

---

## 2. Ontology vs Taxonomy vs Knowledge Graph

这三个概念经常被混用，但它们其实是不同层次的东西。

### 表格对比

| 维度 | Taxonomy（分类法） | Ontology（本体论） | Knowledge Graph（知识图谱） |
|------|-------------------|--------------------|-----------------------------|
| **本质** | 一棵分类树 | 一套概念+关系的形式化定义 | 大量实体和关系的实例数据 |
| **结构** | 树形（严格父子） | 图形（任意关系） | 图形（海量节点+边） |
| **关系类型** | 只有"是一种"（is-a） | 任意关系（拥有、属于、调用…） | 任意关系 |
| **有没有实例** | 通常没有 | 定义模式，可有可无 | 海量实例 |
| **类比** | 超市货架分区 | 超市经营手册 | 超市里具体的每一件商品 |
| **技术圈类比** | 目录树/枚举值 | Proto/IDL schema | 数据库里的实际数据 |

### 用直播业务举例

**Taxonomy（分类法）**：

```
直播内容分类
├── 游戏
│   ├── MOBA
│   ├── FPS
│   └── 卡牌
├── 才艺
│   ├── 唱歌
│   ├── 跳舞
│   └── 乐器
└── 聊天
    ├── 情感
    └── 职场
```

这就是一棵分类树。它只能表达"唱歌是才艺的一种"，但不能表达"主播在直播间里唱歌"。

**Ontology（本体论）**：

```
定义了：
- LiveRoom 有 owner (Anchor), category (Category), status (enum)
- Anchor 是 User 的子类
- Gift 有 sender (Viewer), receiver (Anchor), value (Money)
- "赠送" 是一种 Action，涉及 sender, receiver, object, timestamp
```

它定义的是"概念模型"——世界上有什么东西、它们之间有什么关系。

**Knowledge Graph（知识图谱）**：

```
(直播间#12345, 拥有者, 主播小明)
(主播小明, 等级, 钻石)
(观众老王, 送了, 火箭)
(火箭, 送给, 主播小明)
(火箭, 价值, 500抖币)
(直播间#12345, 分类, 唱歌)
```

这是具体的实例数据。

**三者的关系**：
- Taxonomy 是 Ontology 的一个子集（只包含分类关系）
- Knowledge Graph 是 Ontology 的实例化（填入真实数据）
- **Ontology 定义 schema，Knowledge Graph 存储 data**，就像 Proto 定义消息格式，DB 里存储实际消息

---

## 3. Ontology 的核心概念

### 3.1 Class（类）

类就是一类事物的定义，相当于 Go 的 `type`。

```
Class: LiveRoom（直播间）
Class: Anchor（主播）
Class: Viewer（观众）
Class: User（用户）—— Anchor 和 Viewer 的父类
Class: Gift（礼物）
```

类可以有继承关系：

```
User
├── Anchor（主播是一种用户）
└── Viewer（观众是一种用户）
```

### 3.2 Property（属性）

属性描述一个类的具体特征，分两种：

- **数据属性**（Data Property）：值是基本类型（string、int、bool）
  - `LiveRoom.title` → string
  - `Anchor.level` → int
  - `Gift.price` → float

- **对象属性**（Object Property）：值是另一个类的实例
  - `LiveRoom.owner` → Anchor
  - `Gift.sender` → Viewer

对应到 Go 就是：基本类型字段 vs 指针/引用字段。

### 3.3 Relation（关系）

关系是连接两个类实例的边，比属性更通用。

```
owns:      Anchor → LiveRoom  （主播拥有直播间）
watches:   Viewer → LiveRoom  （观众观看直播间）
sends_to:  Viewer → Anchor    （观众给主播送礼）
belongs_to: LiveRoom → Category（直播间属于某分类）
calls:     Service → Service   （服务调用服务）
```

关系可以有属性（称为"边属性"）：

```
(观众老王) ──sends_to──→ (主播小明)
    边属性: gift=火箭, amount=1, timestamp=2024-01-01
```

### 3.4 Instance（实例）

实例是类的具体对象，就是数据库里的一行数据。

```
Class: LiveRoom
Instance: room_12345 (title="小明的唱歌间", status="live", owner=anchor_001)

Class: Anchor
Instance: anchor_001 (nickname="小明", level=5)
```

### 总结：四个概念的类比

| Ontology 概念 | Go 类比 | 数据库类比 | 直播例子 |
|---------------|---------|-----------|---------|
| Class | type struct | Table DDL | LiveRoom |
| Property | struct field | Column | room_id, title |
| Relation | 引用/指针 | Foreign Key | owner → Anchor |
| Instance | 变量/对象 | 一行数据 | room_12345 |

---

## 4. 为什么微服务字段需要 Ontology

### 先说问题：简单标签分类不够用

传统的数据分类方式是给字段打标签：

```
user_id → PII（个人身份信息）
phone   → PII-电话号码
room_id → 业务ID
```

这看起来够用了？考虑以下场景：

**场景 1：同名不同义**

```
// service A: 创建直播间
type CreateRoomReq struct {
    UserID int64  // 这里的 user_id 是主播
}

// service B: 送礼
type SendGiftReq struct {
    UserID int64  // 这里的 user_id 是观众
}
```

两个 `user_id` 都被标为 PII，但语义完全不同。一个是主播身份（关联直播间权限），一个是消费者身份（关联支付信息）。简单标签无法区分。

**场景 2：字段传递链**

```
API 入口: CreateRoom(room_id)
  → 调用 RoomService.Save(room_id)
    → 调用 DB.Insert(rooms.id)
```

`room_id` 从 API 层传到 DB 层，中间可能改名（`room_id` → `id`），但语义不变。简单标签不能表达这种传递关系。

**场景 3：上下文语义**

```
// 在直播服务中
type Room struct {
    OwnerID int64  // 主播的 user_id
}

// 在支付服务中
type Order struct {
    PayerID int64  // 付款人的 user_id（观众）
}
```

`OwnerID` 和 `PayerID` 本质上都是 `user_id`，但上下文不同（所有权 vs 交易行为）。分类标签都是 PII，但隐私合规要求不同。

### Ontology 怎么解决

用 ontology 建模后：

```
FieldInstance: service_a.CreateRoomReq.UserID
  semantic_type: UserIdentifier
  context: RoomOwnership（直播间所有权）
  sensitivity: PII
  data_subject: Anchor（主播）

FieldInstance: service_b.SendGiftReq.UserID
  semantic_type: UserIdentifier
  context: GiftTransaction（礼物交易）
  sensitivity: PII
  data_subject: Viewer（观众）

Relation:
  service_a.CreateRoomReq.UserID ──same_base_type──→ service_b.SendGiftReq.UserID
  （它们都是 UserIdentifier，但 context 不同）
```

**Ontology 比标签强在哪？**

| 能力 | 标签分类 | Ontology |
|------|---------|----------|
| 识别字段类型 | ✅ PII | ✅ PII |
| 区分上下文语义 | ❌ | ✅ Anchor vs Viewer |
| 追踪字段传递 | ❌ | ✅ API→func→DB |
| 推理隐含关系 | ❌ | ✅ 如果字段 A 传给字段 B，B 的标签可传播给 A |
| 跨服务关联 | ❌ | ✅ 同一 room_id 在不同服务中的对应关系 |

简单说：**标签是一维的（这是什么），ontology 是多维的（这是什么、在什么语境、和什么关联、从哪来到哪去）。**

### 对微服务架构的特殊价值

在数十万微服务的环境下，字段的含义不是孤立的，它由以下因素共同决定：

1. **所属服务**：同一个 `id` 在不同服务里含义不同
2. **调用上下文**：这个字段是从哪个 API 传过来的
3. **数据流向**：这个字段最终写到了哪个 DB
4. **业务语境**：这个字段在什么业务场景下使用

Ontology 能把这四个维度都建模进去，而简单标签只能覆盖第一维。

---

## 5. 真实世界的 Ontology 例子

### 5.1 Schema.org — Web 世界的通用 ontology

**是什么**：由 Google、Microsoft、Yahoo、Yandex 联合发起的一套网页结构化数据标准。

**规模**：827 个类型（Types）、1528 个属性（Properties）、14 种数据类型。

**干什么用**：让搜索引擎理解网页内容的语义。

**例子**：

```json
{
  "@context": "https://schema.org",
  "@type": "LiveStream",
  "name": "小明的唱歌直播",
  "description": "每晚8点唱歌",
  "startDate": "2024-01-01T20:00:00",
  "performer": {
    "@type": "Person",
    "name": "小明"
  },
  "audience": {
    "@type": "Audience",
    "audienceType": "online viewers"
  }
}
```

**对我们的启发**：
- Schema.org 用一套统一的 ontology 让全球 4500 万个网站的数据可以互相理解
- 我们的目标类似：用一套字段级 ontology 让数十万微服务的数据可以互相理解

> 参考：[Schema.org 官网](https://schema.org/)、[Schema.org 数据模型](https://schema.org/docs/datamodel.html)

### 5.2 FIBO — 金融行业本体

**是什么**：Financial Industry Business Ontology，金融行业业务本体。由 EDM Council 维护，OMG（Object Management Group）标准化。

**背景**：2008 年金融危机后，监管机构发现各银行对"贷款"、"证券"、"风险敞口"等概念的定义各不相同，导致无法有效监管。FIBO 就是为了解决"大家说的是不是同一个东西"这个问题。

**例子**：

```
Class: LoanContract（贷款合同）
  Properties:
    - hasLender: LegalEntity（出借方）
    - hasBorrower: LegalEntity（借款方）
    - hasPrincipalAmount: MonetaryAmount（本金）
    - hasInterestRate: Percentage（利率）
    - hasMaturityDate: Date（到期日）

Class: MonetaryAmount
  Properties:
    - hasCurrency: Currency
    - hasValue: Decimal
```

**对我们的启发**：
- FIBO 解决的是"不同银行系统之间的语义对齐"——和我们解决"不同微服务之间的字段语义对齐"高度类似
- FIBO 用 OWL（Web Ontology Language）定义，支持自动推理
- 金融行业愿意为此投入大量资源（因为监管合规是硬需求），数据隐私合规对字节同样是硬需求

> 参考：[FIBO 官方](https://spec.edmcouncil.org/fibo/)、[EDM Council FIBO 介绍](https://edmcouncil.org/frameworks/industry-models/fibo/)

### 5.3 SNOMED CT — 医疗领域本体

**是什么**：Systematized Nomenclature of Medicine — Clinical Terms，全球最全面的临床医学术语体系。

**规模**：超过 35 万个医学概念，数百万个语义关系。

**干什么用**：让全球不同医院、不同电子病历系统能用统一的"语言"描述病人的症状、诊断、治疗。

**例子**：

```
概念: 糖尿病（Diabetes mellitus）
  IS-A: 代谢性疾病
  FINDING-SITE: 胰腺（Pancreas）
  ASSOCIATED-WITH: 高血糖（Hyperglycemia）

  子类:
    - 1型糖尿病
    - 2型糖尿病
    - 妊娠期糖尿病
```

**对我们的启发**：
- SNOMED CT 面对的挑战和我们类似：海量的概念（35万+）、复杂的关系、需要跨系统互操作
- 他们的经验：ontology 必须能"自动推理"（给定 A IS-A B，B 有某属性，则 A 也有）——这对我们的字段语义传播非常有价值
- 维护这样的 ontology 需要持续投入，但一旦建成，价值巨大

> 参考：[SNOMED International 官网](https://www.snomed.org/)、[SNOMED CT - Wikipedia](https://en.wikipedia.org/wiki/SNOMED_CT)

### 三个例子的共同启示

| | Schema.org | FIBO | SNOMED CT | **我们的场景** |
|---|-----------|------|-----------|--------------|
| 领域 | Web | 金融 | 医疗 | 微服务 |
| 核心问题 | 网页数据互通 | 金融术语对齐 | 医学概念统一 | 字段语义对齐 |
| 规模 | ~800类型 | ~数千类型 | ~35万概念 | ~数十万字段 |
| 驱动力 | SEO/搜索 | 监管合规 | 临床互操作 | 数据治理/隐私 |
| 关键成功因素 | 简单易用 | 严格标准化 | 持续维护 | **自动化构建** |

最后一行是关键：前三个 ontology 都是**人工构建**的，耗时数年。我们的创新点在于：**用 LLM + Code Graph 自动构建 ontology**，大幅降低建设成本。

---

## 6. 小结

| 你之前以为 | 实际上 |
|-----------|--------|
| Ontology 是学术概念 | 它是工程中最强大的数据建模工具之一 |
| 给字段打标签就够了 | 标签是一维的，ontology 是多维的 |
| Knowledge Graph 就是 ontology | KG 是实例数据，ontology 是 schema |
| 建 ontology 一定很贵 | LLM + 代码分析可以自动化构建 |

**下一步**：在 `kg-tech-stack.md` 中，我们会深入聊如何选择技术栈来实现这个 ontology graph。

---

## 参考资料

- [Schema.org 官网](https://schema.org/)
- [Schema.org 数据模型](https://schema.org/docs/datamodel.html)
- [FIBO — Financial Industry Business Ontology](https://spec.edmcouncil.org/fibo/)
- [EDM Council FIBO 介绍](https://edmcouncil.org/frameworks/industry-models/fibo/)
- [SNOMED International](https://www.snomed.org/)
- [SNOMED CT - Wikipedia](https://en.wikipedia.org/wiki/SNOMED_CT)
- [W3C: Schema vs Ontology](https://www.w3.org/wiki/SchemaVsOntology)
