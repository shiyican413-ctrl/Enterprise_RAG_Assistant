# Enterprise RAG Assistant 优化记录

记录时间：2026-06-27

## 当前验证结果

- 后端测试通过：`pytest`，共 38 项。
- 前端类型检查通过：`npm run typecheck`。
- 前端生产构建通过：`npm run build`。
- `.env` 当前未被 Git 跟踪，状态正确。

## 高优先级优化

1. 收紧生产安全配置

   - `backend/ai_service/main.py` 当前 CORS 使用 `allow_origins=["*"]` 且允许 credentials。生产环境建议改为环境变量白名单。
   - `backend/ai_service/core/config.py` 仍有默认 `JWT_SECRET` 和默认管理员密码。建议生产启动时禁止使用默认值。

2. 上传入库增加资源限制

   - `backend/ai_service/knowledge/service.py` 当前使用 `await file.read()` 一次性读取完整文件。
   - 建议增加 `MAX_UPLOAD_MB`、流式写入、PDF 页数限制、文本长度限制，避免大文件导致内存压力或 embedding 调用异常。

3. 后端错误信息脱敏

   - `backend/ai_service/api/routes/documents.py` 当前上传失败会把异常文本拼接返回给前端。
   - 生产环境建议只返回通用错误文案，详细异常保留在日志和 trace 中。

4. 建立检索质量评估闭环

   - 当前已有 query rewrite、quality report 和 top_k 配置，但缺少可重复评估集。
   - 建议基于 `test-split` 建立 QA golden set，固定评估召回率、引用命中率、无答案拒答率和回答忠实度。

5. 优化 Milvus 大库查询能力

   - `backend/ai_service/retrieval/vector_store.py` 的 `_query_chunks` 固定 `limit=16384`。
   - 文档和片段增长后，列表、删除前查询、重建等操作可能遇到上限或性能问题。
   - 建议增加分页查询，并考虑将文档元数据单独持久化，避免每次通过 chunk 汇总文档列表。

## 中优先级优化

1. 统一 README、脚本和前端端口说明

   - README 文档中写的是后端 `8000`、前端 `3000`。
   - 当前启动脚本和 `frontend/next-web/package.json` 默认使用后端 `8001`、前端 `3001`。

2. 修正 README 截图路径

   - README 使用 `docs/images/...`。
   - 实际图片位于 `docs/assets/images/...`。

3. 增加 `.env.example`

   - 保持真实 `.env` 不入库。
   - 新增安全的 `.env.example`，降低新环境部署成本。

4. 增强前端 SSE 容错

   - `frontend/next-web/lib/api.ts` 当前 SSE 事件 JSON 解析失败会中断整个流。
   - 建议对单个坏事件做容错和错误提示。

## 建议执行顺序

1. 修正文档一致性：README 截图路径、端口说明、`.env.example`。
2. 完成生产安全基线：CORS 白名单、默认密钥和默认管理员密码启动检查。
3. 加上传大小、PDF 页数和文本长度限制。
4. 做错误脱敏和统一错误响应。
5. 建立检索评估脚本和 golden set。
6. 优化 Milvus 分页查询和文档元数据存储。
