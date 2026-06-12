# coding=utf-8
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from system_manage.serializers.open_api import KnowledgeOpenAPIKeySerializer


class KnowledgeOpenAPIKeyView(APIView):
    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=["GET"],
        description=_("Knowledge Open API key list"),
        summary=_("Knowledge Open API key list"),
        tags=[_("System parameters")],
    )
    @has_permissions(
        RoleConstants.ADMIN,
        RoleConstants.USER,
        RoleConstants.WORKSPACE_MANAGE,
        PermissionConstants.SYSTEM_API_KEY_EDIT,
    )
    def get(self, request: Request):
        return result.success(
            KnowledgeOpenAPIKeySerializer.list(
                request.user,
                request.query_params.get("workspace_id"),
            )
        )

    @extend_schema(
        methods=["POST"],
        description=_("Create Knowledge Open API key"),
        summary=_("Create Knowledge Open API key"),
        tags=[_("System parameters")],
    )
    @has_permissions(
        RoleConstants.ADMIN,
        RoleConstants.USER,
        RoleConstants.WORKSPACE_MANAGE,
        PermissionConstants.SYSTEM_API_KEY_EDIT,
    )
    def post(self, request: Request):
        return result.success(KnowledgeOpenAPIKeySerializer.create(request.user, request.data))

    class Operate(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            description=_("Modify Knowledge Open API key"),
            summary=_("Modify Knowledge Open API key"),
            tags=[_("System parameters")],
        )
        @has_permissions(
            RoleConstants.ADMIN,
            RoleConstants.USER,
            RoleConstants.WORKSPACE_MANAGE,
            PermissionConstants.SYSTEM_API_KEY_EDIT,
        )
        def put(self, request: Request, key_id: str):
            return result.success(KnowledgeOpenAPIKeySerializer.edit(request.user, key_id, request.data))

        @extend_schema(
            methods=["DELETE"],
            description=_("Delete Knowledge Open API key"),
            summary=_("Delete Knowledge Open API key"),
            tags=[_("System parameters")],
        )
        @has_permissions(
            RoleConstants.ADMIN,
            RoleConstants.USER,
            RoleConstants.WORKSPACE_MANAGE,
            PermissionConstants.SYSTEM_API_KEY_EDIT,
        )
        def delete(self, request: Request, key_id: str):
            return result.success(KnowledgeOpenAPIKeySerializer.delete(request.user, key_id))
