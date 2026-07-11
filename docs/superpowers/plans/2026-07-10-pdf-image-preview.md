# PDF Image Preview Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist images extracted from PDFs and emit valid OSS Markdown references in document previews.

**Architecture:** `PdfSplitHandle` extracts images once into `File` objects and a page-indexed Markdown map. All PDF parsing paths consume that map, while the existing serializer-owned `save_image` callback persists the files.

**Tech Stack:** Python 3.11, Django 5.2, pypdf 6.10, unittest/Django SimpleTestCase.

## Global Constraints

- No database schema changes or new dependencies.
- Preserve the existing `save_image` callback contract and `./oss/file/<UUID>` URL format.
- Existing drafts require regeneration; no data migration is added.

---

### Task 1: Lock PDF image extraction behavior

**Files:**
- Create: `apps/common/handle/impl/text/tests/__init__.py`
- Create: `apps/common/handle/impl/text/tests/test_pdf_split_handle.py`
- Modify: `apps/common/handle/impl/text/pdf_split_handle.py`

**Interfaces:**
- Produces: `PdfSplitHandle.extract_document_images(pdf_document) -> tuple[dict[int, list[str]], list[File]]`
- Consumes: pypdf image objects exposing `name` and `data`.

- [ ] **Step 1: Write a failing test** asserting one fake PDF image becomes a `File` with the original bytes and a `![image](./oss/file/<UUID>)` page reference.
- [ ] **Step 2: Run** `MAXKB_CONFIG=ENV MAXKB_CONFIG_TYPE=ENV PYTHONPATH=apps .venv/bin/python apps/manage.py test common.handle.impl.text.tests.test_pdf_split_handle -v 2` and confirm failure because `extract_document_images` does not exist.
- [ ] **Step 3: Implement** `extract_document_images`, pass its page map into the normal, TOC, link, and raw-content parsing paths, and call `save_image` once per PDF.
- [ ] **Step 4: Re-run the targeted test** and confirm it passes.

### Task 2: Verify repository compatibility

**Files:**
- Verify: `apps/common/handle/impl/text/pdf_split_handle.py`
- Verify: `apps/common/handle/impl/text/tests/test_pdf_split_handle.py`

**Interfaces:**
- Consumes: the completed PDF image extraction behavior from Task 1.
- Produces: verification evidence only.

- [ ] **Step 1: Run Ruff** with `.venv/bin/ruff check apps/common/handle/impl/text/pdf_split_handle.py apps/common/handle/impl/text/tests/test_pdf_split_handle.py`.
- [ ] **Step 2: Run Django check** with the repository development environment variables.
- [ ] **Step 3: Run** `./scripts/validate-code-rules.sh` and inspect all output.
- [ ] **Step 4: Review** `git diff --check` and the final diff for unrelated changes.
