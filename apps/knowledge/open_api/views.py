# coding=utf-8
import json

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.exception.app_exception import AppApiException, AppUnauthorizedFailed
from common.utils.common import query_params_to_single_dict
from knowledge.models import Document, KnowledgeScope
from knowledge.open_api.auth import (
    authenticate_open_api_key,
    check_knowledge_permission,
    check_workspace,
)
from knowledge.serializers.document import DocumentSerializers
from knowledge.serializers.knowledge import KnowledgeSerializer
from knowledge.serializers.paragraph import ParagraphSerializers


def _page(request: Request):
    return int(request.query_params.get("current_page") or request.query_params.get("page") or 1)


def _page_size(request: Request):
    return int(request.query_params.get("page_size") or request.query_params.get("size") or 20)


def _to_bool(value):
    if value in [True, "true", "True", "1", "yes", "on"]:
        return True
    if value in [False, "false", "False", "0", "no", "off", "", None]:
        return False
    return bool(value)


def _get_patterns(request: Request):
    patterns = []
    if hasattr(request.data, "getlist"):
        patterns = [*request.data.getlist("patterns"), *request.data.getlist("patterns[]")]
    if not patterns and request.data.get("patterns"):
        raw_patterns = request.data.get("patterns")
        if isinstance(raw_patterns, str):
            try:
                parsed = json.loads(raw_patterns)
                patterns = parsed if isinstance(parsed, list) else [raw_patterns]
            except Exception:
                patterns = [raw_patterns]
        elif isinstance(raw_patterns, list):
            patterns = raw_patterns
    return [pattern for pattern in patterns if pattern]


class KnowledgeOpenAPIDocsView(APIView):
    def get(self, request: Request):
        return result.success(
            {
                "auth": "Authorization: Bearer <api_key>",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges",
                        "description": "分页获取当前 API Key 可访问的知识库",
                    },
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}",
                        "description": "获取知识库详情",
                    },
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents",
                        "description": "分页获取知识库文档",
                    },
                    {
                        "method": "POST",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload",
                        "description": (
                            "上传文件、自动分段、创建文档并进入向量化队列。"
                            "可选 split_strategy=llm_text 或 llm_vision；"
                            "llm_text 需传 model_id，llm_vision 需传 vision_model_id 和 llm_model_id。"
                        ),
                        "form_data": [
                            {"name": "file", "type": "file", "required": True},
                            {"name": "limit", "type": "integer", "required": False, "default": 4096},
                            {"name": "patterns", "type": "string[]", "required": False},
                            {"name": "with_filter", "type": "boolean", "required": False},
                            {
                                "name": "split_strategy",
                                "type": "string",
                                "required": False,
                                "enum": ["llm_text", "llm_vision"],
                            },
                            {"name": "model_id", "type": "uuid", "required": False},
                            {"name": "vision_model_id", "type": "uuid", "required": False},
                            {"name": "llm_model_id", "type": "uuid", "required": False},
                        ],
                    },
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/{document_id}/paragraphs",
                        "description": "分页获取文档分段",
                    },
                    {
                        "method": "POST",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/hit-test",
                        "description": "对一个或多个知识库做召回测试",
                    },
                ],
            }
        )


class KnowledgeOpenAPIKnowledgeView(APIView):
    def get(self, request: Request, workspace_id: str):
        identity = authenticate_open_api_key(request)
        check_workspace(identity, workspace_id)
        return result.success(
            KnowledgeSerializer.Query(
                data={
                    "workspace_id": workspace_id,
                    "folder_id": request.query_params.get("folder_id") or workspace_id,
                    "name": request.query_params.get("name"),
                    "desc": request.query_params.get("desc"),
                    "scope": KnowledgeScope.WORKSPACE,
                    "user_id": identity.user.id,
                    "create_user": request.query_params.get("create_user"),
                }
            ).page(_page(request), _page_size(request))
        )


class KnowledgeOpenAPIKnowledgeDetailView(APIView):
    def get(self, request: Request, workspace_id: str, knowledge_id: str):
        identity = authenticate_open_api_key(request)
        check_knowledge_permission(identity, workspace_id, knowledge_id)
        return result.success(
            KnowledgeSerializer.Operate(
                data={"user_id": identity.user.id, "workspace_id": workspace_id, "knowledge_id": knowledge_id}
            ).one()
        )


class KnowledgeOpenAPIDocumentView(APIView):
    def get(self, request: Request, workspace_id: str, knowledge_id: str):
        identity = authenticate_open_api_key(request)
        check_knowledge_permission(identity, workspace_id, knowledge_id)
        return result.success(
            DocumentSerializers.Query(
                data={
                    "workspace_id": workspace_id,
                    "knowledge_id": knowledge_id,
                    "name": request.query_params.get("name"),
                    "tag": request.query_params.get("tag"),
                    "tag_exclude": request.query_params.get("tag_exclude"),
                    "is_active": request.query_params.get("is_active"),
                    "status": request.query_params.get("status"),
                    "task_type": request.query_params.get("task_type"),
                    "order_by": request.query_params.get("order_by"),
                    "create_user": request.query_params.get("create_user"),
                }
            ).page(_page(request), _page_size(request))
        )


class KnowledgeOpenAPIUploadDocumentView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request: Request, workspace_id: str, knowledge_id: str):
        identity = authenticate_open_api_key(request)
        check_knowledge_permission(identity, workspace_id, knowledge_id, manage=True)
        files = request.FILES.getlist("file")
        if not files and request.FILES.get("file") is not None:
            files = [request.FILES.get("file")]
        if not files:
            raise AppApiException(500, _("file is required"))
        split_data = {
            "file": files,
            "limit": int(request.data.get("limit") or 4096),
            "patterns": _get_patterns(request),
            "with_filter": _to_bool(request.data.get("with_filter")),
            "split_strategy": request.data.get("split_strategy") or "",
            "model_id": request.data.get("model_id") or None,
            "vision_model_id": request.data.get("vision_model_id") or None,
            "llm_model_id": request.data.get("llm_model_id") or None,
        }
        document_list = DocumentSerializers.Split(
            data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
        ).parse(split_data)
        saved_document_list = DocumentSerializers.Batch(
            data={"workspace_id": workspace_id, "knowledge_id": knowledge_id, "user_id": identity.user.id}
        ).batch_save(document_list)
        return result.success(
            {
                "documents": saved_document_list,
                "document_count": len(saved_document_list),
            }
        )


class KnowledgeOpenAPIParagraphView(APIView):
    def get(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
        identity = authenticate_open_api_key(request)
        check_knowledge_permission(identity, workspace_id, knowledge_id)
        if not QuerySet(Document).filter(id=document_id, knowledge_id=knowledge_id).exists():
            raise AppUnauthorizedFailed(403, _("No permission to access"))
        return result.success(
            ParagraphSerializers.Query(
                data={
                    **query_params_to_single_dict(request.query_params),
                    "workspace_id": workspace_id,
                    "knowledge_id": knowledge_id,
                    "document_id": document_id,
                }
            ).page(_page(request), _page_size(request))
        )


class KnowledgeOpenAPIHitTestView(APIView):
    def post(self, request: Request, workspace_id: str):
        identity = authenticate_open_api_key(request)
        check_workspace(identity, workspace_id)
        knowledge_id_list = request.data.get("knowledge_id_list") or []
        if request.data.get("knowledge_id"):
            knowledge_id_list = [request.data.get("knowledge_id")]
        if not knowledge_id_list:
            raise AppApiException(500, _("knowledge id list is required"))
        for knowledge_id in knowledge_id_list:
            check_knowledge_permission(identity, workspace_id, str(knowledge_id))
        return result.success(
            KnowledgeSerializer.BatchHitTest(
                data={
                    "workspace_id": workspace_id,
                    "knowledge_id_list": knowledge_id_list,
                    "user_id": identity.user.id,
                    "query_text": request.data.get("query_text"),
                    "top_number": request.data.get("top_number") or 5,
                    "similarity": request.data.get("similarity") or 0.6,
                    "search_mode": request.data.get("search_mode") or "blend",
                }
            ).hit_test()
        )
