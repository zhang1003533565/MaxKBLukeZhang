# 知识库 Open API 异步文档导入设计

## 目标

将尚未正式投入使用的知识库 Open API 文档上传接口升级为异步任务接口，使外部应用能够使用现有 `mkb_` API Key 完整控制文件上传、解析、图文识别、质量优化、预览、确认导入、取消和删除。

同时提供公开的 Markdown 调用文档、独立文档展示页面和原始 Markdown 下载入口。管理页面与外部应用最终复用同一任务能力。

## 约束

- 继续使用 `Authorization: Bearer mkb_xxx`，不新增认证体系。
- 继续使用 `/openapi/knowledge/v1` 前缀。
- 现有上传接口尚未正式投入使用，允许直接将响应升级为异步任务响应。
- 不修改数据库结构，不新增依赖。
- API Key、模型凭证、文件二进制和模型原始响应不得写入任务缓存。
- 正式文档仅在 `apply` 或 `auto_apply=true` 时创建。
- 失败、取消或删除不得破坏已存在的正式知识库内容。

## 鉴权与权限

所有任务接口复用 `authenticate_open_api_key` 和 `check_knowledge_permission(..., manage=True)`。

每次操作同时校验：

1. API Key 有效且启用；
2. API Key 绑定的 `workspace_id` 与路径一致；
3. 调用用户对目标知识库具有 MANAGE 权限；
4. 任务记录的 `owner_key_id`、工作空间和知识库均与当前请求一致。

任务不存在与无权访问统一返回 404，避免任务枚举。API Key 被停用或删除后不可继续查询或操作旧任务。

## 上传接口

现有路径保持不变：

```http
POST /openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload
Authorization: Bearer mkb_xxx
Content-Type: multipart/form-data
```

支持参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file[] | 与 `file_id` 二选一 | 直接上传一个或多个文件 |
| `file_id` | uuid[] | 与 `file` 二选一 | 复用当前 API Key 有权访问的已有文件 |
| `limit` | integer | 否 | 普通分段长度，默认 4096 |
| `patterns` | string[] | 否 | 高级分段标识符 |
| `with_filter` | boolean | 否 | 是否执行现有过滤 |
| `split_strategy` | string | 否 | `llm_text` 或 `llm_vision` |
| `model_id` | uuid | 条件必填 | 文本模型分段使用 |
| `vision_model_id` | uuid | 条件必填 | 图文分段视觉模型 |
| `llm_model_id` | uuid | 条件必填 | 图文分段文本模型 |
| `quality_optimize` | boolean | 否 | 是否执行模型质量优化，默认 false |
| `auto_apply` | boolean | 否 | 预览完成后是否自动导入，默认 false |
| `idempotency_key` | string | 否 | 调用方幂等键，最长 128 字符 |

`file` 与 `file_id` 不允许同时为空。第一版允许同一请求同时提交两类来源，并合并为一个任务；重复文件按文件哈希去重。

响应：

```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "task_id": "019f...",
    "status": "QUEUED",
    "status_url": "/openapi/knowledge/v1/workspaces/default/knowledges/xxx/documents/upload-tasks/019f..."
  }
}
```

## 配套接口

```text
GET    /workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks
GET    /workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}
GET    /workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/preview
POST   /workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/apply
POST   /workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/cancel
DELETE /workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}
```

### 列表

列表仅返回当前 API Key 创建且属于路径工作空间、知识库的任务。支持：

- `page` / `current_page`；
- `size` / `page_size`；
- `status`；
- `created_after`；
- `created_before`。

### 详情

详情返回稳定的任务状态、进度和统计：

```json
{
  "task_id": "019f...",
  "status": "QUALITY_OPTIMIZING",
  "stage": "quality_optimizing",
  "progress": 92,
  "processed": 8,
  "total": 9,
  "remaining": 1,
  "message": "正在优化分段质量",
  "metrics": {
    "uploaded_files": 1,
    "total_files": 1,
    "vision_batches": 46,
    "vision_fallback_batches": 3,
    "quality_batches": 9,
    "quality_fallback_batches": 6
  },
  "document_ids": [],
  "error": null,
  "created_at": "...",
  "updated_at": "...",
  "expires_at": "..."
}
```

进度必须单调递增。`processed`、`total`、`remaining` 表示当前阶段批次，不混合视觉和质量阶段计数；累计信息放在 `metrics`。

### 预览

仅 `PREVIEW_READY`、`APPLYING`、`EMBEDDING`、`COMPLETED` 可读取。返回：

- 文件与拟创建文档信息；
- 段落标题、正文、图片引用；
- 优化前后差异；
- 清洗、拆分、合并、回退及未识别图片报告；
- `can_apply` 和草稿过期时间。

预览支持分页，避免大型文档一次返回全部正文。

### Apply

`apply` 在事务中创建正式文档、段落、问题关联和向量任务。调用幂等：

- 首次成功返回 `document_ids`；
- 重复调用返回相同 `document_ids`；
- `APPLYING` 时返回当前状态，不重复执行；
- 任一严格向量步骤失败时回滚正式数据，任务进入 `FAILED`。

### Cancel

允许 `QUEUED` 到 `QUALITY_VALIDATING` 状态取消。流程：

1. 写入 cancelled tombstone；
2. revoke Celery 任务并强制终止；
3. 删除预览、临时文件和任务生成图片；
4. 状态进入 `CANCELLED`。

重复取消保持幂等。`PREVIEW_READY` 后应使用 DELETE 放弃草稿。

### Delete

- 处理中：先执行强制取消，再清理任务资源；
- `PREVIEW_READY`：删除草稿和临时资源；
- `FAILED/CANCELLED`：清理残留资源；
- `COMPLETED`：只删除任务记录，不删除正式文档；
- 重复删除返回 `{ "deleted": true }`。

## 状态机

```text
CREATED
  → UPLOADING
  → QUEUED
  → PARSING
  → VISION_FILTERING
  → VISION_RECOGNIZING
  → TEXT_SPLITTING
  → QUALITY_CLEANING
  → QUALITY_OPTIMIZING
  → QUALITY_VALIDATING
  → PREVIEW_READY
  → APPLYING
  → EMBEDDING
  → COMPLETED
```

控制和异常状态：

```text
FAILED
CANCELLING
CANCELLED
DELETING
```

`auto_apply=true` 时从 `PREVIEW_READY` 自动进入 `APPLYING`。未开启时必须由调用方确认。

## 任务存储

第一版复用现有 Django Cache、临时 File 记录和 Celery 任务，不增加数据库表。

缓存 TTL 为 2 小时，任务状态包含 `owner_key_id`，但不包含 secret key。临时文件及图片通过 `task_id` 标记。所有清理同时执行立即清理和延迟幂等清理任务。

由于缓存任务列表不能可靠扫描，任务列表维护单独的 API Key 任务索引缓存；创建、删除和过期时更新索引，读取时过滤已经过期的任务 ID。

## 幂等性

`idempotency_key` 的作用域为：

```text
owner_key_id + workspace_id + knowledge_id + idempotency_key
```

相同作用域和相同请求摘要返回原任务；相同幂等键但文件哈希或配置不同返回 `KDI_4003`。幂等记录与任务保持相同 TTL。

`apply`、`cancel`、`delete` 均具有独立的状态级幂等语义。

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `KDI_1001` | API Key 无效 |
| `KDI_1002` | 无知识库管理权限 |
| `KDI_2001` | 文件为空或格式不支持 |
| `KDI_2002` | 文件超过限制 |
| `KDI_3001` | 模型配置无效 |
| `KDI_3002` | 模型调用失败 |
| `KDI_3003` | 模型输出无效，已部分回退 |
| `KDI_4001` | 任务不存在或已过期 |
| `KDI_4002` | 当前状态不能执行该操作 |
| `KDI_4003` | 幂等键冲突 |
| `KDI_5001` | 应用草稿失败，正式数据未改变 |

错误响应不包含供应商原始响应、模型凭证、堆栈或文件内容。详细错误只写服务端日志。

## 公开调用文档

Markdown 唯一内容源：

```text
docs/openapi/knowledge-document-upload.md
```

文档必须包含：

- API Key 创建和 `Bearer mkb_xxx` 鉴权；
- 完整接口路径；
- multipart 和 `file_id` 示例；
- cURL、Python requests、JavaScript fetch 示例；
- 轮询、预览、apply、cancel、delete 示例；
- 状态机和错误码；
- 幂等键建议；
- 安全注意事项；
- 不含真实密钥。

公开页面：

```text
GET /openapi/knowledge/docs
```

原始文档下载：

```text
GET /openapi/knowledge/docs/download
```

页面无需登录，读取同一个 Markdown 文件并渲染，提供目录导航、代码复制和下载按钮。下载响应使用：

```text
Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename="knowledge-document-upload.md"
```

页面不得读取或显示系统中存在的任何真实 API Key。

## Open API Docs JSON

现有 `/openapi/knowledge/v1/docs` 返回值同步更新：

- 上传接口标注为异步；
- 展示新增参数；
- 增加任务列表、详情、预览、apply、cancel、delete；
- 提供公开 HTML 文档页和 Markdown 下载地址。

## 测试

后端覆盖：

- API Key、工作空间、知识库 MANAGE 和 owner_key_id 隔离；
- multipart、file_id 和混合上传；
- 文件哈希去重；
- 创建任务和幂等键冲突；
- 状态机、进度单调性及 metrics；
- 预览分页；
- apply 幂等和失败回滚；
- cancel、delete 和重复操作；
- 已完成任务删除不影响正式文档；
- 临时文件、图片和缓存索引清理；
- 过期任务；
- 稳定错误码和敏感错误隔离；
- 现有知识库列表、详情、段落和召回接口回归。

文档覆盖：

- 公开 HTML 页面无需认证；
- Markdown 下载文件名、Content-Type 和内容；
- 页面内容来自 Markdown 单一文件；
- 文档所有接口路径与 Django URL 一致；
- 示例中不存在真实 `mkb_` 密钥。

前端覆盖：

- 文档页面渲染和目录；
- 代码复制；
- Markdown 下载；
- 窄屏可读性；
- TypeScript 与 ESLint。

## 完成标准

- 现有 Open API 上传返回异步任务，不再保持长连接等待模型处理；
- 外部应用能查询进度、预览、apply、取消和删除；
- 页面能够使用同一任务契约；
- 正式数据只在 apply 或 auto_apply 时创建；
- 所有失败、取消和删除路径完成资源清理；
- 任务与 API Key、工作空间、知识库严格隔离；
- 公开页面可阅读调用说明并下载原始 Markdown；
- 不新增数据库迁移和依赖；
- 全部相关测试、类型检查、ESLint 和项目规则校验通过。
