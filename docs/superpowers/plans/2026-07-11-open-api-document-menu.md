# 开放接口文档菜单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在系统管理中新增可阅读并下载 Knowledge Open API Markdown 文档的独立菜单页面。

**Architecture:** 新页面从现有公开 Markdown 内容接口加载正文并交给全局 `MdPreview` 渲染；下载与公开页面直接使用既有后端 URL。路由复用开放 API 密钥管理页的权限表达式。

**Tech Stack:** Vue 3、TypeScript、Element Plus、Vue Router、md-editor-v3。

## Global Constraints

- 不新增依赖。
- 不修改数据库和现有开放接口。
- 页面权限与 `/system/open-api` 一致。
- Markdown 只维护 `docs/openapi/knowledge-document-upload.md` 一份。

---

### Task 1: 独立 Markdown 文档页面

**Files:**
- Create: `ui/src/views/system/open-api-document/index.vue`

**Interfaces:**
- Consumes: `GET /openapi/knowledge/docs/content`
- Produces: `/system/open-api-document` 页面组件

- [ ] 创建页面，使用 `fetch` 读取 Markdown，并通过全局 `MdPreview` 渲染。
- [ ] 增加 loading、错误提示、重试按钮和下载按钮。
- [ ] 对新 Vue 文件运行 ESLint。

### Task 2: 系统菜单路由与国际化

**Files:**
- Modify: `ui/src/router/modules/system.ts`
- Modify: `ui/src/locales/lang/zh-CN/views/system.ts`
- Modify: `ui/src/locales/lang/en-US/views/system.ts`

**Interfaces:**
- Consumes: Task 1 页面组件
- Produces: 系统管理菜单项 `views.system.knowledgeOpenAPIDocument.title`

- [ ] 新增 `/system/open-api-document` 路由，复用 `/system/open-api` 权限。
- [ ] 增加中英文标题、说明、按钮和错误文案。
- [ ] 运行前端 TypeScript 类型检查。

### Task 3: 完整验证

**Files:**
- Verify: `ui/src/views/system/open-api-document/index.vue`
- Verify: `ui/src/router/modules/system.ts`

- [ ] 运行变更文件 ESLint。
- [ ] 运行 `npm run type-check`。
- [ ] 运行 `./scripts/validate-code-rules.sh`。
- [ ] 运行 `git diff --check`。
