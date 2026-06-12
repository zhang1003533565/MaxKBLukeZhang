import type { RouteRecordRaw } from 'vue-router'
import { isKnowledgeOnly } from '@/utils/knowledge-only'

const modules: any = import.meta.glob('./modules/*.ts', { eager: true })

const knowledgeOnlyModuleNames = new Set(['knowledge.ts', 'model.ts', 'document.ts', 'paragraph.ts', 'system.ts'])
const knowledgeOnlyRouteNames = new Set([
  'ApplicationWorkflow',
  'KnowledgeWorkflow',
  'ToolWorkflow',
  'Chat',
  'demo',
  'UserLogin',
  'application',
  'application-index',
  'ApplicationDetail',
  'tool',
  'tool-index',
  'trigger',
  'trigger-index',
  'knowledgeWorkflowSetting',
  'ApplicationResourceIndex',
  'ToolResourceIndex',
  'authorizationApplication',
  'authorizationTool',
  'tools',
  'SystemChat',
  'ChatUser',
  'Group',
  'Authentication',
])

const knowledgeOnlyPathPrefixes = [
  '/application',
  '/tool',
  '/trigger',
  '/chat',
  '/demo',
  '/user-login',
  '/system/chat',
  '/system/resource-management/application',
  '/system/resource-management/tool',
  '/system/authorization/application',
  '/system/authorization/tool',
  '/system/shared/tool',
]

const isKnowledgeOnlyRoute = (route: RouteRecordRaw) => {
  const routeName = route.name?.toString()
  const routePath = route.path
  return (
    !routeName ||
    !knowledgeOnlyRouteNames.has(routeName) &&
      !knowledgeOnlyPathPrefixes.some((path) => routePath.startsWith(path))
  )
}

const filterKnowledgeOnlyRoutes = (routeList: RouteRecordRaw[]): RouteRecordRaw[] =>
  routeList
    .filter(isKnowledgeOnlyRoute)
    .map((route) => {
      const filteredRoute = { ...route } as RouteRecordRaw
      if (route.children) {
        filteredRoute.children = filterKnowledgeOnlyRoutes(route.children)
      }
      return filteredRoute
    })

const moduleKeys = Object.keys(modules).filter((key) => {
  if (!isKnowledgeOnly) {
    return true
  }
  return knowledgeOnlyModuleNames.has(key.split('/').pop() || '')
})

const rolesRoutes: RouteRecordRaw[] = [...moduleKeys.map((key) => modules[key].default)]

const baseRoutes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'root',
    redirect: '/home',
    children: [
      ...rolesRoutes,
      {
        path: '/home',
        name: 'home',
        redirect: '/home',
        meta: {
          title: 'home.title',
          menu: true,
          order: 1,
          icon: 'app-home',
          iconActive: 'app-home-active',
          group: 'workspace',
        },
        children: [
          {
            path: '/home',
            name: 'home-index',
            meta: {
              title: 'home.title',
              activeMenu: '/home',
              sameRoute: 'home',
            },
            component: () => import('@/views/home/index.vue'),
          },
        ],
        component: () => import('@/layout/layout-template/SimpleLayout.vue'),
      },
      {
        path: '/no-permission',
        name: 'noPermission',
        redirect: '/no-permission',
        meta: {},
        children: [
          {
            path: '/no-permission',
            name: 'noPermissionD',
            meta: {},
            component: () => import('@/views/error/NoPermission.vue'),
          },
        ],
        component: () => import('@/layout/layout-template/SimpleLayout.vue'),
      },
    ],
  },

  // 高级编排
  {
    path: '/application/:from/:id/workflow',
    name: 'ApplicationWorkflow',
    meta: { activeMenu: '/application' },
    component: () => import('@/views/application-workflow/index.vue'),
  },
  // 知识库工作流
  {
    path: '/knowledge/:id/:folderId/workflow',
    name: 'KnowledgeWorkflow',
    meta: { activeMenu: '/knowledge' },
    component: () => import('@/views/knowledge-workflow/index.vue'),
  },
  {
    path: '/tool/:id/:folderId/workflow',
    name: 'ToolWorkflow',
    meta: { activeMenu: '/tool' },
    component: () => import('@/views/tool-workflow/index.vue'),
  },
  // 对话
  {
    path: '/chat/:accessToken',
    name: 'Chat',
    component: () => import('@/views/chat/index.vue'),
  },
  {
    path: '/demo',
    name: 'demo',
    component: () => import('@/views/demo/index.vue'),
  },

  // 对话用户登录
  {
    path: '/user-login/:accessToken',
    name: 'UserLogin',
    component: () => import('@/views/chat/user-login/index.vue'),
  },

  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login/index.vue'),
  },
  {
    path: '/forgot_password',
    name: 'ForgotPassword',
    component: () => import('@/views/login/ForgotPassword.vue'),
  },
  {
    path: '/reset_password/:code/:email',
    name: 'ResetPassword',
    component: () => import('@/views/login/ResetPassword.vue'),
  },
  {
    path: '/permission',
    name: 'permission',
    component: () => import('@/views/Permission.vue'),
  },
  {
    path: '/no-service',
    name: 'NoService',
    component: () => import('@/views/error/NoService.vue'),
  },
  {
    path: '/:pathMatch(.*)',
    name: '404',
    component: () => import('@/views/error/404.vue'),
  },
]

export const routes: Array<RouteRecordRaw> = isKnowledgeOnly
  ? filterKnowledgeOnlyRoutes(baseRoutes)
  : baseRoutes
