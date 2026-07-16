# MaxKB 知识库异步文档导入开放接口

本文档说明外部应用如何使用 API Key 上传文档、查询处理进度、预览分段、确认入库、终止任务和删除任务记录。

## 基础信息

- API 前缀：`https://你的域名/openapi/knowledge/v1`
- 鉴权：`Authorization: Bearer mkb_your_api_key`
- 上传格式：`multipart/form-data`
- 任务保留时间：2 小时。超时后任务状态与未入库的临时文件会失效。
- 正式文档只会在调用 `apply` 或上传时设置 `auto_apply=true` 后创建。

请勿把 API Key 写入浏览器前端代码或公开仓库。

## 0. 获取可用模型

上传接口需要使用真实模型 UUID 时，可先查询当前工作区可见的工作区模型和共享模型。

```bash
curl 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/models?model_type=LLM' \
  -H 'Authorization: Bearer mkb_your_api_key'
```

`model_type` 只支持 `LLM` 和 `IMAGE`。响应中的每个对象只返回：

- `id`
- `name`
- `model_name`
- `model_type`
- `provider`
- `scope`，其中 `workspace` 表示工作区模型，`shared` 表示共享模型

响应示例：

```json
{
  "code": 200,
  "message": "Success",
  "data": [
    {
      "id": "llm-1",
      "name": "通义千问",
      "model_name": "qwen-plus",
      "model_type": "LLM",
      "provider": "Qwen",
      "scope": "workspace"
    },
    {
      "id": "llm-2",
      "name": "共享模型",
      "model_name": "shared-chat",
      "model_type": "LLM",
      "provider": "OpenAI",
      "scope": "shared"
    }
  ]
}
```

## 1. 创建异步上传任务

```bash
curl -X POST \
  'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload' \
  -H 'Authorization: Bearer mkb_your_api_key' \
  -H 'Idempotency-Key: order-20260711-001' \
  -F 'file=@./manual.pdf' \
  -F 'split_strategy=llm_vision' \
  -F 'vision_model_id={qwen3_vl_plus_model_id}' \
  -F 'llm_model_id={deepseek_text_model_id}' \
  -F 'quality_optimize=true' \
  -F 'auto_apply=false'
```

可重复提交多个 `file`。也可使用属于当前知识库的 `file_id`，服务端会复制为本次任务的临时输入。推荐为每个业务请求设置唯一的 `Idempotency-Key`；相同 Key 和相同参数会返回原任务，不同参数会返回 `409`。

常用参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `file` | file[] | 待导入文件，可重复 |
| `file_id` | uuid[] | 当前知识库已有文件 ID，可重复 |
| `limit` | integer | 分段长度，默认 4096 |
| `patterns` | string[] | 高级分段标识 |
| `with_filter` | boolean | 是否清洗文本 |
| `split_strategy` | string | `llm_text` 或 `llm_vision` |
| `model_id` | uuid | 文本大模型分段模型 |
| `vision_model_id` | uuid | 图文理解模型，如 Qwen3-VL-Plus |
| `llm_model_id` | uuid | 图文识别后的文本切分模型，如 DeepSeek 类文本模型 |
| `quality_optimize` | boolean | 是否启用高质量优化 |
| `auto_apply` | boolean | 预览完成后是否自动入库 |
| `idempotency_key` | string | 也可通过 `Idempotency-Key` 请求头传递 |

响应示例：

```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "task_id": "019f...",
    "status": "QUEUED",
    "progress": 0,
    "metrics": {"processed": 0, "total": 0, "remaining": 0},
    "status_url": "https://.../upload-tasks/019f...",
    "preview_url": "https://.../upload-tasks/019f.../preview",
    "apply_url": "https://.../upload-tasks/019f.../apply"
  }
}
```

## 2. 查询任务列表和进度

```bash
curl 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks?page=1&page_size=20' \
  -H 'Authorization: Bearer mkb_your_api_key'

curl 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}' \
  -H 'Authorization: Bearer mkb_your_api_key'
```

`metrics.processed` 表示已处理批次，`metrics.total` 表示总批次，`metrics.remaining` 表示剩余批次。建议每 1～2 秒轮询一次，并在终态停止。

状态：`QUEUED`、`PROCESSING`、`PREVIEW_READY`、`APPLYING`、`COMPLETED`、`FAILED`、`CANCELLED`。

## 3. 分页查看预览

仅 `PREVIEW_READY` 状态可查看预览。

```bash
curl 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/preview?page=1&page_size=20' \
  -H 'Authorization: Bearer mkb_your_api_key'
```

## 4. 确认入库

```bash
curl -X POST 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/apply' \
  -H 'Authorization: Bearer mkb_your_api_key'
```

重复调用已完成任务会返回原有文档结果，不会重复创建。返回 `COMPLETED` 表示文档已创建并进入向量化队列。

## 5. 强制终止任务

```bash
curl -X POST 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/cancel' \
  -H 'Authorization: Bearer mkb_your_api_key'
```

终止会撤销后台任务并清理未入库临时文件。已完成或已经入库的任务不能终止。

## 6. 删除任务记录

```bash
curl -X DELETE 'https://你的域名/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}' \
  -H 'Authorization: Bearer mkb_your_api_key'
```

删除运行中任务时会先强制终止。删除已入库任务只删除任务记录，不删除正式文档。

## Python 轮询示例

```python
import time
import requests

headers = {"Authorization": "Bearer mkb_your_api_key"}
upload = requests.post(upload_url, headers=headers, files={"file": open("manual.pdf", "rb")}).json()["data"]

while True:
    task = requests.get(upload["status_url"], headers=headers).json()["data"]
    print(task["progress"], task["metrics"])
    if task["status"] in {"PREVIEW_READY", "COMPLETED", "FAILED", "CANCELLED"}:
        break
    time.sleep(1.5)
```

## 错误处理

| code | 含义 |
| --- | --- |
| `400` | 缺少文件或参数格式错误 |
| `401` / `1002` / `1003` | API Key 无效或缺失 |
| `403` | API Key 无工作空间或知识库权限 |
| `404` | 任务、知识库或复用文件不存在；任务越权也返回此错误 |
| `409` | 幂等键冲突、任务状态不允许当前操作 |

失败响应中的 `data.error` 只包含稳定错误码和安全提示，不包含模型凭证、原始模型响应或服务端堆栈。
