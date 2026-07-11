# 平衡型文档质量优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有两层质量优化基础上补齐上下文清洗、PDF 断行修复、重复标题批处理、严格来源映射及完整质量报告。

**Architecture:** 扩展纯函数质量引擎，让确定性清洗返回可审计报告；由 Split serializer 根据质量指标和相邻标题构造有限窗口批次。模型仍只调整标题和段落边界，所有结果通过字符序列与保护项门禁后才采用。

**Tech Stack:** Python 3.11、Django、LangChain model interface、Vue 3、Element Plus、TypeScript。

## Global Constraints

- 不修改数据库结构，不新增依赖。
- 基础清洗默认执行；模型质量优化继续由开关控制。
- 目标段落 180～700 字，软上限 900 字，硬上限 1400 字。
- 代码、命令、URL、图片引用、图片说明、数字及正文事实不可改写。
- 不执行 Git 提交或推送。

---

### Task 1: 上下文基础清洗

**Files:**
- Modify: `apps/knowledge/quality/document_quality.py`
- Test: `apps/knowledge/test_document_quality.py`

**Interfaces:**
- Consumes: `clean_paragraph_content(content: str, title: str = "")`
- Produces: `tuple[str, dict]`，报告新增 `removed_page_numbers`、`preserved_numeric_lines`、`joined_pdf_lines`、`removed_duplicates`

- [ ] **Step 1: 写失败测试**

覆盖正文开头重复标题、明确页码、页边界附近独占数字、无法确认的独占数字、相邻重复图片说明和中文 PDF 断行；代码块、URL、图片说明内部换行保持不变。

- [ ] **Step 2: 运行测试确认失败**

Run: `MAXKB_CONFIG=ENV MAXKB_CONFIG_TYPE=ENV MAXKB_KNOWLEDGE_ONLY=true PYTHONPATH=apps .venv/bin/python apps/manage.py test knowledge.test_document_quality --keepdb`

Expected: 新增断言失败。

- [ ] **Step 3: 实现最小清洗状态机**

使用行类型判定保护 fenced code、URL、图片引用和图片说明；仅对 PDF 的连续中文正文行应用断行拼接。由于当前解析结果没有可靠页边界元数据，独占数字全部加入 `preserved_numeric_lines`，只有 `第 N 页` 等明确页标识被删除。

- [ ] **Step 4: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

### Task 2: 候选检测与有限相邻窗口

**Files:**
- Modify: `apps/knowledge/quality/document_quality.py`
- Modify: `apps/knowledge/serializers/document.py`
- Test: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Produces: `analyze_paragraph()` 新增 `duplicate_title`、`multiple_headings`
- Produces: `_build_quality_work_units(paragraphs) -> list[tuple[bool, list[dict]]]`

- [ ] **Step 1: 写失败测试**

覆盖连续相同标题组成同一批次、正常段不调用模型、短段带一个相邻上下文、批次字符和图片数量超限时不继续扩张。

- [ ] **Step 2: 实现批次构造器**

连续相同标题优先成批；短段只带一个相邻段；长段和多标题段单独处理。批次不得包含整份文档，且来源 ID 按段保留。

- [ ] **Step 3: 运行视觉与质量测试**

Run: `MAXKB_CONFIG=ENV MAXKB_CONFIG_TYPE=ENV MAXKB_KNOWLEDGE_ONLY=true PYTHONPATH=apps .venv/bin/python apps/manage.py test knowledge.test_document_vision_split knowledge.test_document_quality --keepdb`

Expected: PASS。

### Task 3: 门禁、来源映射与报告

**Files:**
- Modify: `apps/knowledge/quality/document_quality.py`
- Modify: `apps/knowledge/serializers/document.py`
- Test: `apps/knowledge/test_document_quality.py`
- Test: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Consumes: `validate_optimized_batch(source, result)`
- Produces: `quality_report` 新增 `processed_batches`、`total_batches`、`fallback_batches`、`preserved_numeric_lines`

- [ ] **Step 1: 写失败测试**

覆盖内部空白变化、数字变化、图片顺序变化、两段未合并时逐段来源、真正合并时多来源、拆分时单来源继承。

- [ ] **Step 2: 收紧门禁并完善 provenance**

只去除段落边界空白后比较完整字符序列；保护项 Counter 继续验证代码、URL、图片和说明。输出数量等于输入数量时逐项映射，真正合并时合并来源，单段拆分时所有输出继承同一来源。

- [ ] **Step 3: 汇总任务报告与进度**

每完成一批更新 processed/total/remaining，并统计回退及保留数字；模型调用异常仍使任务失败，单批格式或门禁失败只回退该批。

- [ ] **Step 4: 运行后端回归测试**

Run: `MAXKB_CONFIG=ENV MAXKB_CONFIG_TYPE=ENV MAXKB_KNOWLEDGE_ONLY=true PYTHONPATH=apps .venv/bin/python apps/manage.py test knowledge.test_document_quality knowledge.test_document_vision_split knowledge.test_document_quality_task knowledge.test_split_preview_progress --keepdb`

Expected: PASS。

### Task 4: 前端质量报告与进度文案

**Files:**
- Modify: `ui/src/views/document/upload/SetRules.vue`
- Modify: `ui/src/views/paragraph/component/QualityOptimizeDialog.vue`
- Modify: `ui/src/locales/lang/zh-CN/views/document.ts`
- Modify: `ui/src/locales/lang/en-US/views/document.ts`

**Interfaces:**
- Consumes: 任务状态 `processed`、`total`、`remaining` 和 `result.report`

- [ ] **Step 1: 展示四阶段和批次统计**

上传页与已有文档弹窗显示清洗、分析、模型优化、质量校验；模型阶段显示“已处理 N/T，剩余 R，回退 F”。

- [ ] **Step 2: 扩展质量摘要**

展示明确页码、重复行、PDF 断行、保留独占数字、标题重写、拆分、合并和回退数量。

- [ ] **Step 3: 验证前端**

Run: `cd ui && npm run type-check`

Run: `cd ui && ./node_modules/.bin/eslint --max-warnings=0 src/views/document/upload/SetRules.vue src/views/paragraph/component/QualityOptimizeDialog.vue src/locales/lang/zh-CN/views/document.ts src/locales/lang/en-US/views/document.ts`

Expected: 两条命令均成功。

### Task 5: 完整验证

**Files:**
- Verify all modified files.

- [ ] **Step 1: 运行项目规则校验**

Run: `./scripts/validate-code-rules.sh`

Expected: Validation finished；仅允许仓库已有 URL warning。

- [ ] **Step 2: 检查差异完整性**

Run: `git diff --check`

Expected: 无输出且退出码为 0。

- [ ] **Step 3: 对照设计自检**

确认没有数据库迁移、新依赖、自动提交；关闭模型开关时不新增模型调用；失败路径不修改正式文档。
