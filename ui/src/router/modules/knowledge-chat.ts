import { PermissionConst, RoleConst } from '@/utils/permission/data'

const KnowledgeChatRouter = {
  path: '/knowledge-chat',
  name: 'knowledge-chat',
  meta: {
    title: 'views.knowledge.chatTest.title',
    menu: true,
    permission: [
      RoleConst.USER.getWorkspaceRole,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.KNOWLEDGE_READ.getWorkspacePermission,
      PermissionConst.KNOWLEDGE_READ.getWorkspacePermissionWorkspaceManageRole,
      PermissionConst.KNOWLEDGE_HIT_TEST_READ.getWorkspacePermission,
      PermissionConst.KNOWLEDGE_HIT_TEST_READ.getWorkspacePermissionWorkspaceManageRole,
    ],
    icon: 'app-chat',
    group: 'workspace',
    order: 4,
  },
  redirect: '/knowledge-chat',
  component: () => import('@/layout/layout-template/SimpleLayout.vue'),
  children: [
    {
      path: '/knowledge-chat',
      name: 'knowledge-chat-index',
      meta: {
        title: 'views.knowledge.chatTest.title',
        activeMenu: '/knowledge-chat',
        sameRoute: 'knowledge-chat',
      },
      component: () => import('@/views/knowledge-test/ChatTest.vue'),
    },
  ],
}

export default KnowledgeChatRouter
