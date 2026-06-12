import type { RouteRecordRaw } from 'vue-router'
import knowledgeRoute from './modules/knowledge'
import knowledgeChatRoute from './modules/knowledge-chat'
import modelRoute from './modules/model'
import documentRoute from './modules/document'
import paragraphRoute from './modules/paragraph'
import systemRoute from './modules/system'

const rolesRoutes: RouteRecordRaw[] = [
  knowledgeRoute,
  knowledgeChatRoute,
  modelRoute,
  documentRoute,
  paragraphRoute,
  systemRoute,
]

const baseRoutes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'root',
    redirect: '/knowledge',
    children: [
      ...rolesRoutes,
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

export const routes: Array<RouteRecordRaw> = baseRoutes
