<p align="center">
  <img src="./ui/src/assets/logo/liuguang-kb-icon.svg" alt="流光知识库 Logo" width="72" />
</p>

<h1 align="center">流光知识库</h1>
<h3 align="center">流光小队的项目知识库中枢</h3>

---

## 项目定位

流光知识库是流光小队维护的知识库系统，当前项目目标是保留干净的知识库能力：知识库管理、文档上传、分段、向量化、召回测试、简单聊天测试、用户与工作区隔离，以及对外开放的知识库 API。

当前项目不作为智能体平台使用，默认不暴露应用、工作流、触发器、工具等入口。

## 核心能力

- 知识库：创建项目知识库，上传文档，管理分段、问题、自定义分词和设置。
- 检索测试：在知识库内直接做召回测试，查看命中的分段与图片内容。
- 聊天测试：选择知识库和 LLM 模型，将检索内容交给模型，用来验证项目知识库反馈。
- 用户/工作区：用用户和工作区隔离不同项目的知识库。
- 开放 API：生成 API Key 后，可从外部系统上传文档、查看知识库、查看文档分段、执行召回测试。
- 一键部署：服务器上可用脚本拉起应用、PostgreSQL + pgvector、Redis。
- 自动发布：推送到 GitHub `main` 后，可自动构建镜像并 SSH 更新线上服务。

## 本地开发

推荐一条命令启动开发环境。

macOS / Linux：

```bash
./scripts/dev-all.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-all.ps1
```

启动后访问：

- 管理端：http://localhost:3000/admin
- 后端：http://localhost:8080

本地开发只保留这一组同名启动入口。脚本会自动拉起 PostgreSQL、Redis、后端、任务队列和前端。

代码校验：

```bash
./scripts/validate-code-rules.sh
```

## 服务器一键部署

服务器需要先安装 Docker 和 Docker Compose。首次部署可以直接执行：

```bash
git clone git@github.com:zhang1003533565/MaxKBLukeZhang.git /opt/liuguang-kb
cd /opt/liuguang-kb
./scripts/server-deploy.sh
```

脚本会自动创建 `deploy/.env`，并生成数据库密码、Redis 密码和 Django Secret Key。

默认访问：

```text
http://服务器IP:8080/admin
```

默认管理员：

```text
用户名：admin
密码：LiuguangKB@123..
```

首次启动后建议立刻修改管理员密码。

## 生产配置

生产配置文件位于：

```text
deploy/.env
```

常用配置：

```dotenv
LIUGUANG_KB_PORT=8080
LIUGUANG_KB_IMAGE=ghcr.io/zhang1003533565/liuguang-kb:latest
POSTGRES_DB=liuguang_kb
POSTGRES_USER=liuguang_kb
POSTGRES_PASSWORD=自动生成
REDIS_PASSWORD=自动生成
MAXKB_SECRET_KEY=自动生成
MAXKB_DEFAULT_PASSWORD=LiuguangKB@123..
MAXKB_KNOWLEDGE_ONLY=true
```

从服务器源码重新构建并部署：

```bash
./scripts/server-deploy.sh --local
```

从镜像仓库拉取并部署：

```bash
./scripts/server-deploy.sh --pull
```

查看服务状态：

```bash
./scripts/server-deploy.sh --status
```

## GitHub 自动构建和部署

已添加工作流：

```text
.github/workflows/liuguang-kb-deploy.yml
```

它会在推送到 `main` 后构建 Docker 镜像并推送到 GHCR：

```text
ghcr.io/<github-owner>/liuguang-kb:<commit-sha>
ghcr.io/<github-owner>/liuguang-kb:latest
```

要启用自动 SSH 部署，需要在 GitHub 仓库配置：

Repository Variables：

```text
ENABLE_SERVER_DEPLOY=true
SERVER_DEPLOY_PATH=/opt/liuguang-kb
```

Repository Secrets：

```text
SERVER_HOST=服务器 IP 或域名
SERVER_USER=服务器用户名
SERVER_SSH_KEY=服务器 SSH 私钥
SERVER_PORT=22
```

服务器上需要提前存在仓库目录：

```bash
git clone git@github.com:zhang1003533565/MaxKBLukeZhang.git /opt/liuguang-kb
cd /opt/liuguang-kb
./scripts/server-deploy.sh --pull
```

如果 GHCR 镜像保持私有，服务器还需要先登录镜像仓库：

```bash
echo "<github_token>" | docker login ghcr.io -u "<github_username>" --password-stdin
```

之后推送到 `main`，GitHub Actions 会自动：

1. 构建镜像。
2. 推送到 GHCR。
3. SSH 到服务器。
4. 更新服务器代码到当前提交。
5. 写入最新镜像地址。
6. 执行 `DEPLOY_MODE=pull ./scripts/server-deploy.sh`。

## 开放 API

管理端进入：

```text
系统设置 -> 开放 API
```

生成 API Key 后，外部系统通过以下方式访问：

```http
Authorization: Bearer <api_key>
```

基础路径：

```text
/openapi/knowledge/v1/workspaces/{workspace_id}
```

接口能力：

- `GET /knowledges`：获取知识库列表
- `GET /knowledges/{knowledge_id}`：获取知识库详情
- `GET /knowledges/{knowledge_id}/documents`：获取文档列表
- `POST /knowledges/{knowledge_id}/documents/upload`：上传文档
- `GET /knowledges/{knowledge_id}/documents/{document_id}/paragraphs`：获取文档分段
- `POST /hit-test`：召回测试

开放 API 的权限绑定到生成密钥的用户和当前工作区，不会跨项目访问其他工作区知识库。

## 技术栈

- 前端：Vue 3 + TypeScript + Vite + Element Plus
- 后端：Python 3.11 + Django
- 数据库：PostgreSQL + pgvector
- 缓存与任务队列：Redis + Celery
- 部署：Docker Compose + GitHub Actions

## 许可证

本项目基于原开源项目改造，仍遵循 GPLv3 协议。
