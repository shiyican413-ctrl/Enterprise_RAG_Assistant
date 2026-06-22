# Enterprise RAG Assistant Query 改写方案

## 1. 背景与目标

当前项目的问答链路是：

```text
用户问题
  -> Guardrails
  -> Memory
  -> Planner 判断是否需要知识库
  -> Executor 执行 knowledge_search
  -> ReAct Agent 基于证据回答
```

目前 `knowledge_search` 基本直接使用用户原始问题或 Agent 给出的单个 `query` 去检索。这个方式在简单事实问答里可用，但企业知识库场景会遇到几个典型问题：

- 用户问题口语化，例如“报销多久到账”“这个怎么算”。
- 企业文档更偏制度化表述，例如“费用报销审批通过后三个工作日内支付”。
- 用户会使用简称、别名、业务黑话，例如“差标”“竞业”“权限申请”。
- 一句话里包含多个子问题，例如“差旅和报销有什么区别，分别谁审批”。
- 问题里隐藏时间、部门、文档类型等过滤条件，例如“2026 年 Q2 的差旅标准”。
- 多轮对话里有指代，例如“那它的审批人是谁”。

Query 改写的目标不是让模型“更会聊天”，而是让检索更稳：

```text
把用户自然语言问题
  改写成适合企业知识库检索的结构化检索计划
  再用多路召回、融合、去重、审计记录
  提高召回覆盖率和答案可溯源性
```

## 2. 资料调研结论

### 2.1 企业级 RAG 常见 Query 改写方式

公开工程资料里，Query Transformation / Query Rewrite 通常包含这些模式：

| 方法 | 作用 | 适合本项目的用法 |
| --- | --- | --- |
| Query normalization | 纠正口语、补全语义、统一术语 | 第一版必做 |
| Query expansion | 扩展同义词、简称、相关制度词 | 第一版必做 |
| Multi-query | 生成多个角度的检索 query 并融合结果 | 第一版必做 |
| Query decomposition | 把复杂问题拆成多个可独立检索的子问题 | 第一版必做轻量版 |
| Conversational rewrite | 用会话上下文消解“它/这个/刚才那个” | 第二版做 |
| Metadata extraction | 抽取时间、部门、文档名、制度类型等过滤条件 | 第一版预留，第二版增强 |
| HyDE | 先生成假想答案/假想文档，再用它向量检索 | 暂不首发，成本和幻觉风险更高 |
| Step-back query | 先抽象成上位概念再检索 | 暂不首发，适合复杂研究问答 |
| RAG Fusion / RRF | 多查询结果融合，避免只信单路排名 | 第一版必做 |

工程上比较一致的做法是：不要只把 query 改成一个句子，而是生成一个结构化检索计划：

```json
{
  "original_query": "报销多久到账",
  "standalone_query": "员工费用报销审批通过后多久打款",
  "semantic_queries": [
    "员工费用报销审批通过后多久打款",
    "报销付款周期 财务审批 三个工作日",
    "费用报销制度 打款时间"
  ],
  "keyword_queries": [
    "报销 打款",
    "费用报销 付款",
    "审批通过 三个工作日"
  ],
  "sub_questions": [],
  "filters": {},
  "must_include_terms": ["报销"],
  "rewrite_strategy": "normalize_expand"
}
```

### 2.2 腾讯 ima 可参考的产品思路

从腾讯 ima 官网和公开介绍看，ima.copilot 的公开定位是“以知识库为核心的 AI 工作台”，强调“搜、读、写一体”，并接入腾讯混元和 DeepSeek R1。公开页面能看到“对话模式”“知识库”“问答历史”“生成报告/PPT/播客”等入口。

这对本项目的启发不是照搬 UI，而是借鉴它的工作台式信息流：

```text
用户自然语言任务
  -> 判断任务类型
  -> 围绕知识库进行搜索和阅读
  -> 必要时做任务拆解
  -> 汇总为回答、报告或其他输出
```

对 Query 改写来说，ima 的可借鉴点是：

- 知识库优先：企业私有知识应先被检索、引用和解释。
- 搜读写一体：检索 query 不只服务“问答”，也应服务后续报告、PPT、摘要等任务。
- 多端和历史会话：后续要支持基于会话上下文的独立问题改写。
- 共享知识库/个人知识库：后续 query rewrite 必须携带权限和知识库空间过滤条件。
- 工具化任务入口：生成报告、生成 PPT 这类任务天然需要 query decomposition，而不是单次检索。

注意：ima 的内部检索和 query rewrite 实现没有公开细节，本方案只参考其公开产品定位和交互形态，不假设其内部算法。

## 3. 本项目推荐架构

### 3.1 Query 改写放在哪一层

推荐放在 Tools / RAG 层，也就是 `KnowledgeSearchTool` 内部或其前置服务中：

```text
Planner
  -> Executor
  -> KnowledgeSearchTool
       -> QueryRewriteService
       -> MultiQueryRetriever
       -> ResultFusion
  -> ReAct Agent
```

原因：

- Planner 只负责“要不要检索”和高层路线，不应该塞复杂检索策略。
- Executor 负责稳定执行、超时、重试、日志，不负责理解 query。
- ReAct Agent 可以提出工具参数，但工具层要兜底改写，不能完全相信 Agent 生成的单个 query。
- Query 改写属于 RAG 检索质量治理，和 embedding、rerank、hybrid search 一起演进最合理。

### 3.2 新增模块建议

```text
backend/ai_service/retrieval/
  query_rewriter.py        # 生成 QueryRewritePlan
  result_fusion.py         # 多查询结果融合、去重、RRF
  search_pipeline.py       # 可选：封装 rewrite -> retrieve -> fuse

backend/ai_service/tools/
  knowledge_search_tool.py # 调用 query_rewriter + vector_store
```

第一版也可以只新增 `query_rewriter.py`，把融合逻辑先放在 `knowledge_search_tool.py`，避免过度拆分。

## 4. QueryRewritePlan 数据结构

建议定义一个明确的数据结构，而不是在工具里传散乱字符串：

```python
@dataclass(frozen=True)
class QueryRewritePlan:
    original_query: str
    standalone_query: str
    semantic_queries: list[str]
    keyword_queries: list[str]
    sub_questions: list[str]
    filters: dict[str, str]
    must_include_terms: list[str]
    rewrite_strategy: str
    needs_clarification: bool = False
    clarification_reason: str = ""
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `original_query` | 用户原始问题或 Agent 工具输入 |
| `standalone_query` | 消解口语、指代后的完整问题 |
| `semantic_queries` | 用于 dense embedding 的自然语言查询 |
| `keyword_queries` | 用于未来 BM25 / 稀疏检索 / fallback 的关键词查询 |
| `sub_questions` | 多意图问题拆出来的子问题 |
| `filters` | 时间、部门、文档名、知识库空间、权限等过滤线索 |
| `must_include_terms` | 融合后用于降噪的核心词 |
| `rewrite_strategy` | 便于 trace 和评估，例如 `rule`, `llm`, `hybrid` |
| `needs_clarification` | 是否问题太模糊，需要追问 |

## 5. 第一版实现范围

第一版建议做“低风险、低成本、可测试”的混合方案：

```text
规则改写为主
  + 轻量多查询扩展
  + 子问题拆解
  + RRF 融合
  + Trace 记录
```

### 5.1 规则改写

规则改写适合当前项目，因为：

- 不增加额外 LLM 调用成本。
- 不改变现有测试里 FakeChatClient 的调用次数。
- 对常见企业制度问答非常有效。
- 行为稳定，便于单元测试。

规则示例：

```text
报销多久到账
  -> 员工费用报销审批通过后多久打款
  -> 费用报销 付款周期 财务审批

差旅标准
  -> 差旅费用标准 出差住宿 交通 补贴

权限怎么申请
  -> IT 资源账号权限申请流程 审批
```

建议维护一个小型企业术语表：

```python
ENTERPRISE_SYNONYMS = {
    "报销": ["费用报销", "报销流程", "打款", "付款", "财务审批"],
    "差旅": ["出差", "差旅标准", "住宿标准", "交通补贴"],
    "权限": ["账号权限", "IT资源", "权限申请", "审批流程"],
    "竞业": ["保密", "竞业限制", "竞业规范"],
}
```

### 5.2 多查询生成

对每个问题至少生成 3 类查询：

```text
1. 原始 query
2. 规范化 query
3. 术语扩展 query
4. 子问题 query，可选
```

例如：

```text
用户：差旅和报销分别谁审批，有什么区别？

semantic_queries:
  - 差旅审批流程和费用报销审批流程有什么区别
  - 出差申请审批人 差旅制度
  - 费用报销审批人 报销制度

sub_questions:
  - 差旅申请由谁审批
  - 费用报销由谁审批
  - 差旅制度和报销制度的区别是什么
```

### 5.3 多路检索与融合

当前向量库接口是：

```python
vector_store.search(query, top_k)
```

改造后：

```text
for query in rewrite_plan.semantic_queries:
    results += vector_store.search(query, top_k=per_query_top_k)

fused = reciprocal_rank_fusion(results_by_query)
deduped = dedupe_by_chunk_id(fused)
return top_k
```

RRF 公式：

```text
score = sum(1 / (k + rank_i))
```

其中 `k` 一般取 60。最终分数可以结合原始相似度：

```text
final_score = 0.7 * normalized_vector_score + 0.3 * rrf_score
```

第一版可以更简单：

```text
同一个 chunk 被多个 query 命中 -> 加权提分
同一个 chunk 只被一个 query 命中 -> 保留原始分
按 fused_score 排序取 top_k
```

### 5.4 Trace 与 sources 增强

建议在 `ToolResult.metadata` 中返回改写信息：

```json
{
  "query_rewrite": {
    "original_query": "报销多久到账",
    "standalone_query": "员工费用报销审批通过后多久打款",
    "semantic_queries": ["..."],
    "rewrite_strategy": "rule",
    "retrieved_queries": 3
  }
}
```

在 `sources` 里可选增加：

```json
{
  "matched_query": "费用报销 付款周期 财务审批",
  "fused_score": 0.83
}
```

这样后续前端可以在调试面板展示“系统实际检索了哪些 query”。

## 6. 第二版增强范围

第二版再引入 LLM 改写，但必须可配置：

```text
QUERY_REWRITE_MODE=off|rule|llm|hybrid
QUERY_REWRITE_MAX_QUERIES=5
QUERY_REWRITE_TIMEOUT_SECONDS=8
```

推荐默认：

```text
开发环境：rule
生产环境：hybrid，但失败自动回退 rule
```

LLM 改写只输出 JSON，不直接执行检索：

```json
{
  "standalone_query": "...",
  "semantic_queries": ["...", "..."],
  "keyword_queries": ["...", "..."],
  "sub_questions": ["...", "..."],
  "filters": {
    "year": "2026",
    "document_type": "policy"
  },
  "needs_clarification": false
}
```

Prompt 要强调：

- 不回答用户问题。
- 不编造事实。
- 只改写成检索 query。
- 不输出权限条件，权限由后端系统注入。
- query 数量受限。

## 7. 企业级边界要求

Query 改写不能绕开企业系统边界：

| 边界 | 要求 |
| --- | --- |
| 权限 | 用户能查哪些知识库、文档、部门，必须由后端权限系统决定，不能由 LLM 决定 |
| 审计 | 记录 original query、rewritten queries、命中文档、耗时、用户 ID |
| 成本 | query 数量、LLM 改写超时、最大召回数必须有限制 |
| 降级 | LLM 改写失败时必须回退原始 query 或规则 query |
| 安全 | 改写不得扩大用户意图到敏感范围，例如把“我的工资”扩展到“全员薪资表” |
| 可解释 | 前端/日志能看到检索 query 和命中来源 |

## 8. 与当前代码的落点

当前最小改造路径：

1. 新增 `backend/ai_service/retrieval/query_rewriter.py`
2. 在 `KnowledgeSearchTool.run()` 中调用 rewriter。
3. 对 `semantic_queries` 多次调用 `vector_store.search()`。
4. 对结果按 `chunk.id` 去重并融合分数。
5. `ToolResult.metadata` 返回改写计划。
6. 增加单元测试。

不建议第一版改这些地方：

- 不改 Planner 的路由职责。
- 不改 ReAct Agent 的工具循环协议。
- 不改 VectorStore 的公共接口。
- 不引入新的框架依赖。
- 不做 HyDE。
- 不做完整 BM25 服务，除非后续决定上混合检索。

## 9. 测试方案

### 9.1 单元测试

新增：

```text
tests/retrieval/test_query_rewriter.py
tests/tools/test_knowledge_search_rewrite.py
```

重点用例：

| 用例 | 期望 |
| --- | --- |
| “报销多久到账” | 扩展出“费用报销”“打款”“审批通过”等 query |
| “差旅和报销有什么区别” | 拆出两个或三个子问题 |
| “2026 年 Q2 差旅标准” | 提取年份/季度过滤线索 |
| 英文问题 | 保留英文 query，不强行中文化 |
| 空问题 | 不检索，返回空结果 |
| 多 query 命中同一 chunk | 结果去重，融合分数提升 |

### 9.2 端到端验证

用 `test-split/` 里的企业样例文档做固定问题集：

```text
1. 报销多久可以打款？
2. 出差住宿标准是多少？
3. 竞业限制有哪些要求？
4. IT 权限怎么申请？
5. 客户支持 FAQ 里退换货怎么处理？
6. 差旅制度和报销制度有什么区别？
```

记录改造前后：

| 指标 | 说明 |
| --- | --- |
| Recall@K | 标准答案对应文档是否进入 top_k |
| Source hit rate | 最终 sources 是否包含目标文档 |
| Answer groundedness | 回答是否基于引用，不乱编 |
| Latency | 多 query 后耗时增加多少 |
| Empty retrieval rate | 未命中率是否下降 |

## 10. 迭代路线

### P0：方案落地前准备

- 保留本文档。
- 梳理 `test-split/` 样例问题和标准命中文档。
- 确认是否需要前端展示 rewritten query。

### P1：规则改写 + 多路融合

- 实现 `QueryRewritePlan` 和规则 rewriter。
- 接入 `KnowledgeSearchTool`。
- 实现简单 RRF / 去重融合。
- 返回 `ToolResult.metadata["query_rewrite"]`。
- 增加单元测试。

### P2：会话上下文改写

- 从 `MemoryService` 中取最近 N 轮。
- 支持“它/这个/刚才那个”的 standalone question 改写。
- 对多轮追问增加测试。

### P3：LLM 结构化改写

- 新增 `QUERY_REWRITE_MODE`。
- 接入 chat client 做 JSON 改写。
- 失败自动回退规则改写。
- 增加超时和成本控制。

### P4：混合检索和 Rerank

- 增加 BM25 / 稀疏检索。
- 对 dense + sparse 结果做 RRF。
- 引入 rerank 模型重排最终上下文。
- 建立检索评估脚本。

## 11. 推荐第一版最终链路

```text
用户问题
  -> Planner 判断需要知识库
  -> Executor 调用 knowledge_search
  -> QueryRewriteService
       1. 规范化问题
       2. 术语扩展
       3. 子问题拆解
       4. 输出 QueryRewritePlan
  -> VectorStore 多 query 检索
  -> ResultFusion 去重融合
  -> ReAct Agent 基于融合证据回答
  -> Trace / Sources 返回改写和命中信息
```

这条路线适合当前项目：改动小、风险低、可测试，并且和后续企业级权限、多知识库、混合检索、rerank、ima 式知识工作台演进方向一致。

## 12. 参考资料

- LangChain Blog: Query Transformations  
  https://blog.langchain.dev/query-transformations/
- LangChain Blog: RAG Fusion  
  https://blog.langchain.dev/rag-fusion/
- LlamaIndex Docs: Query Transformations  
  https://docs.llamaindex.ai/en/stable/optimizing/advanced_retrieval/query_transformations/
- Haystack Blog: Query Decomposition & Reasoning  
  https://haystack.deepset.ai/blog/query-decomposition
- Azure AI Search: Query Rewrites in Semantic Ranker  
  https://learn.microsoft.com/en-us/azure/search/semantic-how-to-query-rewrite
- 腾讯 ima 官网  
  https://ima.qq.com/
- 腾讯 ima 官网描述中公开定位：以知识库为核心的 AI 工作台、搜读写一体、接入混元和 DeepSeek R1  
  https://ima.qq.com/
- 公开 RAG 方案对比文章：自建知识库 vs 腾讯 IMA vs Google AI Notebook  
  https://www.53ai.com/news/RAG/2025022447682.html
