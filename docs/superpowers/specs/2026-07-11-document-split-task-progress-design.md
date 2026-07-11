# 文档分段任务真实进度设计

## 目标

将管理端文档分段预览从同步长请求改为异步任务，并展示真实的处理阶段、已处理数量、总数量、剩余数量和总体进度。页面刷新后可以继续查看任务状态和最终预览结果。

## 范围

本次新增管理端文档分段预览任务接口、Celery 后台任务、Redis 状态缓存和前端轮询展示。

保留现有同步 `/document/split` 接口，不改变 OpenAPI、共享 API 和旧客户端行为；不修改数据库结构，不新增依赖。

## 接口

### 创建任务

```text
POST /api/workspace/{workspace_id}/knowledge/{knowledge_id}/document/split/task
Content-Type: multipart/form-data
```

请求字段与现有 `/document/split` 一致，包括文件、切分策略、分段长度和模型 ID。

响应：

```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "task_id": "uuid",
    "status": "queued"
  }
}
```

上传文件在接口内写入现有 `File` 存储，标记为临时任务输入；接口提交 Celery 任务后立即返回，不在 Web 请求进程内解析文档或调用模型。

### 查询任务

```text
GET /api/workspace/{workspace_id}/knowledge/{knowledge_id}/document/split/task/{task_id}
```

处理中响应：

```json
{
  "status": "processing",
  "stage": "vision",
  "progress": 48,
  "processed": 8,
  "total": 20,
  "remaining": 12,
  "message": "正在识别图片，第 8/20 批",
  "result": null,
  "error": null
}
```

完成时 `status=completed` 且 `result` 为现有分段接口返回的数据。失败时 `status=failed`，`error` 为可展示错误摘要；详细异常继续写后端日志。

## 状态安全

任务状态存入 Django Cache（现有 Redis 后端），缓存键包含任务 ID，值中保存：

- `task_id`
- `user_id`
- `workspace_id`
- `knowledge_id`
- `status`
- `stage`
- `progress`
- `processed`
- `total`
- `remaining`
- `message`
- `result`
- `error`

状态和结果缓存 2 小时。状态查询接口必须同时校验当前用户、工作空间、知识库权限以及状态记录中的所有权字段；无权访问时返回无权限，不泄露任务是否存在。

Bearer Token、模型凭证和上传文件内容不得写入进度缓存。

## 处理阶段

### uploading

只存在于前端，使用 Axios `onUploadProgress` 展示真实上传字节进度。上传完成后切换为 `queued`。

### queued

Celery 任务已提交但尚未开始执行。显示“等待处理”。

### parsing

后台读取临时文件并解析 PDF 页、文字和候选图片。此阶段无法提前获得准确子任务总数，展示不确定进度和当前文件序号。

### filtering

执行确定性图片过滤和重复图识别。展示已检查图片数、候选图片总数和剩余数量。

### vision

按每批最多 4 张候选图片调用视觉理解模型。进入阶段前计算本阶段准确批次数；每次模型调用完成后更新：

- `processed`：已完成视觉请求数。
- `total`：视觉请求总数。
- `remaining = total - processed`。

### splitting

视觉增强完成后计算文本模型批次数。每次文本模型调用完成后更新对应的 `processed/total/remaining`。

### completed / failed

成功时缓存完整预览结果；失败时缓存错误摘要并清理临时输入文件以及本次任务产生但未形成有效结果的图片文件。

## 总体进度

总体百分比采用阶段权重，但阶段内部使用真实计数：

- 上传：前端独立显示 0～100%，不计入后台任务百分比。
- queued：0%。
- parsing：5%。
- filtering：10%～20%。
- vision：20%～80%，按视觉请求完成比例计算。
- splitting：80%～99%，按文本请求完成比例计算。
- completed：100%。

如果某阶段总数为 0，直接跳到下一阶段起始百分比。总体百分比只前进不后退。

## 后台任务

新增 Celery 任务接收以下可序列化参数：

- 任务 ID、用户 ID、工作空间 ID、知识库 ID。
- 临时输入 File ID 列表。
- 分段配置和模型 ID。

Celery 参数不传文件字节。任务读取临时 File，构造 Django 上传文件对象并复用 `DocumentSerializers.Split`。任务通过 serializer `context` 注入进度回调，不在模型处理代码中直接依赖 Redis。

进度回调接口：

```python
progress_callback(
    stage: str,
    processed: int,
    total: int,
    message: str,
) -> None
```

serializer 在 PDF 解析、候选过滤、视觉批次和文本批次边界调用回调；同步接口未提供回调时行为保持不变。

## 临时文件生命周期

创建任务时保存的输入文件只供 Celery 任务读取，不作为最终文档源文件。

- 任务开始后读取输入文件。
- `DocumentSerializers.Split` 按现有逻辑生成最终 `source_file_id`。
- 无论成功、失败或异常，Celery 任务在 `finally` 中删除临时输入 File 记录。
- 任务内部生成图片的失败清理由现有双模型图文分段清理逻辑负责。

## 前端

Pinia 的上传草稿新增：

- `backendTaskId`
- `stage`
- `processed`
- `total`
- `remaining`
- `message`

提交流程：

1. 上传任务请求时显示字节上传进度。
2. 收到 `task_id` 后每 1 秒查询状态。
3. `processing` 时更新阶段和真实计数。
4. `completed` 时停止轮询并展示 `result`。
5. `failed` 时停止轮询并展示错误。
6. 组件卸载时停止定时器；页面重新进入时若草稿保存了未完成 `task_id`，恢复轮询。

进度卡展示：

```text
正在识别图片
已处理 8 / 20 批 · 剩余 12 批
总体进度 48%
```

解析阶段总数未知时不显示伪造计数，只显示阶段消息和不确定状态。

## 并发与幂等

- 每个任务 ID 只对应一次处理。
- 前端新建任务时停止旧任务轮询，但不自动撤销已经提交的后台任务。
- 状态更新以任务 ID 为缓存键，不相互覆盖。
- 查询完成状态不会重复执行任务。
- 缓存过期后查询返回任务已过期，前端提示重新生成预览。

## 测试

后端测试覆盖：

- 创建任务保存临时输入并返回 task ID。
- 状态查询权限和任务所有权隔离。
- 状态缓存 TTL 为 2 小时。
- 视觉阶段准确更新已处理、总数和剩余数。
- 文本分段阶段准确更新计数。
- 阶段百分比单调且边界正确。
- Celery 成功时缓存结果并清理临时输入。
- Celery 失败时缓存错误并清理临时输入。
- 现有同步 `/document/split` 行为不变。

前端验证覆盖：

- 上传完成后不再固定停在 95%。
- 每秒轮询并展示 `processed/total/remaining`。
- 完成和失败后停止轮询。
- 页面刷新后恢复轮询。
- 组件卸载时清理定时器。

## 验收标准

上传包含多页和多张图片的 PDF 后，用户可以看到当前阶段、真实已完成请求数、请求总数和剩余请求数；任务完成后自动展示分段预览。页面刷新不会丢失进行中的任务，失败不会留下临时输入文件或错误地显示 100%。
