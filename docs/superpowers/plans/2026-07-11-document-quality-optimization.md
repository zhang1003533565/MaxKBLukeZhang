# 文档分段质量优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为上传预览和已有文档提供共享的规则清洗、可选模型语义优化、质量门禁、草稿预览及确认应用能力。

**Architecture:** 新建纯函数质量引擎负责清洗、分析、保护项与门禁；上传 Split serializer 复用该引擎。已有文档通过缓存草稿和独立 Celery 任务生成优化结果，应用时事务替换段落并触发重新向量化。

**Tech Stack:** Django、DRF、Celery、Django Cache、LangChain model interface、Vue 3、Element Plus、Pinia、TypeScript。

## Global Constraints

- 不修改数据库结构，不新增依赖。
- 高质量模型优化默认关闭；基础规则清洗默认执行。
- 图片、URL、代码、命令和图片说明必须保持多重集合一致。
- 已导入文档只有确认应用后才修改。
- 不执行 Git 提交或推送。

---

### Task 1: 共享规则清洗与质量分析引擎

**Files:**
- Create: `apps/knowledge/quality/document_quality.py`
- Create: `apps/knowledge/quality/__init__.py`
- Create: `apps/knowledge/test_document_quality.py`

**Interfaces:**
- `clean_paragraph_content(content: str) -> tuple[str, dict]`
- `analyze_paragraph(paragraph: dict) -> dict`
- `clean_paragraphs(paragraphs: list[dict]) -> tuple[list[dict], dict]`

- [ ] 写页码、水印、私有项目符号、空行及幂等性失败测试。
- [ ] 运行 `knowledge.test_document_quality` 确认测试失败。
- [ ] 实现只删除独占页码、`www.themegallery.com`，规范私有符号和空行，保持 URL、代码和图片引用。
- [ ] 实现长度、图片、fallback 图片、噪声、通用标题、长短段落指标与汇总报告。
- [ ] 运行测试确认通过。

### Task 2: 保护项、模型提示与质量门禁

**Files:**
- Modify: `apps/knowledge/quality/document_quality.py`
- Modify: `apps/knowledge/test_document_quality.py`

**Interfaces:**
- `extract_protected_items(content: str) -> Counter`
- `validate_optimized_batch(source: list[dict], result: list[dict]) -> tuple[bool, str]`
- `build_quality_prompt(document_name: str, paragraphs: list[dict]) -> str`
- `normalize_quality_result(payload) -> list[dict]`

- [ ] 写图片/URL/代码/命令/图片说明缺失、重复和改变的失败测试。
- [ ] 写标题 4～40 字、普通文本最短 80、最大 1400、正文变化 15% 的失败测试。
- [ ] 实现保护项 Counter、提示词、JSON 规范化和门禁。
- [ ] 验证合格结果通过、任一保护项变化回退。

### Task 3: 上传预览基础清洗与高质量优化开关

**Files:**
- Modify: `apps/knowledge/api/document.py`
- Modify: `apps/knowledge/views/document.py`
- Modify: `apps/knowledge/serializers/document.py`
- Modify: `apps/knowledge/task/split_preview.py`
- Modify: `apps/knowledge/test_document_vision_split.py`
- Modify: `apps/knowledge/test_split_preview_progress.py`

**Interfaces:**
- Request field: `quality_optimize: bool`
- Split context/report result: 每个文档可附加 `quality_report`

- [ ] 写开关关闭时只清洗且不增加模型调用测试。
- [ ] 写开关开启时对问题批次调用当前文本模型、无问题批次跳过测试。
- [ ] 写模型无效重试一次、门禁失败单批回退测试。
- [ ] 在所有 split strategy 返回前执行基础清洗；开启时运行模型优化并报告阶段进度。
- [ ] 更新异步任务配置透传和多阶段进度。
- [ ] 运行现有视觉/进度测试确认兼容。

### Task 4: 上传页开关、进度与质量报告

**Files:**
- Modify: `ui/src/views/document/upload/SetRules.vue`
- Modify: `ui/src/stores/modules/knowledge.ts`
- Modify: `ui/src/locales/lang/zh-CN/views/document.ts`
- Modify: `ui/src/locales/lang/en-US/views/document.ts`

- [ ] 增加默认关闭的“高质量优化”开关，仅模型分段模式显示。
- [ ] FormData 和 sessionStorage 草稿透传 `quality_optimize`。
- [ ] 支持 quality_analyzing/optimizing/validating 进度文案。
- [ ] 在预览上方显示优化前后段落数、噪声、标题、拆分、合并、回退、未识别图片摘要。
- [ ] 运行 TypeScript 和 ESLint。

### Task 5: 已有文档异步优化草稿后端

**Files:**
- Create: `apps/knowledge/task/document_quality.py`
- Create: `apps/knowledge/test_document_quality_task.py`
- Modify: `apps/knowledge/tasks.py`
- Modify: `apps/knowledge/views/document.py`
- Modify: `apps/knowledge/urls.py`

**Interfaces:**
- `POST document/{document_id}/quality/task`，body `{model_id}`
- `GET/DELETE document/{document_id}/quality/task/{task_id}`
- `POST document/{document_id}/quality/task/{task_id}/apply`

- [ ] 写任务所有权、状态、TTL、取消和终态保护失败测试。
- [ ] 写任务读取按 position 排序段落、保存快照更新时间和优化草稿测试。
- [ ] 写 apply 原文未变时事务替换、原文变化拒绝、草稿过期拒绝测试。
- [ ] 实现缓存任务、Celery 优化、取消与 2 小时 TTL。
- [ ] 实现 apply：事务删除旧映射/段落/向量，创建新段落，触发文档重新向量化。
- [ ] 运行后端任务测试。

### Task 6: 已有文档质量优化前端

**Files:**
- Modify: `ui/src/api/knowledge/document.ts`
- Modify: `ui/src/views/paragraph/index.vue`
- Create: `ui/src/views/paragraph/component/QualityOptimizeDialog.vue`
- Modify: `ui/src/locales/lang/zh-CN/views/document.ts`
- Modify: `ui/src/locales/lang/en-US/views/document.ts`

- [ ] 增加 create/get/cancel/apply API。
- [ ] 在段落页工具栏增加“质量优化”按钮和模型选择。
- [ ] 对话框轮询任务、展示进度、支持终止及刷新恢复。
- [ ] 完成后展示按标题重写、拆分、合并、清洗、回退分组的前后摘要与正文对比。
- [ ] 应用前二次确认；成功后关闭对话框并刷新段落列表。
- [ ] 运行 TypeScript 与 ESLint。

### Task 7: 完整验证与审查

- [ ] 运行质量、视觉、进度、PDF、已有文档任务相关后端测试。
- [ ] 运行 `./scripts/validate-code-rules.sh`。
- [ ] 运行 `git diff --check`。
- [ ] 请求代码审查，修复全部 Critical/Important 后重跑完整验证。
