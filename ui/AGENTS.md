# Web 前端编码规范

本目录是 MaxKB 管理端前端代码。

## 快速规则

- 先复用，后新增：新建模块前先找现有实现。
- 有相似实现时，优先小步通用化改造，不做过度设计。
- 本项目默认 `VITE_KNOWLEDGE_ONLY=true`，不要在知识库单体模式中重新暴露应用、聊天、触发器、工具入口。
- API 请求统一放在 `src/api/`，组件只处理展示和交互。
- 路由配置统一放在 `src/router/`，新增页面优先懒加载。
- 所有用户可见新文案优先走 `src/locales/` 的现有 i18n 体系。
- 字体禁止使用海外 CDN，优先系统字体或 `src/styles/font/` 本地字体。
- 不确定实现方式时，先在现有代码中搜索再动手。

## 技术栈

- Vue 3 + TypeScript + Vite
- Element Plus + SCSS
- Pinia + Vue Router + Axios + Vue I18n

## 组件与模块

- 组件文件名使用 `PascalCase`，如 `UserCard.vue`。
- Props 必须有明确类型；确实需要兼容历史代码时才使用 `any`。
- 模板避免复杂表达式，复杂逻辑放到计算属性或方法中。
- 组件样式默认使用 `<style scoped>`，全局样式放到既有全局样式文件。
- 单个组件建议不超过 300 行，单个函数建议不超过 50 行。
- 避免深层嵌套，优先 early return。

## TypeScript

- 对象类型优先 `interface`，联合/交叉类型使用 `type`。
- 需要兜底时优先 `unknown`，避免新增不必要的 `any`。
- 统一使用 `@/` 引用 `src/` 路径。
- 不要通过类型断言掩盖真实数据结构问题。

## 样式与资源

- 复杂样式使用 SCSS，保持现有 Element Plus 视觉体系。
- 静态图片放在 `public/` 或 `src/assets/`。
- 小图标优先使用现有图标组件、Element Plus 图标或项目已有 SVG。
- 页面文字、按钮、卡片内容必须在移动端和桌面端都不溢出。

## 数据请求与状态

- Axios 拦截器统一处理通用错误。
- 组件局部状态用 `ref/reactive`，全局状态用 Pinia。
- Store 命名统一 `useXxxStore`。
- 前端展示图片字段优先使用 `image_url`，传给后端参数时遵守既有接口命名。

## 推荐校验

```bash
./scripts/validate-code-rules.sh
```

针对前端的最小手动检查：

```bash
cd ui
npm run type-check
npm run build
```

