# Two-Stage Vision Document Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `llm_vision` use a configurable vision model to classify and describe original PDF images, then a configurable text LLM to perform the final semantic split.

**Architecture:** Extend the existing upload request with separate `vision_model_id` and `llm_model_id`. Reuse the PDF parser's persisted original image references, process them page-context-first in bounded vision batches, remove rejected image references/files, enrich kept references with descriptions, then pass the enriched text through the existing LLM JSON split pipeline with strict image-ID conservation validation.

**Tech Stack:** Django REST Framework, LangChain messages, pypdf/Pillow, Vue 3, TypeScript, Element Plus, Pinia.

## Global Constraints

- Do not add dependencies or database migrations.
- Do not hardcode model vendors or model names; validate MaxKB model types only.
- Preserve `llm_text` and non-model split behavior.
- Do not stage, commit, or push Git changes.
- Use TDD for backend behavior and run repository validation before completion.

---

### Task 1: Lock the two-model API contract

**Files:**
- Modify: `apps/knowledge/serializers/document.py`
- Modify: `apps/knowledge/api/document.py`
- Modify: `apps/knowledge/views/document.py`
- Create: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Consumes: multipart fields `split_strategy`, `model_id`, `vision_model_id`, `llm_model_id`.
- Produces: validated model IDs passed into `file_to_paragraph` and `_apply_model_split`.

- [ ] **Step 1: Write failing serializer tests**

Add tests that assert `llm_vision` rejects a missing vision or text model ID, `_get_model_instance(id, expected_type)` rejects the wrong model type, and `llm_text` still accepts `model_id`.

- [ ] **Step 2: Run the targeted tests and verify failure**

Run:

```bash
MAXKB_CONFIG_TYPE=ENV MAXKB_LOG_DIR=.local/maxkb/logs \
MAXKB_DB_NAME=maxkb MAXKB_DB_HOST=127.0.0.1 MAXKB_DB_PORT=5432 \
MAXKB_DB_USER=root MAXKB_DB_PASSWORD='Password123@postgres' \
MAXKB_REDIS_HOST=127.0.0.1 MAXKB_REDIS_PORT=6380 \
MAXKB_REDIS_PASSWORD='Password123@redis' MAXKB_REDIS_DB=0 \
MAXKB_REDIS_MAX_CONNECTIONS=100 \
.venv/bin/python apps/manage.py test knowledge.test_document_vision_split --keepdb
```

Expected: failures showing the new fields and validation helpers are missing.

- [ ] **Step 3: Implement the request fields and validation**

Add UUID fields to `DocumentSplitRequest`, forward both fields in the view, and resolve models through one helper that accepts an explicit expected `ModelTypeConst` value. Keep `model_id` unchanged for `llm_text`.

- [ ] **Step 4: Run the targeted tests**

Expected: contract tests pass.

### Task 2: Add conservative image prefiltering and vision result validation

**Files:**
- Modify: `apps/knowledge/serializers/document.py`
- Test: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Produces: `_is_meaningful_image_candidate(image_bytes) -> bool` and `_normalize_vision_images(payload, expected_ids) -> dict[str, dict]`.

- [ ] **Step 1: Write failing image-filter tests**

Generate Pillow fixtures for a 1x1 image, a fully transparent image, a solid-color image, and a textured diagram. Assert the first three are rejected and the diagram is retained.

- [ ] **Step 2: Write failing vision JSON tests**

Assert valid results are normalized while missing IDs, unknown IDs, duplicate IDs, empty kept descriptions, and invalid JSON raise `AppApiException`.

- [ ] **Step 3: Run tests and verify failure**

Expected: helper methods do not yet exist.

- [ ] **Step 4: Implement conservative helpers**

Decode through Pillow, reject undecodable/tiny/extreme/transparent/near-solid candidates, and validate exact one-to-one coverage of expected candidate IDs.

- [ ] **Step 5: Run tests**

Expected: filter and validation tests pass.

### Task 3: Implement bounded per-page vision enrichment

**Files:**
- Modify: `apps/knowledge/serializers/document.py`
- Test: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Produces: `_enrich_paragraphs_with_vision(document_name, paragraphs, vision_model) -> tuple[list[dict], set[str]]`.
- Batch size: at most 4 original images per vision request.

- [ ] **Step 1: Write failing batch tests**

Create paragraph fixtures with image references and mocked `File.get_bytes()`. Assert five candidates cause two vision calls, both calls include the same page text, and candidate IDs are explicitly paired with image content.

- [ ] **Step 2: Write failing enrichment tests**

Return one kept diagram and one rejected background. Assert the diagram receives a searchable `图片说明：...` immediately before its unchanged Markdown reference, while the background reference is removed.

- [ ] **Step 3: Run tests and verify failure**

Expected: vision enrichment method is missing.

- [ ] **Step 4: Implement vision calls**

Build `HumanMessage` content from page text plus alternating candidate-ID labels and Base64 image items. Require strict JSON, validate all IDs, collect kept descriptions, and remove rejected references from the page content.

- [ ] **Step 5: Run tests**

Expected: batching and enrichment tests pass.

### Task 4: Enforce image conservation during final text splitting

**Files:**
- Modify: `apps/knowledge/serializers/document.py`
- Test: `apps/knowledge/test_document_vision_split.py`

**Interfaces:**
- Consumes: vision-enriched paragraphs and the selected `LLM` model.
- Produces: final paragraphs whose image ID multiset exactly equals the enriched input image ID set.

- [ ] **Step 1: Write failing conservation tests**

Mock text-model outputs that preserve, drop, invent, and duplicate image references. Assert only the preserving result succeeds.

- [ ] **Step 2: Run tests and verify failure**

Expected: current model split accepts invalid image sets.

- [ ] **Step 3: Implement the two-stage orchestration**

For `llm_vision`, resolve both models, run vision enrichment first, then call the existing text split code with the `LLM` instance. Compare input and output image counters and reject image-only paragraphs without descriptions.

- [ ] **Step 4: Implement cleanup on failure**

Track image file IDs created by the current preview request. On any vision/text failure, delete only those request-owned image records/files; never delete pre-existing files.

- [ ] **Step 5: Run tests**

Expected: orchestration, conservation, and cleanup tests pass.

### Task 5: Update the upload UI to select two models

**Files:**
- Modify: `ui/src/views/document/upload/SetRules.vue`
- Modify: `ui/src/stores/modules/knowledge.ts`
- Modify: `ui/src/locales/lang/zh-CN/views/document.ts`
- Modify: `ui/src/locales/lang/en-US/views/document.ts`

**Interfaces:**
- Produces multipart fields `vision_model_id` and `llm_model_id` for `llm_vision`.

- [ ] **Step 1: Render two model selectors for `radio === '4'`**

Bind the first to `form.vision_model_id` using `IMAGE` options and the second to `form.llm_model_id` using `LLM` options. Add localized labels for both roles.

- [ ] **Step 2: Update validation and draft persistence**

Disable preview unless both IDs are present for `llm_vision`; preserve both IDs in the Pinia draft. Keep `llm_text` validation limited to the LLM ID.

- [ ] **Step 3: Update request construction**

Submit `model_id` for `llm_text`; submit `vision_model_id` and `llm_model_id` for `llm_vision`.

- [ ] **Step 4: Run frontend checks**

Run:

```bash
cd ui
./node_modules/.bin/eslint src/views/document/upload/SetRules.vue src/stores/modules/knowledge.ts
npm run type-check
```

Expected: ESLint and type-check pass.

### Task 6: Update OpenAPI and run full verification

**Files:**
- Modify: `ui/src/views/system/open-api/index.vue`
- Modify: `ui/src/locales/lang/zh-CN/views/system.ts`
- Modify: `ui/src/locales/lang/en-US/views/system.ts`
- Modify: generated/static API comments only if required by existing project convention.

- [ ] **Step 1: Update the OpenAPI example form**

Expose separate vision and text model selectors/fields for `llm_vision`, while leaving `llm_text` on `model_id`.

- [ ] **Step 2: Run backend targeted tests and lint**

Run the Task 1 Django test command plus:

```bash
.venv/bin/ruff check apps/knowledge/serializers/document.py \
  apps/knowledge/api/document.py apps/knowledge/views/document.py \
  apps/knowledge/test_document_vision_split.py
```

- [ ] **Step 3: Run Django and repository validation**

Run:

```bash
./scripts/validate-code-rules.sh
```

Expected: all checks pass; only pre-existing URL warnings may remain.

- [ ] **Step 4: Review the final diff**

Run `git diff --check` and confirm there are no unrelated modifications, dependencies, migrations, staged files, commits, or pushes.
