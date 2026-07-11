# 文档切分预览任务强制终止设计

## 目标

为工作区文档切分预览任务提供“终止任务”能力。用户确认终止后，系统强制终止对应的 Celery 任务，不保留本次预览产生的上传文件、源文件、提取图片或预览结果。

## 范围

- 仅作用于工作区异步切分预览任务。
- 支持 `queued`、`parsing`、`filtering`、`vision`、`splitting` 等未结束状态。
- 不改变 systemShare 和 systemManage 仍使用同步预览接口的现状。
- 不修改数据库结构，不新增依赖。
- 不提供暂停、恢复或取消后续跑功能。

## 取消语义

- 前端只有在取得后台任务 ID 后才显示“终止任务”按钮。
- 点击按钮先展示确认对话框，明确说明当前预览和临时文件会被删除。
- 用户确认后，后端先将任务状态改为 `cancelled`，再强制终止 Celery 任务。
- 已完成、失败或已取消的任务不可再次终止。
- 取消成功后，前端停止轮询、清空预览结果并显示“任务已终止”。
- 强制终止针对承载该 Celery 任务的子进程。正在进行的模型 HTTP 请求会随子进程终止而断开。

## 后端接口

新增接口：

```text
DELETE /admin/api/workspace/{workspace_id}/knowledge/{knowledge_id}/document/split/task/{task_id}
```

接口复用任务状态查询的知识库读取权限，并额外校验缓存中的 `user_id`、`workspace_id` 和 `knowledge_id`。不存在、过期或不属于当前用户的任务统一返回 404，避免泄露任务是否存在。

成功响应：

```json
{
  "task_id": "...",
  "status": "cancelled"
}
```

终态任务返回业务冲突错误，不执行 revoke 或文件删除。

## Celery 任务标识

创建预览任务时保存 `split_document_preview_task.delay(...)` 返回的 Celery Task ID，并写入缓存状态的 `celery_task_id` 字段。

取消接口使用该 ID 执行：

```python
celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")
```

缓存状态增加：

- `status: cancelled`
- `stage: cancelled`
- `message: 任务已终止`
- `result: null`
- `error: null`

任务内的进度更新不得把 `cancelled` 覆盖为 `processing`、`failed` 或 `completed`。如果进程在收到终止信号前继续运行，下一次状态更新应检测到取消状态并主动退出。

## 文件归属与清理

所有异步预览产生的文件都必须可由 `task_id` 定位：

- 上传的临时 PDF：保持 `source_type=TEMPORARY_120_MINUTE`、`source_id=task_id`。
- 预览过程中创建的知识库源文件：`meta.split_preview_task_id=task_id`。
- PDF 提取及规范化后的图片：`meta.split_preview_task_id=task_id`。

同步预览不传 `split_preview_task_id`，保持现有行为。

提供统一清理函数，删除：

1. `source_type=TEMPORARY_120_MINUTE AND source_id=task_id` 的上传文件；
2. `meta.split_preview_task_id=task_id` 的所有源文件和图片。

取消接口在 revoke 后立即清理一次。由于强杀与文件保存可能存在竞态，还需投递一个独立的延迟清理任务，在 5 秒后再次执行同一幂等清理函数。原预览任务的 `finally` 仅清理上传临时文件，成功预览产生的源文件和图片必须保留到正式导入或用户取消。

延迟清理任务不得修改已取消状态，也不得删除其他任务或正式导入文档的文件。

## 前端交互

在进度卡片中增加危险样式的“终止任务”按钮：

- 显示条件：存在 `backendTaskId` 且状态为 `queued`、`parsing` 或 `processing`。
- 点击后使用 Element Plus 确认对话框。
- 请求期间按钮进入 loading，避免重复提交。
- 取消成功后调用 `stopPolling()`，将草稿状态更新为 `cancelled`，进度保留在终止时数值，清空 `paragraphList`。
- 刷新页面后，持久化草稿中的 `cancelled` 状态，不恢复轮询。
- 状态查询先返回 `cancelled` 时，前端执行同样的终止态收敛。

Pinia 草稿类型和中英文语言包增加 `cancelled`、确认标题、确认说明、按钮文字和取消成功提示。

## 错误处理

- revoke 调用失败：接口记录详细日志，但仍执行两次文件清理；任务状态保持 `cancelled`，防止用户继续等待一个不可用任务。
- 即时清理失败：记录日志并依赖延迟清理重试。
- 延迟清理失败：Celery 按现有任务日志策略记录错误，不把任务恢复为失败或处理中。
- 前端取消请求失败：保留当前任务状态和轮询，让用户可以重试终止。

## 测试

后端测试覆盖：

- 创建任务后缓存 Celery Task ID；
- 所有者可取消进行中任务；
- 非所有者、不匹配工作区/知识库和不存在任务统一返回 404；
- 终态任务不能 revoke；
- revoke 使用 `terminate=True` 和 `SIGTERM`；
- 即时清理和延迟清理均被触发；
- 清理函数只删除指定 task ID 的临时文件和标记文件；
- 取消状态不会被后续进度、成功或异常覆盖；
- serializer 为异步任务创建的源文件和图片写入 task ID 标记；
- 同步预览不写入任务标记。

前端静态验证覆盖：

- 类型检查和 ESLint 通过；
- 按钮仅在可取消状态显示；
- 用户取消确认框不会发送请求；
- 请求成功停止轮询并进入 `cancelled`；
- 请求失败保持轮询并允许重试。

## 完成标准

- 用户能够从正在处理的分段预览中强制终止任务。
- 终止后页面不再轮询，不产生预览结果。
- 本次任务的上传文件、源文件和图片最终全部删除。
- 其他用户、其他知识库和其他任务的文件不受影响。
- 现有预览、图片识别、文本切分和进度展示测试继续通过。
