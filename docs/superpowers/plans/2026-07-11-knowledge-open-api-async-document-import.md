# 知识库 Open API 异步文档导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Knowledge Open API 上传升级为可查询进度、预览、确认、取消和删除的异步任务，并提供公开可下载的 Markdown 调用文档页面。

**Architecture:** 复用 split preview Celery、缓存状态和文件清理能力，在 Open API 层增加 API Key 任务所有权、索引与幂等映射。上传完成后先生成预览，apply 时复用正式文档批量保存；Markdown 是公开文档页面的唯一内容源。

**Tech Stack:** Django、DRF、Celery、Django Cache、Vue 3、TypeScript、Element Plus。

## Global Constraints

- 使用 `Authorization: Bearer mkb_xxx` 和 `/openapi/knowledge/v1`。
- 不修改数据库结构，不新增依赖。
- 正式文档只在 apply 或 auto_apply 时创建。
- 任务、临时文件和图片必须按 API Key、工作空间和知识库隔离。
- 不执行 Git 提交或推送。

---

### Task 1: Open API 任务状态、索引和幂等缓存

**Files:**
- Create: `apps/knowledge/open_api/document_import_task.py`
- Test: `apps/knowledge/test_open_api_document_import.py`

**Interfaces:**
- `create_import_task_state(task_id, identity, workspace_id, knowledge_id, request_digest, idempotency_key=None)`
- `get_import_task_state(task_id)`
- `update_import_task_state(task_id, **fields)`
- `list_import_task_states(owner_key_id, workspace_id, knowledge_id)`
- `delete_import_task_state(task_id)`

- [ ] 写缓存 TTL、owner_key_id 隔离、列表索引、幂等命中/冲突和删除幂等测试。
- [ ] 运行 `knowledge.test_open_api_document_import` 确认失败。
- [ ] 实现基于 Django Cache 的状态、索引和幂等映射。
- [ ] 运行测试确认通过。

### Task 2: 异步上传、查询、预览、apply、cancel、delete

**Files:**
- Modify: `apps/knowledge/open_api/views.py`
- Modify: `apps/knowledge/open_api/urls.py`
- Modify: `apps/knowledge/task/split_preview.py`
- Modify: `apps/knowledge/test_open_api_document_import.py`

**Interfaces:**
- `POST .../documents/upload`
- `GET .../documents/upload-tasks`
- `GET .../documents/upload-tasks/{task_id}`
- `GET .../documents/upload-tasks/{task_id}/preview`
- `POST .../documents/upload-tasks/{task_id}/apply`
- `POST .../documents/upload-tasks/{task_id}/cancel`
- `DELETE .../documents/upload-tasks/{task_id}`

- [ ] 写异步创建、权限、状态、预览分页和非法状态测试。
- [ ] 写 apply 幂等、cancel、delete、完成后删除不影响正式文档测试。
- [ ] 扩展 split preview worker，使完成结果同步写入 Open API 任务状态并支持 auto_apply。
- [ ] 实现 Open API views 和 URL。
- [ ] 运行测试确认通过。

### Task 3: Open API 文档契约与错误处理

**Files:**
- Modify: `apps/knowledge/open_api/views.py`
- Modify: `apps/knowledge/open_api/auth.py`
- Modify: `apps/knowledge/test_open_api_document_import.py`

- [ ] 统一任务不存在/无权访问为 404。
- [ ] 返回稳定任务状态、metrics、error code 和 status_url。
- [ ] 确保响应不包含 API Key、模型凭证、模型原始响应和堆栈。
- [ ] 更新 `/openapi/knowledge/v1/docs` JSON。
- [ ] 运行 Open API 测试。

### Task 4: Markdown 调用文档和公开服务

**Files:**
- Create: `docs/openapi/knowledge-document-upload.md`
- Modify: `apps/knowledge/open_api/views.py`
- Modify: `apps/knowledge/open_api/urls.py`
- Test: `apps/knowledge/test_open_api_document_import.py`

- [ ] 编写鉴权、上传、轮询、预览、apply、cancel、delete、状态机和错误码文档。
- [ ] 增加公开 Markdown 内容接口和 attachment 下载接口。
- [ ] 测试无需认证、Content-Type、Content-Disposition、内容和无真实密钥。

### Task 5: 独立文档页面

**Files:**
- Create: `ui/src/views/system/KnowledgeOpenAPIDocument.vue`
- Modify: `ui/src/router/modules/system.ts`
- Modify: `ui/src/locales/lang/zh-CN/views/system.ts`
- Modify: `ui/src/locales/lang/en-US/views/system.ts`

- [ ] 创建独立页面读取公开 Markdown 内容。
- [ ] 展示目录、正文、复制代码和下载按钮。
- [ ] 增加公开路由入口并保持窄屏可读。
- [ ] 运行 TypeScript 与 ESLint。

### Task 6: 完整验证和审查

- [ ] 运行 Open API、质量、视觉、任务进度相关后端测试。
- [ ] 运行 `./scripts/validate-code-rules.sh`。
- [ ] 运行 `git diff --check`。
- [ ] 请求代码审查并修复全部 Critical/Important。
