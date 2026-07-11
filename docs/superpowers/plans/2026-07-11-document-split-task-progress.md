# Document Split Task Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run management-side document split previews as Celery tasks and show exact stage request counts through one-second frontend polling.

**Architecture:** The new task endpoint persists uploaded inputs as temporary `File` records, stores an ownership-scoped task state in Django Cache, and submits a Celery task. The task reconstructs uploaded files, reuses `DocumentSerializers.Split` with a context progress callback, caches the final preview or failure, and always deletes temporary input files. The current synchronous endpoint remains unchanged.

**Tech Stack:** Django REST Framework, Celery, Django Cache/Redis, Vue 3, Pinia, Axios.

## Global Constraints

- No database migrations or new dependencies.
- Preserve the existing synchronous split and OpenAPI behavior.
- Task status is private to the requesting user/workspace/knowledge.
- Cache state for exactly 7200 seconds.
- Do not stage, commit, or push Git changes.

---

### Task 1: Task state utility and progress math

**Files:**
- Create: `apps/knowledge/task/split_preview.py`
- Create: `apps/knowledge/test_split_preview_progress.py`

**Interfaces:**
- `create_split_task_state(task_id, user_id, workspace_id, knowledge_id) -> dict`
- `update_split_task_state(task_id, **fields) -> dict`
- `get_split_task_state(task_id) -> dict | None`
- `calculate_split_progress(stage, processed, total) -> int`

- [ ] Write failing tests for cache TTL, ownership fields, remaining count, stage boundaries, and monotonic progress.
- [ ] Run `knowledge.test_split_preview_progress` and verify failure.
- [ ] Implement cache helpers with a `split-preview:{task_id}` key and 7200-second timeout.
- [ ] Re-run tests and verify pass.

### Task 2: Serializer progress callbacks

**Files:**
- Modify: `apps/knowledge/serializers/document.py`
- Modify: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Serializer context callback: `(stage: str, processed: int, total: int, message: str) -> None`.

- [ ] Write failing tests that collect callback events for parsing, filtering, vision batches, and text batches.
- [ ] Add a no-op-safe `_report_progress` helper.
- [ ] Refactor vision enrichment into filter and model-call passes so total visual batches are known before the first request.
- [ ] Report exact text-model batch counts in both `llm_text` and `llm_vision` flows.
- [ ] Run the existing PDF/vision tests plus new progress tests.

### Task 3: Celery split-preview task

**Files:**
- Modify: `apps/knowledge/task/split_preview.py`
- Create: `apps/knowledge/tasks.py`
- Test: `apps/knowledge/test_split_preview_progress.py`

**Interfaces:**
- `split_document_preview_task(task_id, user_id, workspace_id, knowledge_id, input_file_ids, split_config)`.

- [ ] Write success/failure tests with mocked serializer and temporary File queryset.
- [ ] Reconstruct `SimpleUploadedFile` values from temporary File records.
- [ ] Invoke `DocumentSerializers.Split(..., context={"progress_callback": callback}).parse(...)`.
- [ ] Cache completed result or safe error summary and log the traceback.
- [ ] Delete all temporary input File records in `finally`.
- [ ] Export the task through Django/Celery autodiscovery in `knowledge/tasks.py`.

### Task 4: Create/status endpoints

**Files:**
- Modify: `apps/knowledge/views/document.py`
- Modify: `apps/knowledge/urls.py`
- Modify: `apps/knowledge/api/document.py`
- Test: `apps/knowledge/test_split_preview_progress.py`

**Interfaces:**
- `POST .../document/split/task`
- `GET .../document/split/task/<task_id>`

- [ ] Write endpoint tests for task creation, enqueue failure cleanup, missing/expired state, and ownership mismatch.
- [ ] Reuse the current Split permission decorators on both endpoints.
- [ ] Save uploaded inputs as temporary File records with `source_id=task_id`.
- [ ] Create state before enqueue and return `{task_id, status}`.
- [ ] Validate user/workspace/knowledge ownership before returning status.
- [ ] Keep `/document/split` unchanged.

### Task 5: Frontend task APIs and draft state

**Files:**
- Modify: `ui/src/api/knowledge/document.ts`
- Modify: `ui/src/api/system-shared/document.ts`
- Modify: `ui/src/api/system-resource-management/document.ts`
- Modify: `ui/src/stores/modules/knowledge.ts`

**Interfaces:**
- `postSplitDocumentTask(knowledgeId, formData, onUploadProgress)`.
- `getSplitDocumentTask(knowledgeId, taskId)`.

- [ ] Add both API methods to all dynamic document API variants.
- [ ] Extend `DocumentUploadDraft` with backend task ID, stage, counts, and message.
- [ ] Run TypeScript type-check.

### Task 6: Real progress polling UI

**Files:**
- Modify: `ui/src/views/document/upload/SetRules.vue`
- Modify: `ui/src/locales/lang/zh-CN/views/document.ts`
- Modify: `ui/src/locales/lang/en-US/views/document.ts`

**Interfaces:**
- Poll task status every 1000 ms until `completed`, `failed`, or expired.

- [ ] Replace the synchronous call with task creation followed by polling.
- [ ] Preserve true Axios upload percentage during upload; remove the fixed 95% state.
- [ ] Render stage message and `processed / total · remaining` only when total is known.
- [ ] Restore polling from the Pinia draft on mount.
- [ ] Stop polling before a new task and on component unmount.
- [ ] Run ESLint and `npm run type-check`.

### Task 7: Verification and review

**Files:**
- Review all modified files and the two design/plan documents.

- [ ] Run targeted Django tests for PDF images, two-stage vision splitting, and split progress.
- [ ] Run Ruff on all changed Python files.
- [ ] Run `./scripts/validate-code-rules.sh`.
- [ ] Run `git diff --check` and inspect `git status --short`.
- [ ] Request read-only code review focused on task ownership, temporary-file cleanup, cache leaks, polling lifecycle, and old endpoint compatibility.
- [ ] Fix all Critical and Important findings, then repeat verification.
