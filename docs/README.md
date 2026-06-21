# 项目文档目录

本目录用于存放 `Enterprise RAG Assistant` 的设计文档、架构说明、功能方案和运维指南。

## 目录结构

| 目录 | 说明 |
|---|---|
| [`architecture/`](architecture/) | 系统架构与项目总体方案 |
| [`agent/`](agent/) | Agent 流程、方法论与后续改进路线 |
| [`knowledge/`](knowledge/) | 知识库入库优化、知识库管理页面设计 |
| [`frontend/`](frontend/) | 前端页面功能清单与设计参考 |
| [`auth/`](auth/) | 登录、权限与知识库访问控制方案 |
| [`ops/`](ops/) | 部署与启动说明 |
| [`assets/`](assets/) | 文档配图与截图 |

## 快速索引

### 架构设计
- [`architecture/架构设计文档.md`](architecture/架构设计文档.md) — 当前系统架构、模块职责、核心链路、数据模型
- [`architecture/项目架构与功能方案.md`](architecture/项目架构与功能方案.md) — 项目总体规划与技术选型

### Agent 与 RAG
- [`agent/agent-flow-note.md`](agent/agent-flow-note.md) — Agent 完整工作流程与 SSE 事件说明
- [`agent/agent改进.md`](agent/agent改进.md) — 企业级 Agent 分层设计方法论
- [`agent/Agent与RAG后续改进路线.md`](agent/Agent与RAG后续改进路线.md) — 检索、评测、安全、审计等后续演进方向

### 知识库
- [`knowledge/知识库入库优化方案.md`](knowledge/知识库入库优化方案.md) — 入库链路优化与质量提升方案
- [`knowledge/知识库管理页面功能清单.md`](knowledge/知识库管理页面功能清单.md) — 知识库管理页面功能拆分
- [`knowledge/知识库管理页面架构设计.md`](knowledge/知识库管理页面架构设计.md) — 知识库管理页面前后端架构

### 前端
- [`frontend/前端页面功能清单.md`](frontend/前端页面功能清单.md) — 前端各页面功能清单
- [`frontend/design/`](frontend/design/) — xAI 风格设计参考（DESIGN.md、CSS 变量、Design Tokens）

### 权限
- [`auth/登录权限与知识库访问控制方案.md`](auth/登录权限与知识库访问控制方案.md) — 认证、RBAC、知识库空间隔离方案

### 运维
- [`ops/部署与启动说明.md`](ops/部署与启动说明.md) — 环境准备、依赖安装、服务启动

### 图片资源
- [`assets/images/`](assets/images/) — 聊天页、知识库页截图
