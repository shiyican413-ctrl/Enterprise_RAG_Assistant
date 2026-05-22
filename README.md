# Enterprise RAG Assistant

面向企业内部知识库、制度查询、产品资料问答和客服辅助场景的 RAG 智能问答平台。

当前仓库已从方案文档进入开发阶段，已落地 `FastAPI AI Service MVP` 和 `Next.js 企业前端控制台`，用于验证完整 RAG 主链路：

```text
文档上传 -> 文本解析 -> 文本切分 -> 本地知识库持久化 -> 相似度检索 -> 带引用问答 -> 会话历史
```

## 项目结构

```text
backend/
  ai_service/
    api/                 FastAPI 路由和请求模型
    loaders/             文档解析
    services/            RAG、知识库、检索、会话服务
    config.py            配置
    main.py              FastAPI 入口
frontend/
  next-web/
    app/                 Next.js App Router 页面与全局样式
    lib/                 前端 API 调用封装
data/
  sample_policy.txt      示例企业制度文档
  uploads/               上传文件目录
  knowledge_base/        本地索引和历史记录
docs/
  部署与启动说明.md
requirements.txt
项目架构与功能方案.md
```

## 后端快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.ai_service.main:app --reload --host 127.0.0.1 --port 8000
```

可以在项目根目录创建本地 `.env` 配置 GLM Embedding：

```text
GLM_API_KEY=your-glm-api-key
GLM_EMBEDDING_MODEL=embedding-3
GLM_EMBEDDING_URL=https://open.bigmodel.cn/api/paas/v4/embeddings
GLM_CHAT_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
GLM_FAST_MODEL=GLM-4V-Flash
GLM_THINKING_MODEL=GLM-4.1V-Thinking-Flash
```

当前使用 PostgreSQL + pgvector 作为知识库和会话存储，在 `.env` 中配置：

```text
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/enterprise_rag
```

首次启动时服务会自动执行 `CREATE EXTENSION IF NOT EXISTS vector`，并创建 `documents`、`document_chunks`、`chat_turns` 表。数据库需要提前创建好，并安装 pgvector 扩展。上传入库需要配置 `GLM_API_KEY`，用于生成 pgvector 检索所需的 embedding。

打开 `http://127.0.0.1:8000/docs` 查看接口文档。

## 前端快速开始

```bash
cd frontend/next-web
npm install
npm run dev
```

打开 `http://127.0.0.1:3000` 查看企业 RAG 助手控制台。

默认前端会连接：

```text
http://127.0.0.1:8000
```

如需修改后端地址，可以设置：

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 示例调用

上传示例制度文档：

```bash
curl -X POST "http://127.0.0.1:8000/api/documents/upload" ^
  -F "file=@data/sample_policy.txt"
```

提问：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat/ask" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"报销多久可以打款？\"}"
```

## 当前实现说明

当前版本已支持 GLM `embedding-3` 嵌入模型和 GLM Chat Completions 回答生成。配置 `GLM_API_KEY` 后，文档入库会保存 2048 维 dense embedding，问答检索会优先使用向量相似度，并把检索片段交给聊天模型生成带引用编号的回答；前端问答默认使用 `/api/chat/stream` 进行真正的流式输出。未配置 Key 时会自动降级到纯 Python 本地稀疏检索和模板回答，方便离线开发。

- `vector_store_service.py` 后续可继续替换为 Chroma、pgvector 或 Qdrant。
- `rag_service.py` 已支持快速模式 `GLM-4V-Flash` 和思考模式 `GLM-4.1V-Thinking-Flash`。
- `routes.py` 已提供普通问答和真正的 SSE 流式问答接口，方便 Next.js 前端对接。
- `frontend/next-web` 已提供知识库上传、智能问答、文档列表、引用来源和服务状态展示。

## 开发路线

1. FastAPI RAG 核心链路。
2. GLM Embedding-3 接入。
3. Next.js 企业前端。
4. Chroma、pgvector 或 Qdrant 向量库。
5. Django 用户、权限、文档元数据和日志后台。
6. Agent 工具调用、Dify 对照和 CrewAI 扩展。
