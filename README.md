# 流光知识库

流光知识库是流光小队的项目知识中枢，用来沉淀资料、整理文档、完成向量化检索，并把可复用的知识能力开放给内部系统。

这个服务只保留知识库相关能力。默认不作为智能体平台使用，也不开放应用、工作流、触发器、工具等入口。

## 核心能力

- 知识库管理：创建知识库，维护文档、分段、问题、自定义分词和知识库设置。
- 文档处理：上传项目资料，完成分段、索引、向量化和状态跟踪。
- 召回测试：在管理端测试问题命中情况，查看分段、图片和相似度结果。
- 模型验证：选择知识库和模型进行简单问答，验证资料是否能支撑回答。
- 用户隔离：用用户、工作区和权限边界区分不同项目资料。
- 开放接口：通过 API Key 给内部系统提供知识库列表、文档上传、分段查看和召回测试能力。
- 一键部署：脚本会拉起后端、前端、任务队列、数据库和缓存服务。

## 本地启动

macOS 或 Linux：

```bash
./scripts/dev-all.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-all.ps1
```

启动完成后：

- 管理端端口：`3000`，路径：`/admin`
- 后端端口：`8080`

本地启动脚本会自动准备 PostgreSQL、Redis、后端服务、任务队列和前端管理端。

## 服务器部署

服务器需要提前准备 Docker 和 Docker Compose。进入项目目录后执行：

```bash
./scripts/server-deploy.sh
```

常用操作：

```bash
./scripts/server-deploy.sh --local   # 从服务器源码构建并部署
./scripts/server-deploy.sh --pull    # 拉取已构建镜像并部署
./scripts/server-deploy.sh --status  # 查看服务状态
```

首次部署会生成生产配置文件：

```text
deploy/.env
```

脚本会自动生成数据库密码、缓存密码和服务密钥。首次登录后请立即修改默认管理员密码。

## 开放接口

管理端进入：

```text
系统设置 -> 开放 API
```

生成 API Key 后，内部系统在请求头中携带：

```http
Authorization: Bearer <api_key>
```

基础路径：

```text
/openapi/knowledge/v1/workspaces/{workspace_id}
```

当前保留的接口能力：

- `GET /knowledges`：获取知识库列表
- `GET /knowledges/{knowledge_id}`：获取知识库详情
- `GET /knowledges/{knowledge_id}/documents`：获取文档列表
- `POST /knowledges/{knowledge_id}/documents/upload`：上传文档
- `GET /knowledges/{knowledge_id}/documents/{document_id}/paragraphs`：获取文档分段
- `POST /hit-test`：执行召回测试

开放接口的权限绑定到生成密钥的用户和当前工作区，不会跨项目访问其他工作区资料。

## 维护边界

- 继续保持知识库单体定位。
- 不恢复应用、聊天、工作流、触发器、工具等入口，除非后续明确要求。
- 不新增数据库结构和第三方依赖，除非先说明必要性和影响范围。
- 修改后运行项目校验脚本，确保文档和代码规则仍然一致。

## 校验

```bash
./scripts/validate-code-rules.sh
```

## 技术组成

- 前端：Vue 3、TypeScript、Vite、Element Plus
- 后端：Python 3.11、Django
- 数据库：PostgreSQL、pgvector
- 缓存与任务队列：Redis、Celery
- 部署：Docker Compose
