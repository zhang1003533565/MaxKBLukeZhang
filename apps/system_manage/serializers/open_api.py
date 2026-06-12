# coding=utf-8
import secrets

import uuid_utils.compat as uuid
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from common.exception.app_exception import AppApiException
from system_manage.models import SettingType, SystemSetting
from users.serializers.user import get_workspace_list_by_user


OPEN_API_META_KEY = "knowledge_open_api_keys"


class KnowledgeOpenAPIKeyCreateRequest(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=64, label=_("name"))
    workspace_id = serializers.CharField(required=True, max_length=128, label=_("workspace id"))


class KnowledgeOpenAPIKeyEditRequest(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=64, label=_("name"))
    is_active = serializers.BooleanField(required=False, label=_("Is active"))


def _now():
    return timezone.now().isoformat()


def _get_setting():
    setting, _ = SystemSetting.objects.get_or_create(
        type=SettingType.KNOWLEDGE_OPEN_API,
        defaults={"meta": {OPEN_API_META_KEY: []}},
    )
    if not isinstance(setting.meta, dict):
        setting.meta = {OPEN_API_META_KEY: []}
    if OPEN_API_META_KEY not in setting.meta or not isinstance(setting.meta.get(OPEN_API_META_KEY), list):
        setting.meta[OPEN_API_META_KEY] = []
    return setting


def _workspace_map(user_id):
    return {str(workspace.get("id")): workspace for workspace in get_workspace_list_by_user(user_id)}


class KnowledgeOpenAPIKeySerializer(serializers.Serializer):
    @staticmethod
    def _serialize_key(row):
        return {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "secret_key": row.get("secret_key"),
            "workspace_id": row.get("workspace_id"),
            "workspace_name": row.get("workspace_name"),
            "user_id": row.get("user_id"),
            "username": row.get("username"),
            "nick_name": row.get("nick_name"),
            "is_active": row.get("is_active", True),
            "create_time": row.get("create_time"),
            "update_time": row.get("update_time"),
        }

    @staticmethod
    def list(user, workspace_id=None):
        setting = _get_setting()
        rows = setting.meta.get(OPEN_API_META_KEY, [])
        return [
            KnowledgeOpenAPIKeySerializer._serialize_key(row)
            for row in rows
            if row.get("user_id") == str(user.id)
            and (workspace_id in [None, "", row.get("workspace_id")])
        ]

    @staticmethod
    @transaction.atomic
    def create(user, instance):
        data = KnowledgeOpenAPIKeyCreateRequest(data=instance)
        data.is_valid(raise_exception=True)
        workspace_id = data.validated_data.get("workspace_id")
        workspace = _workspace_map(user.id).get(workspace_id)
        if workspace is None:
            raise AppApiException(403, _("No permission to access"))
        setting = SystemSetting.objects.select_for_update().filter(type=SettingType.KNOWLEDGE_OPEN_API).first()
        if setting is None:
            setting = _get_setting()
        keys = setting.meta.get(OPEN_API_META_KEY, [])
        now = _now()
        row = {
            "id": str(uuid.uuid7()),
            "name": data.validated_data.get("name") or str(_("Knowledge Open API Key")),
            "secret_key": "mkb_" + secrets.token_urlsafe(32),
            "workspace_id": workspace_id,
            "workspace_name": workspace.get("name") or workspace_id,
            "user_id": str(user.id),
            "username": user.username,
            "nick_name": user.nick_name,
            "is_active": True,
            "create_time": now,
            "update_time": now,
        }
        setting.meta = {**setting.meta, OPEN_API_META_KEY: [row, *keys]}
        setting.save(update_fields=["meta"])
        return KnowledgeOpenAPIKeySerializer._serialize_key(row)

    @staticmethod
    @transaction.atomic
    def edit(user, key_id, instance):
        data = KnowledgeOpenAPIKeyEditRequest(data=instance)
        data.is_valid(raise_exception=True)
        setting = SystemSetting.objects.select_for_update().filter(type=SettingType.KNOWLEDGE_OPEN_API).first()
        if setting is None:
            raise AppApiException(500, _("API key does not exist"))
        keys = setting.meta.get(OPEN_API_META_KEY, [])
        for row in keys:
            if row.get("id") == key_id and row.get("user_id") == str(user.id):
                if "name" in data.validated_data:
                    row["name"] = data.validated_data.get("name") or row.get("name")
                if "is_active" in data.validated_data:
                    row["is_active"] = data.validated_data.get("is_active")
                row["update_time"] = _now()
                setting.meta = {**setting.meta, OPEN_API_META_KEY: keys}
                setting.save(update_fields=["meta"])
                return KnowledgeOpenAPIKeySerializer._serialize_key(row)
        raise AppApiException(500, _("API key does not exist"))

    @staticmethod
    @transaction.atomic
    def delete(user, key_id):
        setting = SystemSetting.objects.select_for_update().filter(type=SettingType.KNOWLEDGE_OPEN_API).first()
        if setting is None:
            return True
        keys = setting.meta.get(OPEN_API_META_KEY, [])
        next_keys = [
            row
            for row in keys
            if not (row.get("id") == key_id and row.get("user_id") == str(user.id))
        ]
        setting.meta = {**setting.meta, OPEN_API_META_KEY: next_keys}
        setting.save(update_fields=["meta"])
        return True

    @staticmethod
    def get_by_secret(secret_key):
        setting = _get_setting()
        for row in setting.meta.get(OPEN_API_META_KEY, []):
            if row.get("secret_key") == secret_key:
                return KnowledgeOpenAPIKeySerializer._serialize_key(row)
        return None
