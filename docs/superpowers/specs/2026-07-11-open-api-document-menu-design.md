# 开放接口文档菜单设计

## 目标

在系统管理中增加“开放接口文档”菜单。用户进入页面后可以阅读现有 Knowledge Open API Markdown 文档，并直接下载 Markdown 文件。

## 页面与路由

- 菜单位置：系统管理。
- 菜单名称：开放接口文档。
- 前端路由：`/system/open-api-document`。
- 页面权限与现有 `/system/open-api` 一致，不新增权限常量。

## 页面结构

- 顶部展示标题和说明。
- 右上角提供“下载 Markdown”按钮。
- 主体通过现有 `MdPreview` 组件渲染 Markdown。
- 加载时显示 loading，加载失败时显示明确错误和重试按钮。
- 窄屏下按钮允许换行，正文保持可滚动和代码块可读。

## 数据来源

- Markdown 内容：`GET /openapi/knowledge/docs/content`。
- 下载：浏览器打开 `/openapi/knowledge/docs/download`。
- Markdown 源文件仍为 `docs/openapi/knowledge-document-upload.md`，不复制内容到前端。

## 影响范围

- 新增一个 Vue 页面。
- 增加系统路由和中英文文案。
- 不修改数据库，不新增依赖，不改变现有开放接口。

## 验证

- TypeScript 类型检查通过。
- 新页面 ESLint 通过。
- 项目代码规则校验通过。
- 验证菜单权限、Markdown 加载、失败重试和下载链接。
