# Enterprise RAG Assistant

面向企业内部资料、制度查询、产品知识和客服辅助场景的 RAG 智能问答平台。项目当前已经形成一个可运行的前后端 MVP：后端使用 FastAPI 提供文档入库、向量检索、流式问答和会话存储能力；前端使用 Next.js 构建企业知识库智能问答控制台。

核心链路：

```text
文档上传 -> 文本解析 -> 文本切分 -> PostgreSQL/pgvector 入库 -> 相似度检索 -> 流式问答 -> 引用追溯 -> 会话记录
```

## 界面预览

### 智能问答首页

上传企业资料后，可以直接在问答区提问；右侧知识库面板展示文档数、片段数、引用数、入库入口和最近文档。

![智能问答首页](docs/images/chat-empty.png)

### 带引用的问答结果

问答页支持快速模式和思考模式，默认通过 SSE 接收流式回答，并展示本次检索命中的企业资料引用数量。

![带引用的问答结果](docs/images/chat-answer.png)

### 知识库管理页

独立的知识库页面支持查看文档总数、片段总数、索引状态、最近入库时间，并提供搜索、筛选、查看片段、复制 ID、删除文档和重建索引等管理操作。

![知识库管理页](docs/images/knowledge-page.png)

## 当前能力

- 文档入库：支持 `.txt`、`.md`、`.csv`、`.json`、`.pdf` 文件上传、解析、切分和入库。
- 语义检索：配置 `GLM_API_KEY` 后使用 GLM `embedding-3` 生成 dense embedding，并写入 PostgreSQL + pgvector。
- 降级检索：未配置模型 Key 时保留本地稀疏检索和模板回答能力，便于离线开发和链路验证。
- 智能问答：支持普通问答接口和 SSE 流式问答接口，返回回答正文、引用来源、会话 ID、回答模式和模型信息。
- 双回答模式：快速模式使用 `GLM-4V-Flash`，思考模式使用 `GLM-4.1V-Thinking-Flash`。
- 会话记录：问答历史写入 PostgreSQL，可按 `conversation_id` 查询。
- 知识库管理：前端已提供文档列表、搜索筛选、片段查看、删除文档、上传文档和重建索引入口。

## 项目结构

```text
backend/
  ai_service/
    api/                 FastAPI 路由和请求/响应模型
    loaders/             TXT/Markdown/CSV/JSON/PDF 文档解析
    services/            RAG、知识库、检索、模型和会话服务
    config.py            环境变量、模型和切分参数配置
    main.py              FastAPI 应用入口
frontend/
  next-web/
    app/                 Next.js App Router 页面
    components/          聊天、侧边栏、知识库和基础 UI 组件
    lib/                 前端 API 调用封装
data/
  uploads/               上传文件目录
  knowledge_base/        本地降级索引和历史记录目录
docs/
  images/                README 截图
  *.md                   架构、部署和页面设计文档
test-split/              用于测试入库的企业资料样例
tests/                   后端测试
requirements.txt         Python 依赖
```

## 环境配置

后端会读取项目根目录下的 `.env`。PostgreSQL/pgvector 是当前主要存储方式，需要先创建数据库并安装 pgvector 扩展。

```text
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/enterprise_rag

GLM_API_KEY=your-glm-api-key
GLM_EMBEDDING_MODEL=embedding-3
GLM_EMBEDDING_URL=https://open.bigmodel.cn/api/paas/v4/embeddings
GLM_CHAT_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
GLM_FAST_MODEL=GLM-4V-Flash
GLM_THINKING_MODEL=GLM-4.1V-Thinking-Flash
```

首次启动时服务会自动执行 `CREATE EXTENSION IF NOT EXISTS vector`，并创建 `documents`、`document_chunks`、`chat_turns` 表。使用 pgvector 入库时需要配置 `GLM_API_KEY`，否则无法生成向量。

## 后端启动

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.ai_service.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- 健康检查：`http://127.0.0.1:8000/health`
- Swagger 文档：`http://127.0.0.1:8000/docs`

## 前端启动

```bash
cd frontend/next-web
npm install
npm run dev
```

启动后访问 `http://127.0.0.1:3000`。前端默认连接 `http://127.0.0.1:8000`，如需修改可在 `frontend/next-web/.env.local` 中配置：

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 常用接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| POST | `/api/documents/upload` | 上传并入库文档 |
| GET | `/api/documents` | 查看知识库文档列表 |
| GET | `/api/documents/{document_id}/chunks` | 查看指定文档的知识片段 |
| DELETE | `/api/documents/{document_id}` | 删除文档及其片段索引 |
| POST | `/api/knowledge/rebuild` | 根据 `data/uploads` 重建知识库 |
| POST | `/api/chat/ask` | 普通问答 |
| POST | `/api/chat/stream` | SSE 流式问答 |
| GET | `/api/chat/conversations/{conversation_id}` | 获取会话历史 |

## 示例调用

上传示例文档：

```bash
curl -X POST "http://127.0.0.1:8000/api/documents/upload" ^
  -F "file=@data/sample_policy.txt"
```

发起问答：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat/ask" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"报销多久可以打款？\",\"answer_mode\":\"fast\"}"
```

流式问答事件顺序：

```text
answer_delta -> answer_delta -> sources -> done
```

其中 `sources` 包含引用文档、片段内容、片段序号和匹配分数，前端会用它展示引用追溯信息。

## 开发与验证

后端测试：

```bash
pytest
```

前端类型检查：

```bash
cd frontend/next-web
npm run typecheck
```

前端生产构建：

```bash
cd frontend/next-web
npm run build
```

## 后续方向

1. 补齐登录、用户角色、文档权限和审计日志。
2. 增加多租户、部门标签、文档元数据和更细粒度的访问控制。
3. 引入 rerank、混合检索、召回质量评估和引用命中统计。
4. 扩展 OpenAI Compatible API、Ollama、DashScope 等模型服务适配。
5. 将当前单页工作台继续拆分为会话记录、权限审计、模型配置、系统设置和 Agent 工具页面。
