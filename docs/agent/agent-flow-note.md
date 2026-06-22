# Enterprise RAG Assistant — Agent 流程架构笔记

> 本文档详细梳理了项目的智能体（Agent）完整工作流程，从用户输入到最终回答的全链路。

> 定位说明：本项目目标是企业级 RAG 智能问答平台，不是 MVP 或一次性 Demo。Planner、Executor、ReAct Agent、Tool Registry、Trace 和分层 SSE 事件用于支撑企业场景下的可观测、可审计、可扩展和可治理能力。

---

## 一、整体架构概览

```
┌────────────────────────────────────────────────────────────────────────┐
│                          前端 (Next.js)                                 │
│  page.tsx → chat-panel.tsx → lib/api.ts (SSE ReadableStream)            │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ POST /api/chat/stream
                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       后端 (FastAPI)                                    │
│  routes.py → OrchestratorService → ChatWorkflow                        │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
    规划层 (Planner)    执行层 (Executor)   命令层 (Answer Gen)
```

**核心技术栈**：
- **LLM**: 阿里云百炼（快速 `qwen3.5-flash` / 思考 `qwen3.7-plus`）— 通过 OpenAI 兼容 API 调用
- **Embedding**: 通义千问 DashScope (text-embedding-v4, 2048维)
- **向量存储**: Milvus (COSINE 向量相似度检索)
- **对话历史**: PostgreSQL (`chat_turns` 表)

---

## 二、服务组合根：OrchestratorService

`orchestrator_service.py` 是整个系统的**组装入口**，负责将所有服务组装在一起：

```python
OrchestratorService
  ├── MilvusVectorStore            # 向量存储 (Milvus)
  ├── PostgresHistoryService       # 对话历史存储
  ├── BailianChatClient            # LLM 客户端（阿里云百炼）
  ├── TraceService                 # 全链路追踪
  ├── MemoryService                # 会话记忆 (包装 HistoryService)
  ├── PlannerService               # 规划层 (包装 ChatClient)
  ├── ToolRegistry([KnowledgeSearchTool])  # 工具注册表
  ├── ExecutorService              # 执行层 (包装 ToolRegistry + ChatClient + TraceService)
  ├── GuardrailService             # 输入安全校验
  └── ChatWorkflow                 # 固定状态流水线 (包装 Memory + Planner + Executor + Trace + Guardrails)
```

两个对外入口：
- `handle_chat()` → 同步模式，返回完整 dict
- `stream_chat()` → 异步流式模式，yield SSE 事件（**实际使用的主路径**）

---

## 三、三层流水线：ChatWorkflow

`workflow_service.py` 实现了固定的**应用状态流**（无模型调用逻辑在此层）：

### Phase 1 — Guardrails（输入安全校验）

**服务**: `GuardrailService` (`guardrail_service.py`)

**触发时机**: 用户输入进入流水线的第一关

**校验规则**:
| 规则 | 条件 | 结果 |
|------|------|------|
| 非空检查 | question 为空或仅空白 | 拒绝 |
| 长度限制 | question > 8000 字符 | 拒绝 |

**SSE 事件**:
```
→ phase: { layer: "guardrails", status: "start", label: "输入安全校验" }
→ route_step: { step: "guardrails.input", status: "ok", duration_ms: 0.12 }
→ phase: { layer: "guardrails", status: "done", label: "输入安全校验" }
```

---

### Phase 2 — Memory（加载会话记忆）

**服务**: `MemoryService` (`memory_service.py`) → `PostgresHistoryService`

**作用**: 从 PostgreSQL 中加载该 `conversation_id` 的历史对话轮次，为后续规划和执行提供上下文

**流程**:
1. 接收 `conversation_id`（首次对话时为 null）
2. 调用 `HistoryService.get_conversation(conversation_id)` 获取历史
3. 返回 `memory_context: list[dict]`（每项包含 question / answer / sources）

**SSE 事件**:
```
→ phase: { layer: "memory", status: "start", label: "加载会话记忆" }
→ route_step: { step: "memory.load", status: "ok", duration_ms: 15.3 }
→ phase: { layer: "memory", status: "done", label: "加载会话记忆" }
```

---

### Phase 3 — Planner（规划层）

**服务**: `PlannerService` (`planner_service.py`)

**作用**: 根据问题的复杂度和对话历史，决定执行路线（Plan）

#### 规划策略选择逻辑

```
_should_use_llm(question, memory)?
│
├─ enable_llm_planning == False  →  使用规则策略
├─ chat_client 未启用            →  使用规则策略
│
├─ 问题长度 > 120 字符           →  使用 LLM 策略
├─ 历史轮次 >= 3                  →  使用 LLM 策略
├─ 包含复杂标记词                 →  使用 LLM 策略
│   (compare/summarize/analyze/plan/steps/
│    multiple/difference/why/how should)
│
└─ 否则                           →  使用规则策略
```

#### 策略 A：规则策略 (rule) — 默认

固定生成 **3 个步骤**：

| 步骤名 | step_type | 说明 |
|--------|----------|------|
| `agent.answer` | `agent_answer` | 运行 ReAct 智能体 |
| `tool.knowledge_search` | `knowledge_search` | 知识库检索（fallback） |
| `model.answer` | `answer_generation` | LLM 生成最终回答（fallback） |

`rationale`: `"Default enterprise RAG route."`

#### 策略 B：LLM 策略 (llm) — 复杂问题

调用豆包 LLM（temperature=0.0）动态生成 Plan：

```
System: "You are a planning module for an enterprise RAG system.
         Return exactly one JSON object. Do not execute tools.
         Allowed step types are: agent_answer, knowledge_search, answer_generation.
         Keep plans short and deterministic."

User: "Question: {question}
       Answer mode: {answer_mode}
       Memory turns available: {len(memory)}

       Return JSON shape:
       {"rationale":"...","steps":[{"name":"agent.answer",
        "step_type":"agent_answer","input":{}}]}"
```

LLM 返回的 steps 会经过校验：只有 `agent_answer` / `knowledge_search` / `answer_generation` 三种 type 会被保留。

**SSE 事件**:
```
→ phase: { layer: "planner", status: "start", label: "规划层 · 分析问题并制定路线" }
→ route_step: { step: "planner.create_plan", ... }
→ plan: { strategy: "rule"|"llm", rationale: "...", steps: [...] }
→ phase: { layer: "planner", status: "done", label: "规划层 · 分析问题并制定路线" }
```

---

### Phase 4 — Executor（执行层）

**服务**: `ExecutorService` (`executor_service.py`)

**作用**: 按照 Planner 产出的 Plan 逐步执行，包含 ReAct Agent 推理、知识检索、答案生成三个子阶段

#### Step 4.1：ReAct Agent 推理 (`agent_answer`)

**核心类**: `ReActAgent` (`agent_service.py`)

**关键设计**: 采用 **Prompt-based ReAct**（非原生 tool-calling），通过 JSON 格式的 prompt 指导模型做推理，模型无关。

**Agent 循环机制** (最多 4 步):

```
for _ in range(max_steps=4):
    1. 构建消息 (_build_messages)
       - System: 角色 + Action/Final JSON 格式 + 可用工具列表
       - User: 问题 + 回答模式 + 历史步骤 + 指令

    2. 调用 LLM (chat_client.complete)

    3. 解析决策 (_parse_decision)
       ├─ JSON 解析成功:
       │   ├─ type == "action" → 执行工具调用
       │   └─ type == "final"  → 返回最终答案
       └─ JSON 解析失败 → 视为纯文本最终答案

    4a. 如果是 action:
        - 查找工具 → tool.run(action_input)
        - 生成 AgentStep(thought, action, action_input, observation)
        - yield { type: "thought", step }
        - 继续循环

    4b. 如果是 final:
        - yield { type: "thought", step }
        - yield { type: "final", run: AgentRun(...) }
        - 结束循环

强制终结: 如果 4 步内未返回 final →
    发送 force_final=True 的消息，LLM 必须返回最终答案
```

**System Prompt 全文**:
```
You are an enterprise RAG ReAct agent. Use tools when the answer
depends on private knowledge. Do not invent facts outside tool
observations. Respond with exactly one JSON object and no markdown.

Action JSON shape:
{"type":"action","thought":"...","action":"tool_name","action_input":{"query":"..."}}

Final JSON shape:
{"type":"final","thought":"...","answer":"..."}

Available tools:
- knowledge_search: Search the enterprise knowledge base.
  Input JSON: {"query":"user question or focused search query"}.
```

**两种回答模式对 Agent 的影响**:

| 模式 | Temperature | 指令 |
|------|-------------|------|
| `fast` | 0.2 | "Give a concise answer in 3 to 6 points." |
| `thinking` | 0.1 | "Analyze carefully, then provide only the final answer to the user." |

**SSE 事件** (每个 Agent 步骤实时推送):
```
→ phase: { layer: "agent", status: "start", label: "执行层 · 智能体推理与检索" }
→ agent_step: { thought: "需要搜索知识库...", action: "knowledge_search", action_input: {query: "..."}, observation: "[1] 文档名 chunk 0: ..." }
→ agent_step: { thought: "已有足够信息", action: null, observation: null }  (final step)
→ route_step: { step: "agent.answer", status: "ok", duration_ms: 2340.5 }
→ phase: { layer: "agent", status: "done", label: "执行层 · 智能体推理与检索" }
```

#### Step 4.2：知识库直接检索 (`knowledge_search`) — Fallback

**触发条件**: Agent 运行完毕后 `sources` 为空 AND Plan 包含 `knowledge_search` 步骤

**执行**:
```python
search_result = ToolRegistry.run("knowledge_search", {"query": question}, tool_context)
# → KnowledgeSearchTool.run()
#   → VectorStore.search(query, top_k)  # Milvus 向量检索
#   → 返回 ToolResult(content=evidence, sources=[...], raw_results=[...])
```

**知识检索格式** (返回给 Agent / LLM 的 evidence):
```
[1] 企业管理制度.docx chunk 0: 公司实行弹性工作制...
[2] 产品手册v3.pdf chunk 5: 系统支持单点登录...
[3] FAQ汇总.md chunk 2: 年假标准为工作满一年...
```

**Source 结构** (返回给前端的引用):
```python
{
    "document_id": "uuid",
    "document_name": "企业管理制度.docx",
    "chunk_id": "uuid",
    "chunk_index": 0,
    "snippet": "公司实行弹性工作制...",  # 前360字符
    "score": 0.8523,
    "metadata": {}
}
```

#### Step 4.3：答案生成 (`answer_generation`) — 命令层

**触发条件**: `answer` 为空 AND Plan 包含 `answer_generation` 步骤

**三种生成路径** (按优先级):

```
路径 A: Agent 已产出答案
  → 逐字符 chunk_text(answer, size=48) 推送
  → 每个 chunk 48 字符

路径 B: 有检索结果 + LLM 可用
  → 调用 chat_client.stream_complete() 流式生成
  → System: "You are an enterprise RAG assistant. Answer strictly
             from the provided evidence. Do not invent facts outside
             the evidence. Cite key claims with references [1] [2]..."
  → User: answer_mode + mode_instruction + question + evidence
  → 逐 token 推送 answer_delta

路径 C: 全部失败 — 模板兜底
  → build_template_answer() 拼接原始 chunk 片段
  → "Based on the most relevant knowledge base content, here is what
     I found for '...':\n1. chunk片段1\n2. chunk片段2\n..."
```

**错误处理**:
- LLM 流式中途失败 → 保留已输出部分 + 追加错误提示
- LLM 完全不可用 → 降级到路径 C + 追加错误原因

**SSE 事件**:
```
→ phase: { layer: "answer", status: "start", label: "命令层 · 生成最终回答" }
→ answer_delta: { content: "根据企业知识库..." }
→ answer_delta: { content: "公司实行弹性工作..." }
→ answer_delta: { content: "制度规定..." }
→ route_step: { step: "model.answer", status: "ok", duration_ms: 1850.2 }
→ phase: { layer: "answer", status: "done", label: "命令层 · 生成最终回答" }
→ executor_result: { answer: "完整答案...", sources: [...], model: "qwen3.7-plus" }
```

---

### Phase 5 — Memory（保存对话）

**作用**: 将本轮的问答追加到 PostgreSQL 对话历史

```python
MemoryService.append_turn(question, answer, sources, conversation_id)
→ HistoryService.append_message(conversation_id, role="user", content=question)
→ HistoryService.append_message(conversation_id, role="assistant", content=answer, sources=sources)
```

**SSE 事件**:
```
→ route_step: { step: "memory.append_turn", status: "ok", duration_ms: 8.7 }
→ sources: { content: [{ document_name, snippet, score, ... }] }
→ done: { conversation_id, trace_id, answer_mode, model, route: [...] }
```

---

## 四、优雅降级策略（Fallback Chain）

系统设计了 **4 层 fallback**，确保即使部分组件失败也能返回有用答案：

```
Layer 1: ReAct Agent 推理
  │     Agent 可能直接回答（不调用工具），也可能调用工具后回答
  ├─ 成功 → 直接使用 Agent 的 answer + sources
  │
  ▼ Layer 2: 知识库直接检索
  │     Agent 未找到 sources 时触发
  ├─ 成功 → 拿到检索结果，进入 Layer 3 生成
  │
  ▼ Layer 3: LLM 答案生成
  │     用检索到的 evidence 让 LLM 生成结构化回答
  ├─ 成功 → 流式输出最终回答
  │
  ▼ Layer 4: 模板兜底
        LLM 不可用或完全无结果时
        → 拼接原始 chunk 片段返回
```

---

## 五、工具系统

### 工具协议

```python
class Tool(Protocol):
    name: str
    description: str
    def run(self, payload: dict, context: ToolContext) -> ToolResult: ...

@dataclass
class ToolContext:
    trace_id: str
    top_k: int
    metadata: dict | None = None

@dataclass
class ToolResult:
    content: str           # 文本证据
    sources: list[dict]    # 引用来源
    raw_results: list[SearchResult]  # 原始检索结果
    metadata: dict | None  # 附加信息
```

### 工具注册表

`ToolRegistry` 是简单的字典注册机制：
- `register(tool)` — 注册工具
- `get(name)` — 按名称获取
- `run(name, payload, context)` — 执行工具
- `descriptions()` — 返回所有工具的 name + description（用于 Agent prompt）

### 已注册工具

| 工具 | name | 描述 | 实现 |
|------|------|------|------|
| **KnowledgeSearchTool** | `knowledge_search` | 搜索企业知识库 | 调用 `MilvusVectorStore.search(query, top_k)` |
| **MCPToolAdapter** | (动态) | MCP 协议扩展适配器 | 预留接口，暂未使用 |

---

## 六、全链路追踪：TraceService

每个流水线阶段都被 `traced_step` 上下文管理器包裹：

```python
with traced_step(trace_service, trace, "agent.answer"):
    result = agent.run(...)   # 正常完成 → status: "ok"
                             # 异常     → status: "error", error: "..."
```

**追踪数据结构**:
```python
TraceStep:
  name: str              # 步骤名，如 "agent.answer"
  status: str            # "ok" | "error"
  error: str | None      # 错误信息
  duration_ms: float     # 耗时（毫秒）
  started_at: str        # ISO 时间戳
```

**前端展示**: 追踪数据通过 `route_step` 事件实时推送到前端的 **RouteTimeline** 面板。

---

## 七、SSE 事件完整时序图

以一个典型问题 "公司的年假制度是怎样的？" 为例：

```
时间轴    事件类型              数据
─────    ────────              ────
  0ms    phase                  guardrails/start
  1ms    route_step             guardrails.input {ok, 0.12ms}
  1ms    phase                  guardrails/done
  2ms    phase                  memory/start
 17ms    route_step             memory.load {ok, 15.3ms}
 17ms    phase                  memory/done
 18ms    phase                  planner/start
 19ms    route_step             planner.create_plan {ok, 1.2ms}
 19ms    plan                   {strategy:"rule", steps:[agent.answer, knowledge_search, model.answer]}
 19ms    phase                  planner/done
 20ms    phase                  agent/start
       ┌─────────────────────────────────────────────┐
       │  ReAct Agent 推理循环                        │
520ms    │  agent_step  thought:"需要搜索知识库"        │
       │    action: knowledge_search                  │
       │    action_input: {query:"公司年假制度"}        │
890ms    │    observation: "[1] 人事制度 chunk 3: ..."│
       │                                              │
1420ms   │  agent_step  thought:"已找到年假规定"         │
       │    (final, 无 action)                        │
       └─────────────────────────────────────────────┘
1421ms   route_step             agent.answer {ok, 1401ms}
1421ms   phase                  agent/done
         ──── Agent 已有 answer，跳过 knowledge_search ───
1422ms   phase                  answer/start
1423ms   answer_delta           "根据公司人事管理制度的规定"
1460ms   answer_delta           "，员工年假标准如下..."
1500ms   answer_delta           "工作满1年可享受5天..."
1501ms   route_step             model.answer {ok, 78ms}  (复用agent答案)
1501ms   phase                  answer/done
1502ms   executor_result        {answer:"完整答案...", sources:[...]}
1505ms   route_step             memory.append_turn {ok, 3.2ms}
1506ms   sources                [{document_name:"人事制度.docx", snippet:"...", score:0.92}]
1506ms   done                   {conversation_id:"uuid", trace_id:"uuid", model:"qwen3.7-plus"}
```

---

## 八、数据流关键代码路径

### 同步路径 (handle_chat)

```
OrchestratorService.handle_chat()
  → TraceService.start_trace()
  → ChatWorkflow.run_chat()
      → GuardrailService.validate_chat_input()
      → MemoryService.load_context()
      → PlannerService.create_plan()
      → ExecutorService.execute()
          → ReActAgent.run() → [tool calls] → AgentRun
          → ToolRegistry.run("knowledge_search") [fallback]
          → ExecutorService.build_answer() [fallback]
          → build_template_answer() [fallback]
      → MemoryService.append_turn()
  → return {conversation_id, answer, sources, agent_steps, route}
```

### 流式路径 (stream_chat)

```
OrchestratorService.stream_chat()
  → TraceService.start_trace()
  → ChatWorkflow.stream_chat()
      → yield phase/guardrails events
      → yield phase/memory events
      → yield phase/plan events
      → async for event in ExecutorService.stream_execute()
          → yield phase/agent events
          → for item in ReActAgent.run_stream()
              → yield agent_step events (每步实时)
          → yield route_step events
          → yield answer_delta events (逐字符/token)
          → yield executor_result
      → yield phase/memory.append_turn
      → yield sources
      → yield done
```

---

## 九、前端侧处理

### API 调用 (`lib/api.ts`)

```typescript
streamQuestion(request) → fetch("/api/chat/stream") + ReadableStream reader
  逐行解析 SSE data: {...}\n\n
  回调处理不同事件类型 → 更新 React 状态
```

### UI 面板 (`chat-panel.tsx`)

| 面板 | 展示内容 | 对应事件 |
|------|----------|----------|
| **LayerTimeline** | 流水线各阶段状态（running/done） | `phase` |
| **PlanPanel** | 规划策略 + 步骤列表 | `plan` |
| **AgentSteps** | ReAct 推理过程（可展开） | `agent_step` |
| **RouteTimeline** | 每步耗时和状态 | `route_step` |
| **消息气泡** | 最终回答（流式打字效果） | `answer_delta` |
| **引用卡片** | 知识来源 + 摘要 + 相似度 | `sources` |

---

## 十、关键设计决策总结

| 决策 | 方案 | 理由 |
|------|------|------|
| Agent 推理方式 | Prompt-based ReAct (JSON in prompt) | 模型无关，不依赖原生 tool-calling API |
| 最大推理步数 | 4 步 | 平衡成本与效果，超限强制终结 |
| 规划策略 | 规则 + LLM 双模式 | 简单问题快速响应，复杂问题动态规划 |
| 流式粒度 | 48字符/块 (Agent答案) / 单token (LLM生成) | Agent答案是已知文本切块，LLM是原生流 |
| 降级策略 | 4 层 fallback | 任何组件异常都不返回空白 |
| 追踪机制 | 上下文管理器 + 毫秒级计时 | 零侵入，自动记录异常 |
| 工具扩展 | MCPToolAdapter 预留 | 为未来 MCP 协议集成做准备 |
