# coding=utf-8
import hashlib
import json
import uuid
from pathlib import Path

from django.http import HttpResponse
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.exception.app_exception import AppApiException, AppUnauthorizedFailed
from common.utils.common import query_params_to_single_dict
from knowledge.models import Document, File, FileSourceType, KnowledgeScope
from knowledge.open_api.auth import (
    authenticate_open_api_key,
    check_knowledge_permission,
    check_workspace,
)
from knowledge.open_api.document_import_task import (
    apply_import_task,
    build_request_digest,
    create_import_task_state,
    delete_import_task_state,
    get_import_task_state,
    list_import_task_states,
    update_import_task_state,
)
from knowledge.serializers.document import DocumentSerializers
from knowledge.serializers.knowledge import KnowledgeSerializer
from knowledge.serializers.paragraph import ParagraphSerializers
from knowledge.task.split_preview import (
    cleanup_split_preview_files,
    force_cancel_split_preview_task,
    split_document_preview_task,
)
from maxkb.conf import PROJECT_DIR
from models_provider.serializers.model_serializer import ModelSerializer


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


def _uploaded_file_fingerprint(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return {
        "name": uploaded_file.name,
        "size": uploaded_file.size,
        "sha256": digest.hexdigest(),
    }


KNOWLEDGE_OPEN_API_DOC_PATH = (
    Path(PROJECT_DIR) / "docs" / "openapi" / "knowledge-document-upload.md"
)
OPEN_API_MODEL_TYPES = {"LLM", "IMAGE"}
OPEN_API_MODEL_FIELDS = ("id", "name", "model_name", "model_type", "provider")


def _read_open_api_document():
    return KNOWLEDGE_OPEN_API_DOC_PATH.read_text(encoding="utf-8")


def _open_api_model(model, scope):
    return {
        **{field: model.get(field) for field in OPEN_API_MODEL_FIELDS},
        "scope": scope,
    }


class PublicAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def perform_authentication(self, request):
        return None


class KnowledgeOpenAPIDocsPageView(PublicAPIView):
    def get(self, request: Request):
        html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MaxKB 知识库开放接口</title>
<style>body{margin:0;background:#f5f7fa;color:#1f2329;font:15px/1.7 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}header{position:sticky;top:0;background:#fff;border-bottom:1px solid #e5e6eb;padding:14px 24px;display:flex;justify-content:space-between;align-items:center}main{max-width:1040px;margin:24px auto;background:#fff;padding:36px 48px;border-radius:10px;box-shadow:0 2px 12px #0000000d}a{background:#3370ff;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none}#content{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}@media(max-width:700px){main{margin:0;padding:24px 16px;border-radius:0}header{padding:12px 16px}}</style>
</head><body><header><strong>MaxKB 知识库开放接口</strong><a href="./docs/download">下载 Markdown</a></header>
<main><div id="content">正在加载文档…</div></main><script>fetch('./docs/content').then(r=>r.text()).then(t=>document.getElementById('content').textContent=t).catch(()=>document.getElementById('content').textContent='文档加载失败')</script></body></html>"""
        return HttpResponse(html, content_type="text/html; charset=utf-8")


class KnowledgeOpenAPIDocsContentView(PublicAPIView):
    def get(self, request: Request):
        return HttpResponse(
            _read_open_api_document(), content_type="text/markdown; charset=utf-8"
        )


class KnowledgeOpenAPIDocsDownloadView(KnowledgeOpenAPIDocsContentView):
    def get(self, request: Request):
        response = super().get(request)
        response["Content-Disposition"] = (
            'attachment; filename="maxkb-knowledge-open-api.md"'
        )
        return response


class KnowledgeOpenAPIDocsView(PublicAPIView):
    def get(self, request: Request):
        return result.success(
            {
                "auth": "Authorization: Bearer <api_key>",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/models",
                        "description": "获取当前 API Key 可访问的工作区模型与共享模型。",
                        "query_params": [
                            {
                                "name": "model_type",
                                "type": "string",
                                "required": True,
                                "enum": ["LLM", "IMAGE"],
                            }
                        ],
                    },
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
                            "创建异步上传任务，完成后可预览并确认入库。"
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
                            {"name": "quality_optimize", "type": "boolean", "required": False},
                            {"name": "auto_apply", "type": "boolean", "required": False},
                            {"name": "idempotency_key", "type": "string", "required": False},
                        ],
                    },
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks",
                        "description": "分页获取当前 API Key 创建的导入任务",
                    },
                    {
                        "method": "GET/DELETE",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}",
                        "description": "查询任务进度或删除任务",
                    },
                    {
                        "method": "GET",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/preview",
                        "description": "分页查看分段预览",
                    },
                    {
                        "method": "POST",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/apply",
                        "description": "确认预览并创建正式文档",
                    },
                    {
                        "method": "POST",
                        "path": "/openapi/knowledge/v1/workspaces/{workspace_id}/knowledges/{knowledge_id}/documents/upload-tasks/{task_id}/cancel",
                        "description": "强制终止运行中的任务并清理临时文件",
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


class KnowledgeOpenAPIModelView(APIView):
    def get(self, request: Request, workspace_id: str):
        identity = authenticate_open_api_key(request)
        check_workspace(identity, workspace_id)
        model_type = (request.query_params.get("model_type") or "").upper()
        if model_type not in OPEN_API_MODEL_TYPES:
            raise AppApiException(400, _("model_type must be LLM or IMAGE"))
        payload = ModelSerializer.Query(
            data={"user_id": str(identity.user.id), "model_type": model_type}
        ).model_list(workspace_id=workspace_id, with_valid=True)
        models = [
            *[_open_api_model(model, "workspace") for model in payload.get("model", [])],
            *[_open_api_model(model, "shared") for model in payload.get("shared_model", [])],
        ]
        return result.success(models)


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
        file_ids = request.data.getlist("file_id") if hasattr(request.data, "getlist") else []
        if request.data.get("file_id") and not file_ids:
            file_ids = [request.data.get("file_id")]
        if not files and not file_ids:
            raise AppApiException(400, _("file is required"))
        split_data = {
            "file": files,
            "limit": int(request.data.get("limit") or 4096),
            "patterns": _get_patterns(request),
            "with_filter": _to_bool(request.data.get("with_filter")),
            "split_strategy": request.data.get("split_strategy") or "",
            "model_id": request.data.get("model_id") or None,
            "vision_model_id": request.data.get("vision_model_id") or None,
            "llm_model_id": request.data.get("llm_model_id") or None,
            "quality_optimize": _to_bool(request.data.get("quality_optimize")),
        }
        if files:
            split_serializer = DocumentSerializers.Split(
                data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
            )
            split_serializer.is_valid(instance=split_data, raise_exception=True)
        DocumentSerializers.Split._validate_model_selection(
            split_data.get("split_strategy") or "",
            split_data.get("model_id"),
            split_data.get("vision_model_id"),
            split_data.get("llm_model_id"),
        )
        task_id = str(uuid.uuid7())
        idempotency_key = request.data.get("idempotency_key") or request.headers.get(
            "Idempotency-Key"
        )
        digest = build_request_digest(
            {
                **{key: value for key, value in split_data.items() if key != "file"},
                "files": [_uploaded_file_fingerprint(row) for row in files],
                "file_ids": sorted(str(row) for row in file_ids),
                "auto_apply": _to_bool(request.data.get("auto_apply")),
            }
        )
        state, created = create_import_task_state(
            task_id,
            identity,
            workspace_id,
            knowledge_id,
            digest,
            idempotency_key=idempotency_key,
            auto_apply=_to_bool(request.data.get("auto_apply")),
        )
        if not created:
            return result.success(_task_response(state, request))

        input_file_ids = []
        try:
            for uploaded_file in files:
                input_file = File(
                    file_name=uploaded_file.name,
                    source_type=FileSourceType.TEMPORARY_120_MINUTE.value,
                    source_id=task_id,
                    meta={"split_preview_task_id": task_id},
                )
                input_file.save(uploaded_file.read())
                input_file_ids.append(str(input_file.id))
            if file_ids:
                reusable_files = QuerySet(File).filter(
                    id__in=file_ids,
                    source_type=FileSourceType.KNOWLEDGE.value,
                    source_id=str(knowledge_id),
                )
                if reusable_files.count() != len(set(str(row) for row in file_ids)):
                    raise AppApiException(
                        404, "file_id does not exist in this knowledge base"
                    )
                for source_file in reusable_files:
                    temporary_file = File(
                        file_name=source_file.file_name,
                        source_type=FileSourceType.TEMPORARY_120_MINUTE.value,
                        source_id=task_id,
                        meta={"split_preview_task_id": task_id},
                    )
                    temporary_file.save(source_file.get_bytes())
                    input_file_ids.append(str(temporary_file.id))
            split_config = {
                key: value
                for key, value in split_data.items()
                if key != "file" and value is not None
            }
            async_result = split_document_preview_task.delay(
                task_id,
                str(identity.user.id),
                workspace_id,
                knowledge_id,
                input_file_ids,
                split_config,
            )
            state = update_import_task_state(task_id, celery_task_id=async_result.id)
        except Exception:
            QuerySet(File).filter(id__in=input_file_ids).delete()
            update_import_task_state(
                task_id,
                status="failed",
                stage="failed",
                message="任务提交失败",
                error="任务提交失败，请检查请求参数",
            )
            raise
        return result.success(_task_response(state, request))


def _task_response(state, request=None):
    status_map = {
        "queued": "QUEUED",
        "processing": "PROCESSING",
        "completed": "PREVIEW_READY",
        "applying": "APPLYING",
        "import_completed": "COMPLETED",
        "failed": "FAILED",
        "cancelled": "CANCELLED",
    }
    task_id = state.get("task_id")
    response = {
        "task_id": task_id,
        "status": status_map.get(
            state.get("status"), str(state.get("status", "")).upper()
        ),
        "stage": state.get("stage"),
        "progress": state.get("progress", 0),
        "metrics": {
            "processed": state.get("processed", 0),
            "total": state.get("total", 0),
            "remaining": state.get("remaining", 0),
        },
        "message": state.get("message"),
        "error": (
            {"code": "IMPORT_FAILED", "message": state.get("error")}
            if state.get("error")
            else None
        ),
        "documents": state.get("documents") or [],
    }
    if request is not None:
        base = request.build_absolute_uri(request.path).rstrip("/")
        if not base.endswith(str(task_id)):
            base = (
                f"{base.rsplit('/documents/', 1)[0]}/documents/upload-tasks/{task_id}"
            )
        response.update(
            {
                "status_url": base,
                "preview_url": f"{base}/preview",
                "apply_url": f"{base}/apply",
            }
        )
    return response


def _get_owned_import_task(
    request, workspace_id, knowledge_id, task_id, manage=False
):
    identity = authenticate_open_api_key(request)
    check_knowledge_permission(identity, workspace_id, knowledge_id, manage=manage)
    state = get_import_task_state(
        task_id, identity.key.get("id"), workspace_id, knowledge_id
    )
    if state is None:
        raise AppApiException(404, "Import task expired or does not exist")
    return identity, state


class KnowledgeOpenAPIUploadTaskListView(APIView):
    def get(self, request: Request, workspace_id: str, knowledge_id: str):
        identity = authenticate_open_api_key(request)
        check_knowledge_permission(identity, workspace_id, knowledge_id)
        states = list_import_task_states(
            identity.key.get("id"), workspace_id, knowledge_id
        )
        page, size = _page(request), _page_size(request)
        start = (page - 1) * size
        return result.success(
            {
                "total": len(states),
                "records": [
                    _task_response(row, request)
                    for row in states[start : start + size]
                ],
            }
        )


class KnowledgeOpenAPIUploadTaskView(APIView):
    def get(self, request: Request, workspace_id: str, knowledge_id: str, task_id: str):
        _, state = _get_owned_import_task(
            request, workspace_id, knowledge_id, task_id
        )
        return result.success(_task_response(state, request))

    def delete(self, request: Request, workspace_id: str, knowledge_id: str, task_id: str):
        _, state = _get_owned_import_task(
            request, workspace_id, knowledge_id, task_id, manage=True
        )
        if state.get("status") == "applying":
            raise AppApiException(409, "The task is being applied and cannot be deleted")
        if state.get("status") not in {
            "completed",
            "import_completed",
            "failed",
            "cancelled",
        }:
            force_cancel_split_preview_task(task_id)
        if state.get("status") != "import_completed":
            cleanup_split_preview_files(task_id)
        delete_import_task_state(task_id)
        return result.success({"task_id": task_id, "deleted": True})


class KnowledgeOpenAPIUploadTaskPreviewView(APIView):
    def get(self, request: Request, workspace_id: str, knowledge_id: str, task_id: str):
        _, state = _get_owned_import_task(
            request, workspace_id, knowledge_id, task_id
        )
        if state.get("status") not in {"completed", "applying"} or state.get(
            "result"
        ) is None:
            raise AppApiException(409, "The preview is not ready")
        records = state.get("result") or []
        page, size = _page(request), _page_size(request)
        start = (page - 1) * size
        return result.success(
            {"total": len(records), "records": records[start : start + size]}
        )


class KnowledgeOpenAPIUploadTaskApplyView(APIView):
    def post(self, request: Request, workspace_id: str, knowledge_id: str, task_id: str):
        _get_owned_import_task(
            request, workspace_id, knowledge_id, task_id, manage=True
        )
        return result.success(_task_response(apply_import_task(task_id), request))


class KnowledgeOpenAPIUploadTaskCancelView(APIView):
    def post(self, request: Request, workspace_id: str, knowledge_id: str, task_id: str):
        _, state = _get_owned_import_task(
            request, workspace_id, knowledge_id, task_id, manage=True
        )
        if state.get("status") == "applying":
            raise AppApiException(409, "The task is being applied and cannot be cancelled")
        if state.get("status") in {
            "completed",
            "import_completed",
            "failed",
            "cancelled",
        }:
            raise AppApiException(409, "The import task is already finished")
        return result.success(
            _task_response(force_cancel_split_preview_task(task_id), request)
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
