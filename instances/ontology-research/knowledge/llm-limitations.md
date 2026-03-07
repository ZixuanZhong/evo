# LLM 在代码语义提取场景的精度与局限

> 本文深度分析 LLM 在从代码中提取字段语义时的 7 大风险和局限，每个都配有具体缓解方案。

---

## 1. 风险全景

在我们的场景中（LLM 分析 Go/Java/Python 代码 → 提取字段语义 → 构建 ontology），LLM 不是在"生成"代码，而是在"理解"代码。这个区分很重要——理解任务的风险模式和生成任务不同。

| # | 风险 | 严重性 | 发生频率 | 影响 |
|---|------|--------|---------|------|
| 1 | Hallucination（幻觉） | 🔴 高 | 中 | 产出错误的语义标注 |
| 2 | 多义字段混淆 | 🔴 高 | 高 | 同名字段标注错误 |
| 3 | 上下文窗口限制 | 🟠 中 | 高 | 跨文件信息丢失 |
| 4 | 成本不可控 | 🟠 中 | 中 | 全公司扫描成本爆炸 |
| 5 | 语言差异 | 🟡 低 | 中 | 动态语言精度骤降 |
| 6 | 内部框架/术语盲区 | 🟠 中 | 高 | 不认识字节内部库 |
| 7 | 非确定性输出 | 🟡 低 | 中 | 相同输入不同结果 |

---

## 2. 风险 1: Hallucination（幻觉）

### 2.1 问题描述

LLM 可能会"自信地胡说"——对字段语义给出看似合理但实际错误的描述。

**CodeHalu 研究**（Tian et al., AAAI 2025, [arxiv.org/abs/2405.00253](https://arxiv.org/abs/2405.00253)）评估了 17 个 LLM 在代码任务上的幻觉情况，发现所有模型都存在不同程度的代码幻觉。

**Library Hallucination 研究**（[arxiv.org/pdf/2509.22202](https://arxiv.org/pdf/2509.22202)）发现 LLM 会捏造不存在的库名、API 和 import 路径——在我们的场景中类似的风险是：LLM 可能捏造字段之间的映射关系。

**在我们场景中的具体表现**：

```go
type OrderReq struct {
    UID    int64  `json:"uid"`
    Amount int64  `json:"amount"`
}
```

LLM 可能给出：
- UID: "用户唯一标识符" ✅（正确）
- Amount: "订单金额，单位元" ❌（实际上单位是分！LLM 猜的）

### 2.2 缓解方案

#### 方案 A: Confidence Scoring + 阈值过滤

```python
# LLM 输出时要求附带 confidence
prompt = """
对每个字段给出语义描述和置信度 (0-1)。
如果你不确定，置信度给低分，不要猜测。

输出格式:
{"field": "Amount", "semantic": "...", "confidence": 0.7, "uncertainty_reason": "无法确定单位"}
"""

# 低置信度标记为"待人工审核"
if result.confidence < 0.7:
    mark_for_human_review(result)
```

#### 方案 B: 交叉验证（多次调用取共识）

```python
def cross_validate(code_snippet, field, n_calls=3):
    """
    对同一字段调用 LLM 3 次，取共识结果。
    """
    results = [llm_extract(code_snippet, field) for _ in range(n_calls)]
    
    # 如果 3 次结果一致 → 高置信度
    if all_agree(results):
        return results[0], confidence=0.95
    
    # 如果 2/3 一致 → 中置信度
    majority = get_majority(results)
    if majority:
        return majority, confidence=0.80
    
    # 全不一致 → 低置信度，标记人工审核
    return results[0], confidence=0.40, flag="divergent"
```

#### 方案 C: AST 事实核查

LLM 给出的语义描述可以用 AST 信息做基本核查：
- LLM 说 "这个字段是 string 类型" → 和 Go struct 定义的类型比对
- LLM 说 "这个字段是可选的" → 和 Thrift IDL 的 required/optional 比对
- LLM 说 "这个字段传递给了 X 函数" → 和 Code Graph 的调用关系比对

---

## 3. 风险 2: 多义字段混淆

### 3.1 问题描述

同名字段在不同上下文中含义不同，LLM 容易混淆。

```go
// 服务 A: 直播间
type EnterRoomReq struct {
    UserID int64  // 这里是观众 ID
}

// 服务 B: 结算系统
type SettlementReq struct {
    UserID int64  // 这里是主播 ID
}
```

LLM 看到 `UserID` 可能给出通用描述"用户 ID"，但无法区分它在具体业务场景中代表观众还是主播。

### 3.2 缓解方案

#### 注入调用链上下文

```python
def extract_with_context(target_func, field, call_chain):
    """
    把调用链上下文注入 prompt，帮助 LLM 理解字段在当前业务场景中的含义。
    """
    # 构建上下文信息
    context = f"""
    调用链: {' → '.join(call_chain)}
    当前服务: {target_func.service_name}
    当前 API: {target_func.api_name}
    API 功能: {target_func.api_description or "未知"}
    
    周围字段: {[f.name for f in target_func.sibling_fields]}
    """
    
    prompt = f"""
    在以下业务上下文中，分析字段 {field.name} 的具体含义：
    
    {context}
    
    代码：
    {target_func.code}
    
    注意：不要给出通用描述（如"用户ID"），要结合上下文给出具体含义
    （如"送礼物的观众用户ID"或"被结算的主播用户ID"）。
    """
    return llm_call(prompt)
```

#### 周围字段暗示

如果 struct 中有 `AnchorID` 和 `ViewerID`，那同一 struct 中的 `UserID` 更可能是第三种角色（如管理员）。利用同一 struct 中的其他字段做暗示。

---

## 4. 风险 3: 上下文窗口限制

### 4.1 问题描述

即使现在 GPT-4o 支持 128K token、Claude 支持 200K token，一个完整微服务的代码量仍可能超出窗口：

| 服务规模 | 代码行数 | 约等于 token 数 | 能否放进 128K？ |
|----------|---------|----------------|---------------|
| 小型服务 | 1,000-5,000 | 5K-25K | ✅ |
| 中型服务 | 5,000-20,000 | 25K-100K | ⚠️ 勉强 |
| 大型服务 | 20,000-100,000 | 100K-500K | ❌ |
| Monorepo | 100,000+ | 500K+ | ❌❌ |

更严重的问题：**"Lost in the Middle"效应**——LLM 对超长上下文中间部分的注意力显著下降。即使代码放得进窗口，中间部分的字段提取精度也会降低。

参考：Chain of Agents (NeurIPS 2024) 提出为每个 agent 分配短上下文来解决长文本注意力问题。

### 4.2 缓解方案

#### AST 预处理 + 按需注入

```python
def smart_context_assembly(target_function, max_tokens=8000):
    """
    不要把整个服务代码塞给 LLM。
    用 AST 工具精确提取目标函数需要的上下文。
    """
    context_parts = []
    remaining = max_tokens
    
    # 第 1 优先：目标函数本身
    func_code = get_function_code(target_function)
    context_parts.append(func_code)
    remaining -= count_tokens(func_code)
    
    # 第 2 优先：目标函数引用的 struct 定义
    referenced_types = ast_get_referenced_types(target_function)
    for t in referenced_types:
        type_def = get_type_definition(t)
        if count_tokens(type_def) <= remaining:
            context_parts.append(type_def)
            remaining -= count_tokens(type_def)
    
    # 第 3 优先：被调用函数的签名（不含实现）
    callees = get_callee_signatures(target_function)
    for sig in callees:
        if count_tokens(sig) <= remaining:
            context_parts.append(sig)
            remaining -= count_tokens(sig)
    
    # 第 4 优先：文件级注释和 package 文档
    if remaining > 500:
        doc = get_package_doc(target_function.package)
        context_parts.append(doc[:remaining])
    
    return "\n\n".join(context_parts)
```

#### 分层分析策略

```
Layer 1: Thrift IDL 分析（小，~1K token/服务）→ 提取接口和字段定义
Layer 2: Handler 函数分析（中，~2K token/函数）→ 提取字段映射
Layer 3: DAL 函数分析（中，~2K token/函数）→ 提取 DB 操作
Layer 4: 跨函数关系合并（无需 LLM，图计算）
```

每层都控制在 8K token 以内，避免触及窗口限制。

---

## 5. 风险 4: 成本不可控

### 5.1 模型成本对比（2025-2026 定价）

| 模型 | Input ($/M token) | Output ($/M token) | 代码理解能力 | 窗口 |
|------|-------------------|--------------------|----|------|
| **GPT-4o** | $2.50 | $10.00 | ⭐⭐⭐⭐⭐ | 128K |
| **GPT-4o-mini** | $0.15 | $0.60 | ⭐⭐⭐⭐ | 128K |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | ⭐⭐⭐⭐⭐ | 200K |
| **Claude Haiku** | $0.80 | $4.00 | ⭐⭐⭐⭐ | 200K |
| **DeepSeek-Coder-V2** | $0.14 | $0.28 | ⭐⭐⭐⭐ | 128K |
| **Qwen2.5-Coder-32B** | 自部署 | 自部署 | ⭐⭐⭐⭐ | 128K |

参考: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing), [IntuitionLabs LLM Pricing Comparison 2025](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)

### 5.2 全公司扫描成本估算

假设 10 万个服务，每服务 20 个 API，每 API 需分析 ~2K token：

| 方案 | Token 总量 | 单价 | 总成本 | 耗时 |
|------|-----------|------|--------|------|
| 全用 GPT-4o | ~4B input + 1B output | $2.50/$10 | **~$20,000** | 数天 |
| 全用 GPT-4o-mini | 同上 | $0.15/$0.60 | **~$1,200** | 数天 |
| 全用 DeepSeek-V2 | 同上 | $0.14/$0.28 | **~$840** | 数天 |
| 分层策略（推荐） | ~1B input + 0.3B output | 混合 | **~$500-800** | 2-3天 |

### 5.3 成本控制策略

```
1. AST 先行：能用 AST 提取的信息不调用 LLM
   - IDL 解析: 免费（AST 工具）
   - 同名字段匹配: 免费
   - 仅语义描述/消歧时调用 LLM
   → 预计减少 60-70% 的 LLM 调用

2. 分层模型：
   - 粗扫（GPT-4o-mini / DeepSeek-V2）: 全量，$0.15/M
   - 精扫（GPT-4o / Claude Sonnet）: 仅高敏感或低置信度，$2.50/M
   → 预计 90% 用小模型，10% 用大模型

3. 缓存复用：
   - 同一 struct 在多个函数中出现时，只分析一次
   - 常见模式（BaseResp, Pagination 等）建立模板
   → 预计减少 30% 重复调用

4. 自部署开源模型（长期）：
   - Qwen2.5-Coder-32B 或 DeepSeek-Coder-V2
   - A100 GPU ~$2/小时，批处理吞吐高
   - 长期成本比 API 低 5-10 倍
```

---

## 6. 风险 5: 语言差异

### 6.1 Go vs Python 提取精度对比

| 维度 | Go（强类型） | Python（动态类型） |
|------|-------------|-------------------|
| **字段类型信息** | 编译期确定（`int64`, `string`） ✅ | 运行时确定，可能缺少 type hint ❌ |
| **struct 定义** | 显式 `type Xxx struct` ✅ | dict / dataclass / Pydantic，形式多样 ⚠️ |
| **JSON 序列化名** | `json:"xxx"` tag 显式 ✅ | 可能无显式定义 ❌ |
| **import 关系** | 静态、编译期检查 ✅ | 动态 import，monkey-patching ❌ |
| **框架模式** | Hertz/Kitex 高度统一 ✅ | Flask/FastAPI/Django 各异 ⚠️ |
| **预估提取精度** | **88-95%** | **70-82%** |

### 6.2 缓解

- **Go 优先**：字节主力语言是 Go，优先覆盖投入产出比最高
- **Python 补充**：对 Python 服务，优先分析有 type hint 和 Pydantic model 的
- **Java 适中**：Java 强类型 + Spring 注解，精度接近 Go（85-92%）

---

## 7. 风险 6: 内部框架/术语盲区

### 7.1 问题描述

LLM 的训练数据不包含字节内部代码。它不认识：
- **内部框架**：`bytelib`, `byterpc`, `bytearch` 等内部库
- **内部术语**：PSM（服务标识）、BOE（测试环境）、TOS（对象存储）
- **内部约定**：字段命名规范、错误码含义、中间件注入字段

### 7.2 缓解方案

#### 内部术语表注入

```python
INTERNAL_GLOSSARY = {
    "PSM": "Product Service Module，字节内部服务唯一标识，格式如 product.module.service",
    "BOE": "ByteDance Online Environment，内部测试环境",
    "TOS": "Toutiao Object Storage，字节对象存储服务",
    "RPC_UID": "通过 RPC 框架从 token 中解析出的用户 ID，由中间件自动注入",
    "BizCode": "业务错误码，0 表示成功，非 0 表示各类业务异常",
}

def build_prompt_with_glossary(code, glossary_subset):
    """
    扫描代码中出现的内部术语，将相关解释注入 prompt。
    """
    terms_found = [t for t in glossary_subset if t.lower() in code.lower()]
    glossary_section = "\n".join(f"- {t}: {glossary_subset[t]}" for t in terms_found)
    
    return f"""
    ## 内部术语参考
    {glossary_section}
    
    ## 代码
    {code}
    """
```

#### 持续学习循环

```
1. 人工审核发现 LLM 不认识的内部术语
2. 添加到术语表
3. 下次扫描时自动注入
4. 定期更新术语表（每季度）
```

---

## 8. 风险 7: 非确定性输出

### 8.1 问题描述

LLM 是概率模型，相同输入可能产生不同输出。这对我们的场景意味着：
- 今天扫描和明天扫描可能给出不同的字段语义描述
- 重新运行 pipeline 可能改变已有的 ontology 标注
- 难以做回归测试

### 8.2 缓解方案

```python
# 1. 设置 temperature=0（最大确定性）
result = llm_call(prompt, temperature=0, seed=42)

# 2. 结果锁定：一旦人工确认，不再被 LLM 覆盖
if field.source == "human_reviewed":
    skip_llm_update(field)

# 3. 变更检测：如果新结果和旧结果差异大，标记为"待确认"而非自动覆盖
if semantic_similarity(old_result, new_result) < 0.8:
    mark_as_pending_review(field, old_result, new_result)
else:
    # 小幅变化，静默更新
    update_silently(field, new_result)
```

---

## 9. LLMDFA 的启示

**LLMDFA** (Wang et al., NeurIPS 2024, [arxiv.org/abs/2402.10754](https://arxiv.org/abs/2402.10754)) 是目前 LLM 做数据流分析最有说服力的工作：

| 指标 | LLMDFA 结果 | 对我们的启示 |
|------|------------|------------|
| Source/Sink 提取精度 | **100%** precision+recall | 基础提取任务 LLM 非常可靠 |
| 路径可达性分析 | **87-91%** precision | 需要分解子任务才能达到高精度 |
| 无需编译 | ✅ | 适合我们的大规模无编译扫描场景 |
| 自定义分析 | ✅ | 可定制不同的提取目标 |

**关键启示**：LLMDFA 的成功在于"分解 + 合成"——把复杂的数据流分析分解为多个简单的子任务（source 提取、sink 提取、路径可达性），每个子任务 LLM 都能做好。我们的 ontology 提取也应该采用同样的分解策略。

---

## 10. 综合缓解架构

```
┌─────────────────────────────────────────────────────────┐
│                    提取精度保障体系                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  第 1 层：AST 预处理（免费、100% 精度）                   │
│  ├── Go AST → struct 定义、类型、tag                     │
│  ├── Thrift IDL → 接口、字段、required/optional          │
│  └── SQL Parser → 表名、列名、操作类型                    │
│                                                          │
│  第 2 层：LLM 语义提取（成本可控、85-95% 精度）           │
│  ├── 小模型粗扫：GPT-4o-mini / DeepSeek-V2              │
│  ├── 大模型精扫：GPT-4o / Claude（仅高敏感字段）          │
│  └── 上下文注入：调用链 + 术语表 + 周围字段               │
│                                                          │
│  第 3 层：交叉验证（提升 5-10% 精度）                     │
│  ├── 多次调用共识（n=3）                                 │
│  ├── AST 事实核查（类型/必填性比对）                      │
│  └── Code Graph 一致性检查（调用关系验证）                │
│                                                          │
│  第 4 层：人工闭环（最终兜底）                             │
│  ├── 低置信度标记 → 人工审核队列                          │
│  ├── 定期抽检 → 发现系统性错误                            │
│  └── 反馈循环 → 更新术语表和 few-shot 示例                │
│                                                          │
│  预期综合精度: 92-97%（含人工闭环）                       │
│  预期纯自动精度: 85-92%（不含人工）                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 11. 小结

| 风险 | 严重性 | 核心缓解 | 预期效果 |
|------|--------|---------|---------|
| **Hallucination** | 🔴 | Confidence scoring + 交叉验证 + AST 核查 | 精度 +8-12% |
| **多义字段** | 🔴 | 调用链上下文注入 + 周围字段暗示 | 消歧准确率 85%+ |
| **上下文窗口** | 🟠 | AST 预处理按需组装 + 分层分析 | 控制在 8K token/次 |
| **成本** | 🟠 | 分层模型 + AST 先行 + 缓存 | 全量扫描 <$1,000 |
| **语言差异** | 🟡 | Go 优先 + Python type hint 依赖 | Go 90%+ / Python 75%+ |
| **内部盲区** | 🟠 | 术语表注入 + 持续更新 | 覆盖 90%+ 内部术语 |
| **非确定性** | 🟡 | temperature=0 + 结果锁定 + 变更检测 | 99%+ 输出一致性 |

**总体评估**：LLM 用于代码语义提取是可行的，但需要"AST 做重活、LLM 做巧活、人工做兜底"的分层架构。单独依赖 LLM 精度约 80-85%，加上 AST + 交叉验证 + 术语表后可达 90-95%，加上人工闭环可达 95%+。

---

*最后更新: 2026-03-05*
*参考: CodeHalu (Tian et al., AAAI 2025), LLMDFA (Wang et al., NeurIPS 2024), Library Hallucinations (arxiv 2509.22202), Claude/OpenAI Pricing 2025-2026*
