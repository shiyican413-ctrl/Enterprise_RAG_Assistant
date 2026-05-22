# Enterprise RAG Assistant

面向企业内部知识库、制度查询、产品资料问答和客服辅助场景的 RAG 智能问答平台。

当前仓库已从方案文档进入开发阶段，第一版先落地 `FastAPI AI Service MVP`，用于验证完整 RAG 主链路：

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
data/
  sample_policy.txt      示例企业制度文档
  uploads/               上传文件目录
  knowledge_base/        本地索引和历史记录
docs/
  08_部署与启动说明.md
requirements.txt
项目架构与功能方案.md
```

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.ai_service.main:app --reload --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/docs` 查看接口文档。

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

第一版为了让开发不被外部模型 Key 和向量数据库安装卡住，先使用纯 Python 本地稀疏向量检索与模板化回答。它已经保留了清晰替换点：

- `vector_store_service.py` 后续可替换为 Chroma、pgvector 或 Qdrant。
- `rag_service.py` 后续可接入通义千问、Ollama 或 OpenAI Compatible API。
- `routes.py` 已提供普通问答和 SSE 流式问答接口，方便 Next.js 前端对接。

## 开发路线

1. FastAPI RAG 核心链路。
2. 真实 Embedding 与 Chroma 向量库。
3. Next.js 企业前端。
4. Django 用户、权限、文档元数据和日志后台。
5. Agent 工具调用、Dify 对照和 CrewAI 扩展。
