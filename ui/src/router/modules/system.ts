import { PermissionConst, EditionConst, RoleConst } from '@/utils/permission/data'
import { ComplexPermission } from '@/utils/permission/type'

const systemRouter = {
  path: '/system',
  name: 'system',
  meta: {
    title: 'views.system.title',
    menu: true,
    permission: [
      RoleConst.ADMIN,
      RoleConst.USER.getWorkspaceRole,
      RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
      PermissionConst.SYSTEM_API_KEY_EDIT,
      PermissionConst.USER_READ,
      PermissionConst.WORKSPACE_READ,
      PermissionConst.WORKSPACE_WORKSPACE_READ.getWorkspacePermission,
      PermissionConst.ROLE_READ,
      PermissionConst.WORKSPACE_ROLE_READ.getWorkspacePermission,
      PermissionConst.KNOWLEDGE_WORKSPACE_USER_RESOURCE_PERMISSION_READ,
      PermissionConst.KNOWLEDGE_WORKSPACE_USER_RESOURCE_PERMISSION_READ
        .getWorkspacePermissionWorkspaceManageRole,
      PermissionConst.MODEL_WORKSPACE_USER_RESOURCE_PERMISSION_READ,
      PermissionConst.MODEL_WORKSPACE_USER_RESOURCE_PERMISSION_READ
        .getWorkspacePermissionWorkspaceManageRole,
    ],
    icon: 'app-setting',
    iconActive: 'app-setting-active',
    order: 8,
  },
  redirect: '/system/user',
  component: () => import('@/layout/layout-template/SystemMainLayout.vue'),
  children: [
    {
      path: '/system/user',
      name: 'user',
      meta: {
        icon: 'User',
        iconActive: 'UserFilled',
        title: 'views.userManage.title',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'user',
        permission: [RoleConst.ADMIN, PermissionConst.USER_READ],
      },
      component: () => import('@/views/system/user-manage/index.vue'),
    },
    {
      path: '/system/workspace',
      name: 'workspace',
      meta: {
        icon: 'app-workspace',
        iconActive: 'app-workspace-active',
        title: 'views.workspace.title',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'workspace',
        permission: [
          new ComplexPermission(
            [RoleConst.WORKSPACE_MANAGE, RoleConst.ADMIN],
            [PermissionConst.WORKSPACE_WORKSPACE_READ, PermissionConst.WORKSPACE_READ],
            [EditionConst.IS_EE],
            'OR',
          ),
        ],
      },
      component: () => import('@/views/system/workspace/index.vue'),
    },
    {
      path: '/system/role',
      name: 'role',
      meta: {
        icon: 'app-role',
        iconActive: 'app-role-active',
        title: 'views.role.title',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'role',
        permission: [
          new ComplexPermission(
            [RoleConst.ADMIN, RoleConst.WORKSPACE_MANAGE.getWorkspaceRole],
            [PermissionConst.ROLE_READ, PermissionConst.WORKSPACE_ROLE_READ],
            [EditionConst.IS_EE, EditionConst.IS_PE],
            'OR',
          ),
        ],
      },
      component: () => import('@/views/system/role/index.vue'),
    },

    {
      path: '/system/resource-management',
      name: 'resourceManagement',
      meta: {
        icon: 'app-resource-management',
        iconActive: 'app-resource-management',
        title: 'views.system.resource_management.label',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        permission: [
          new ComplexPermission(
            [RoleConst.ADMIN],
            [PermissionConst.RESOURCE_KNOWLEDGE_READ],
            [EditionConst.IS_EE],
            'OR',
          ),
          new ComplexPermission(
            [RoleConst.ADMIN],
            [PermissionConst.RESOURCE_MODEL_READ],
            [EditionConst.IS_EE],
            'OR',
          ),
        ],
      },
      children: [
        {
          path: '/system/resource-management/knowledge',
          name: 'KnowledgeResourceIndex',
          meta: {
            title: 'views.knowledge.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            sameRoute: 'workspace',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.RESOURCE_KNOWLEDGE_READ],
                [EditionConst.IS_EE],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-resource-management/KnowledgeResourceIndex.vue'),
        },
        {
          path: '/system/resource-management/model',
          name: 'ModelResourceIndex',
          meta: {
            title: 'views.model.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.RESOURCE_MODEL_READ],
                [EditionConst.IS_EE],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-resource-management/ModelResourceIndex.vue'),
        },
      ],
    },
    {
      path: '/system/authorization',
      name: 'authorization',
      meta: {
        icon: 'app-resource-authorization',
        iconActive: 'app-resource-authorization-active',
        title: 'views.system.resourceAuthorization.title',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'authorization',
        permission: [
          new ComplexPermission(
            [RoleConst.ADMIN, RoleConst.WORKSPACE_MANAGE],
            [
              PermissionConst.KNOWLEDGE_WORKSPACE_USER_RESOURCE_PERMISSION_READ,
              PermissionConst.KNOWLEDGE_WORKSPACE_USER_RESOURCE_PERMISSION_READ
              .getWorkspacePermissionWorkspaceManageRole,
            ],
            [],
            'OR',
          ),
          new ComplexPermission(
            [RoleConst.ADMIN, RoleConst.WORKSPACE_MANAGE],
            [
              PermissionConst.MODEL_WORKSPACE_USER_RESOURCE_PERMISSION_READ,
              PermissionConst.MODEL_WORKSPACE_USER_RESOURCE_PERMISSION_READ
                .getWorkspacePermissionWorkspaceManageRole,
            ],
            [],
            'OR',
          ),
        ],
      },

      children: [
        {
          path: '/system/authorization/knowledge',
          name: 'authorizationKnowledge',
          meta: {
            title: 'views.knowledge.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            resource: 'KNOWLEDGE',
            sameRoute: 'authorization',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN, RoleConst.WORKSPACE_MANAGE],
                [
                  PermissionConst.KNOWLEDGE_WORKSPACE_USER_RESOURCE_PERMISSION_READ,
                  PermissionConst.KNOWLEDGE_WORKSPACE_USER_RESOURCE_PERMISSION_READ
                    .getWorkspacePermissionWorkspaceManageRole,
                ],
                [],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system/resource-authorization/index.vue'),
        },
        {
          path: '/system/authorization/model',
          name: 'authorizationModel',
          meta: {
            title: 'views.model.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            resource: 'MODEL',
            sameRoute: 'authorization',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN, RoleConst.WORKSPACE_MANAGE],
                [
                  PermissionConst.MODEL_WORKSPACE_USER_RESOURCE_PERMISSION_READ,
                  PermissionConst.MODEL_WORKSPACE_USER_RESOURCE_PERMISSION_READ
                    .getWorkspacePermissionWorkspaceManageRole,
                ],
                [],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system/resource-authorization/index.vue'),
        },
      ],
    },
    {
      path: '/system/open-api',
      name: 'knowledgeOpenAPI',
      meta: {
        icon: 'Connection',
        iconActive: 'Connection',
        title: 'views.system.knowledgeOpenAPI.title',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'knowledgeOpenAPI',
        permission: [
          RoleConst.ADMIN,
          RoleConst.USER.getWorkspaceRole,
          RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
          PermissionConst.SYSTEM_API_KEY_EDIT,
        ],
      },
      component: () => import('@/views/system/open-api/index.vue'),
    },
    {
      path: '/system/shared',
      name: 'shared',
      meta: {
        icon: 'app-shared',
        iconActive: 'app-shared-active',
        title: 'views.shared.shared_resources',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        permission: [
          new ComplexPermission(
            [RoleConst.ADMIN],
            [PermissionConst.SHARED_KNOWLEDGE_READ],
            [EditionConst.IS_EE],
            'OR',
          ),
          new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.SHARED_MODEL_READ],
                [EditionConst.IS_EE],
                'OR',
              ),
        ],
      },
      children: [
        {
          path: '/system/shared/knowledge',
          name: 'knowledgeBase',
          meta: {
            title: 'views.knowledge.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.SHARED_KNOWLEDGE_READ],
                [EditionConst.IS_EE],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-shared/KnowLedgeSharedIndex.vue'),
        },
        {
          path: '/system/shared/model',
          name: 'models',
          meta: {
            title: 'views.model.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.SHARED_MODEL_READ],
                [EditionConst.IS_EE],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-shared/ModelSharedIndex.vue'),
        },
      ],
    },
    {
      path: '/system/setting',
      name: 'setting',
      meta: {
        icon: 'app-setting',
        iconActive: 'app-setting-active',
        title: 'views.system.subTitle',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'setting',
        permission: [
          new ComplexPermission(
            [RoleConst.ADMIN],
            [PermissionConst.APPEARANCE_SETTINGS_READ],
            [EditionConst.IS_EE, EditionConst.IS_PE],
            'OR',
          ),
          new ComplexPermission(
            [RoleConst.ADMIN],
            [PermissionConst.LOGIN_AUTH_READ],
            [EditionConst.IS_EE, EditionConst.IS_PE],
            'OR',
          ),
          new ComplexPermission([RoleConst.ADMIN], [PermissionConst.EMAIL_SETTING_READ], [], 'OR'),
        ],
      },
      children: [
        {
          path: '/system/setting/theme',
          name: 'theme',
          meta: {
            title: 'theme.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            sameRoute: 'setting',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.APPEARANCE_SETTINGS_READ],
                [EditionConst.IS_EE, EditionConst.IS_PE],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-setting/theme/index.vue'),
        },
        {
          path: '/system/authentication',
          name: 'SystemAuthentication',
          meta: {
            title: 'views.system.authentication.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            sameRoute: 'setting',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.LOGIN_AUTH_READ],
                [EditionConst.IS_EE, EditionConst.IS_PE],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-setting/authentication/index.vue'),
        },
        {
          path: '/system/email',
          name: 'email',
          meta: {
            title: 'views.system.email.title',
            activeMenu: '/system',
            parentPath: '/system',
            parentName: 'system',
            sameRoute: 'setting',
            permission: [
              new ComplexPermission(
                [RoleConst.ADMIN],
                [PermissionConst.EMAIL_SETTING_READ],
                [],
                'OR',
              ),
            ],
          },
          component: () => import('@/views/system-setting/email/index.vue'),
        },
      ],
    },
    {
      path: '/operate',
      name: 'operate',
      meta: {
        icon: 'app-document',
        iconActive: 'app-document-active',
        title: 'views.operateLog.title',
        activeMenu: '/system',
        parentPath: '/system',
        parentName: 'system',
        sameRoute: 'operate',
        permission: [
          new ComplexPermission(
            [RoleConst.ADMIN],
            [PermissionConst.OPERATION_LOG_READ],
            [EditionConst.IS_EE, EditionConst.IS_PE],
            'OR',
          ),
        ],
      },
      component: () => import('@/views/system/operate-log/index.vue'),
    },
  ],
}

export default systemRouter
