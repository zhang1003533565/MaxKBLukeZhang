# 文档切分预览任务强制终止 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工作区异步文档切分预览增加强制终止按钮，并确保终止后清除该任务产生的全部文件。

**Architecture:** 缓存状态保存 Celery Task ID；DELETE 接口先原子地进入 cancelled，再 revoke 对应任务。所有异步预览产物写入 task ID 标记，统一清理函数立即执行一次并由独立 Celery 任务在 5 秒后再次执行。

**Tech Stack:** Django REST Framework、Celery、Django Cache、Vue 3、Pinia、Element Plus、TypeScript。

## Global Constraints

- 不修改数据库结构，不新增依赖。
- 仅工作区异步预览使用强制终止；systemShare/systemManage 保持同步接口。
- 终止后不保留上传文件、源文件、提取图片或预览结果。
- 不执行 `git add`、`git commit` 或 `git push`。

---

### Task 1: 可取消缓存状态与幂等文件清理

**Files:**
- Modify: `apps/knowledge/task/split_preview.py`
- Test: `apps/knowledge/test_split_preview_progress.py`

**Interfaces:**
- Produces: `cancel_split_task_state(task_id) -> dict | None`
- Produces: `cleanup_split_preview_files(task_id) -> None`
- Produces: `cleanup_split_preview_files_task(task_id) -> None`

- [ ] **Step 1: 写失败测试**

覆盖 cancelled 状态不能被普通进度覆盖、清理查询同时包含临时文件归属和 `meta__split_preview_task_id`、延迟清理任务调用统一函数。

- [ ] **Step 2: 运行测试确认失败**

Run: `MAXKB_CONFIG=ENV MAXKB_CONFIG_TYPE=ENV PYTHONPATH=$PWD/apps .venv/bin/python apps/manage.py test knowledge.test_split_preview_progress --keepdb`

Expected: 新增取消/清理测试失败。

- [ ] **Step 3: 最小实现**

在 `update_split_task_state` 中发现当前状态为 `cancelled` 时拒绝非 cancelled 更新；实现：

```python
def cleanup_split_preview_files(task_id):
    QuerySet(File).filter(
        Q(source_type=FileSourceType.TEMPORARY_120_MINUTE.value, source_id=str(task_id))
        | Q(meta__split_preview_task_id=str(task_id))
    ).delete()
```

注册延迟清理 Celery 任务，并让预览任务 `finally` 复用统一函数。

- [ ] **Step 4: 运行测试确认通过**

Expected: `knowledge.test_split_preview_progress` 全部通过。

### Task 2: 标记异步预览产生的所有文件

**Files:**
- Modify: `apps/knowledge/serializers/document.py`
- Test: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Consumes: serializer context `split_preview_task_id: str | None`
- Produces: 源文件和图片的 `meta.split_preview_task_id`

- [ ] **Step 1: 写失败测试**

构造带 `context={"split_preview_task_id": "task-1"}` 的 Split serializer，断言源文件及 `save_image` 保存的图片 meta 带 task ID；无 context 时不带该字段。

- [ ] **Step 2: 运行测试确认失败**

Run: 同 Task 1 环境执行 `knowledge.test_document_vision_split`。

- [ ] **Step 3: 最小实现**

新增内部方法：

```python
def _split_preview_file_meta(self):
    task_id = self.context.get("split_preview_task_id")
    return {"split_preview_task_id": str(task_id)} if task_id else {}
```

创建源文件时传入 meta，保存提取图片时合并该 meta。Celery 预览任务创建 serializer 时传入 task ID context。

- [ ] **Step 4: 运行测试确认通过**

Expected: 文件标记测试及现有视觉切分测试通过。

### Task 3: DELETE 取消接口与 Celery revoke

**Files:**
- Modify: `apps/knowledge/views/document.py`
- Modify: `apps/knowledge/urls.py`
- Modify: `apps/knowledge/task/split_preview.py`
- Modify: `apps/knowledge/tasks.py`
- Test: `apps/knowledge/test_split_preview_progress.py`

**Interfaces:**
- Produces: `DELETE .../document/split/task/<task_id>`
- Consumes: cache state `celery_task_id`

- [ ] **Step 1: 写失败测试**

覆盖创建任务缓存 AsyncResult ID；合法取消调用 `celery_app.control.revoke(id, terminate=True, signal="SIGTERM")`；立即清理并 `apply_async(args=[task_id], countdown=5)`；非所有者统一 404；终态不 revoke。

- [ ] **Step 2: 运行测试确认失败**

Expected: 路由、delete handler 或 celery_task_id 断言失败。

- [ ] **Step 3: 最小实现**

保存 `.delay()` 返回值的 `.id`。在 `SplitTaskStatus.delete` 中复用 GET 的所有权校验，检查可取消状态，写 cancelled 后 revoke、立即清理并调度延迟清理。revoke 异常记录日志但不恢复状态。

- [ ] **Step 4: 运行测试确认通过**

Expected: 所有取消接口测试通过，Celery autodiscovery 能找到预览和清理任务。

### Task 4: 前端终止按钮与取消状态

**Files:**
- Modify: `ui/src/api/knowledge/document.ts`
- Modify: `ui/src/stores/modules/knowledge.ts`
- Modify: `ui/src/views/document/upload/SetRules.vue`
- Modify: `ui/src/locales/lang/zh-CN/views/document.ts`
- Modify: `ui/src/locales/lang/en-US/views/document.ts`

**Interfaces:**
- Produces: `cancelSplitDocumentTask(knowledgeId, taskId)`
- Produces: draft status `cancelled`

- [ ] **Step 1: 实现 API 与状态类型**

使用现有 request `del` 方法调用与状态查询相同 URL；草稿状态联合类型增加 `cancelled`，持久化逻辑保持不变。

- [ ] **Step 2: 实现界面行为**

在有 backendTaskId 且 queued/parsing/processing 时显示 danger 按钮。通过 `ElMessageBox.confirm` 确认；成功后停止轮询、清空 paragraphList、写入 cancelled；失败时继续轮询并允许重试。轮询读到 cancelled 时同样收敛。

- [ ] **Step 3: 增加中英文文案**

添加终止按钮、确认标题、不可恢复说明、已终止状态和取消失败提示。

- [ ] **Step 4: 运行前端验证**

Run: `cd ui && npm run type-check && ./node_modules/.bin/eslint --max-warnings=0 src/views/document/upload/SetRules.vue src/stores/modules/knowledge.ts src/api/knowledge/document.ts`

Expected: exit 0。

### Task 5: 完整验证与审查

**Files:**
- Verify all modified files

- [ ] **Step 1: 运行相关后端测试**

Run: 带完整本地 MAXKB 环境变量执行 `knowledge.test_split_preview_progress knowledge.test_document_vision_split common.handle.impl.text.tests.test_pdf_split_handle --keepdb`。

Expected: 0 failures。

- [ ] **Step 2: 运行仓库统一校验**

Run: `./scripts/validate-code-rules.sh`

Expected: exit 0；允许仓库现有两个 URL warning。

- [ ] **Step 3: 检查变更并请求代码审查**

Run: `git diff --check && git status --short`。

审查重点：权限隔离、终态防覆盖、强杀竞态、清理范围、前端离页/轮询竞态。修复全部 Critical/Important 后再次执行 Step 1 和 Step 2。
