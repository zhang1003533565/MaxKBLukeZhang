# coding=utf-8
from dataclasses import dataclass

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request

from common.constants.permission_constants import ResourceAuthType, ResourcePermission
from common.exception.app_exception import AppAuthenticationFailed, AppUnauthorizedFailed
from knowledge.models import Knowledge
from system_manage.models import AuthTargetType, WorkspaceUserResourcePermission
from system_manage.serializers.open_api import KnowledgeOpenAPIKeySerializer
from users.models import User
from users.serializers.user import is_workspace_manage


@dataclass
class KnowledgeOpenAPIIdentity:
    key: dict
    user: User


def authenticate_open_api_key(request: Request) -> KnowledgeOpenAPIIdentity:
    auth = request.META.get("HTTP_AUTHORIZATION")
    if auth is None or not auth.startswith("Bearer "):
        raise AppAuthenticationFailed(1003, _("Open API key is required"))
    key = KnowledgeOpenAPIKeySerializer.get_by_secret(auth[7:])
    if key is None or not key.get("is_active"):
        raise AppAuthenticationFailed(1002, _("Invalid access token"))
    user = QuerySet(User).filter(id=key.get("user_id"), is_active=True).first()
    if user is None:
        raise AppAuthenticationFailed(1002, _("Authentication information is incorrect! illegal user"))
    return KnowledgeOpenAPIIdentity(key=key, user=user)


def check_workspace(identity: KnowledgeOpenAPIIdentity, workspace_id: str):
    if identity.key.get("workspace_id") != workspace_id:
        raise AppUnauthorizedFailed(403, _("No permission to access"))


def check_knowledge_permission(identity: KnowledgeOpenAPIIdentity, workspace_id: str, knowledge_id: str, manage=False):
    check_workspace(identity, workspace_id)
    if not QuerySet(Knowledge).filter(id=knowledge_id, workspace_id=workspace_id).exists():
        raise AppUnauthorizedFailed(403, _("No permission to access"))
    user_id = str(identity.user.id)
    if is_workspace_manage(user_id, workspace_id):
        return
    permission = (
        QuerySet(WorkspaceUserResourcePermission)
        .filter(
            auth_target_type=AuthTargetType.KNOWLEDGE,
            workspace_id=workspace_id,
            user_id=user_id,
            target=knowledge_id,
        )
        .first()
    )
    if permission is None:
        raise AppUnauthorizedFailed(403, _("No permission to access"))
    if permission.auth_type == ResourceAuthType.ROLE.value:
        if manage:
            raise AppUnauthorizedFailed(403, _("No permission to access"))
        return
    permission_list = [str(row) for row in permission.permission_list]
    if ResourcePermission.MANAGE.value in permission_list:
        return
    if not manage and ResourcePermission.VIEW.value in permission_list:
        return
    raise AppUnauthorizedFailed(403, _("No permission to access"))
