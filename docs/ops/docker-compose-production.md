# Docker Compose 生产部署

本部署方式适合当前方案：前端部署到前端托管平台，后端和数据服务部署到阿里云 ECS。

## 服务组成

- `backend`：FastAPI 后端，绑定到宿主机 `127.0.0.1:8000`
- `postgres`：会话、用户和权限数据
- `milvus`：知识库向量数据
- `etcd` / `minio`：Milvus Standalone 依赖

前端托管平台只需要配置：

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.your-domain.com
```

## 首次部署

在 ECS 上安装 Docker 和 Compose 插件后，进入项目根目录：

```bash
cp docker/prod.env.example .env.production
```

编辑 `.env.production`，至少替换这些值：

```bash
POSTGRES_PASSWORD=...
MINIO_SECRET_KEY=...
JWT_SECRET=...
INITIAL_ADMIN_EMAIL=...
INITIAL_ADMIN_PASSWORD=...
DASHSCOPE_API_KEY=...
```

启动服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

查看状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## Nginx 反代

推荐在宿主机安装 Nginx，并反代到本机后端：

```nginx
server {
    listen 80;
    server_name api.your-domain.com;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

配置 HTTPS：

```bash
certbot --nginx -d api.your-domain.com
```

## 日常更新

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 备份提醒

生产数据在 Docker named volumes 和项目 `data/` 目录里：

- `postgres_data`
- `milvus_data`
- `etcd_data`
- `minio_data`
- `./data/uploads`
- `./data/knowledge_base`

迁移或重装服务器前需要备份这些数据。
