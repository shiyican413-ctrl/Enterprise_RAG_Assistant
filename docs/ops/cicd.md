# CI/CD

本项目使用 GitHub Actions 建立三段流水线：

- `CI`：PR 和主分支 push 时运行后端测试、前端类型检查、前端构建、Docker 构建冒烟。
- `Publish Images`：主分支、版本 tag 或手动触发时构建并推送镜像到 GHCR。
- `Deploy`：镜像发布成功后部署到服务器，也支持手动选择镜像 tag 部署。

## 镜像

默认镜像名：

```text
ghcr.io/<owner>/enterprise-rag-assistant-backend:<tag>
ghcr.io/<owner>/enterprise-rag-assistant-frontend:<tag>
```

常见 tag：

- `latest`：默认分支最新镜像。
- `main` / `master`：对应分支镜像。
- `sha-xxxxxxx`：提交短 SHA 镜像。
- `v1.2.3`：版本 tag 镜像。

## GitHub Secrets

部署工作流需要在仓库或 GitHub Environment 中配置：

```text
DEPLOY_HOST        服务器 IP 或域名
DEPLOY_USER        SSH 用户
DEPLOY_SSH_KEY     SSH 私钥
DEPLOY_SSH_PORT    SSH 端口，可选，默认 22
DEPLOY_PATH        服务器上的项目目录，例如 /opt/enterprise-rag-assistant
GHCR_USERNAME      GHCR 用户名，私有镜像需要
GHCR_TOKEN         GHCR token，私有镜像需要 read:packages
```

如果 GHCR 镜像是公开的，`GHCR_USERNAME` 和 `GHCR_TOKEN` 可以不配。

## GitHub Variables

发布前端镜像时可配置：

```text
NEXT_PUBLIC_API_BASE_URL=https://your-api.example.com
```

这个值会在前端构建时写入浏览器代码。没有配置时默认 `http://127.0.0.1:8000`。

## 服务器准备

服务器目录需要包含：

```text
docker-compose.prod.yml
.env.production
```

可以从仓库复制 `docker/prod.env.example` 到服务器根目录：

```bash
cp docker/prod.env.example .env.production
```

然后填好数据库、JWT、DashScope、Milvus、前端 API 地址等生产环境变量。

## 手动部署

在 GitHub Actions 页面运行 `Deploy` workflow，传入：

```text
image_tag=latest
environment=production
```

部署流程会在服务器上执行：

```bash
docker compose \
  --env-file .env.production \
  --env-file .deploy-images.env \
  -f docker-compose.prod.yml \
  pull backend frontend

docker compose \
  --env-file .env.production \
  --env-file .deploy-images.env \
  -f docker-compose.prod.yml \
  up -d --remove-orphans
```

## 本地生产构建

不使用 GHCR 时，也可以在服务器本地构建：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```
