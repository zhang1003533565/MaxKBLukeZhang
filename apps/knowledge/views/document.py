import uuid_utils.compat as uuid

from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import CompareConstants, PermissionConstants, RoleConstants, ViewPermission
from common.event.listener_manage import ListenerManagement
from common.exception.app_exception import AppApiException
from common.log.log import log
from common.result import result
from django.utils.translation import gettext_lazy as _
from django.db import connection, transaction
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from knowledge.api.document import (
    BatchCancelTaskAPI,
    BatchEditHitHandlingAPI,
    BatchGenerateRelatedAPI,
    BatchRefreshAPI,
    CancelTaskAPI,
    DocumentBatchAPI,
    DocumentBatchCreateAPI,
    DocumentCreateAPI,
    DocumentDeleteAPI,
    DocumentDownloadSourceAPI,
    DocumentEditAPI,
    DocumentExportAPI,
    DocumentMigrateAPI,
    DocumentReadAPI,
    DocumentSplitAPI,
    DocumentSplitPatternAPI,
    DocumentTagsAPI,
    DocumentTreeReadAPI,
    QaDocumentCreateAPI,
    RefreshAPI,
    TableDocumentCreateAPI,
    TemplateExportAPI,
)
from knowledge.api.tag import DocsTagDeleteAPI
from knowledge.serializers.common import get_knowledge_operation_object
from knowledge.serializers.document import DocumentSerializers
from knowledge.models import (
    Document,
    Embedding,
    File,
    FileSourceType,
    Paragraph,
    ProblemParagraphMapping,
    State,
    TaskType,
)
from knowledge.serializers.common import get_embedding_model_id_by_knowledge_id
from knowledge.task.document_quality import optimize_document_quality_task
from knowledge.task.embedding import embedding_by_document
from knowledge.task.split_preview import (
    create_split_task_state,
    delete_split_task_state,
    force_cancel_split_preview_task,
    get_split_task_state,
    split_document_preview_task,
    update_split_task_state,
)
from knowledge.views.common import (
    get_document_operation_object,
    get_document_operation_object_batch,
    get_knowledge_document_operation_object,
)


def build_document_split_data(request):
    split_data = {"file": request.FILES.getlist("file")}
    request_data = request.data
    if (
        "patterns" in request.data
        and request.data.get("patterns") is not None
        and len(request.data.get("patterns")) > 0
    ):
        split_data["patterns"] = request_data.getlist("patterns")
    for field in [
        "limit",
        "with_filter",
        "split_strategy",
        "qa_parse_mode",
        "model_id",
        "vision_model_id",
        "llm_model_id",
        "quality_optimize",
    ]:
        if field in request.data:
            split_data[field] = request_data.get(field)
    return split_data


class DocumentView(APIView):
    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=["POST"],
        description=_("Create document"),
        summary=_("Create document"),
        operation_id=_("Create document"),  # type: ignore
        request=DocumentCreateAPI.get_request(),
        parameters=DocumentCreateAPI.get_parameters(),
        responses=DocumentCreateAPI.get_response(),
        tags=[_("Knowledge Base/Documentation")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_knowledge_permission(),
        PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_permission_workspace_manage_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
        ViewPermission(
            [RoleConstants.USER.get_workspace_role()],
            [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
            CompareConstants.AND,
        ),
    )
    @log(
        menu="document",
        operate="Create document",
        get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
            get_knowledge_operation_object(keywords.get("knowledge_id")), {"name": r.data.get("name")}
        ),
    )
    def post(self, request: Request, workspace_id: str, knowledge_id: str):
        return result.success(
            DocumentSerializers.Create(
                data={"workspace_id": workspace_id, "knowledge_id": knowledge_id, "user_id": request.user.id},
            ).save(request.data)
        )

    @extend_schema(
        methods=["GET"],
        description=_("Get document"),
        summary=_("Get document"),
        operation_id=_("Get document"),  # type: ignore
        parameters=DocumentTreeReadAPI.get_parameters(),
        responses=DocumentTreeReadAPI.get_response(),
        tags=[_("Knowledge Base/Documentation")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
        PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
        ViewPermission(
            [RoleConstants.USER.get_workspace_role()],
            [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
            CompareConstants.AND,
        ),
    )
    def get(self, request: Request, workspace_id: str, knowledge_id: str):
        raw_tags = request.query_params.getlist("tags[]")
        return result.success(
            DocumentSerializers.Query(
                data={
                    "workspace_id": workspace_id,
                    "knowledge_id": knowledge_id,
                    "folder_id": request.query_params.get("folder_id"),
                    "name": request.query_params.get("name"),
                    "tag": request.query_params.get("tag"),
                    "tag_exclude": request.query_params.get("tag_exclude"),
                    "tag_ids": [tag for tag in raw_tags if tag != "NO_TAG"],
                    "no_tag": "NO_TAG" in raw_tags,
                    "desc": request.query_params.get("desc"),
                    "user_id": request.query_params.get("user_id"),
                }
            ).list()
        )

    class Operate(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            description=_("Get document details"),
            summary=_("Get document details"),
            operation_id=_("Get document details"),  # type: ignore
            parameters=DocumentReadAPI.get_parameters(),
            responses=DocumentReadAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            operate = DocumentSerializers.Operate(
                data={"document_id": document_id, "knowledge_id": knowledge_id, "workspace_id": workspace_id}
            )
            operate.is_valid(raise_exception=True)
            return result.success(operate.one())

        @extend_schema(
            description=_("Modify document"),
            summary=_("Modify document"),
            operation_id=_("Modify document"),  # type: ignore
            parameters=DocumentEditAPI.get_parameters(),
            request=DocumentEditAPI.get_request(),
            responses=DocumentEditAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Modify document",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.Operate(
                    data={"document_id": document_id, "knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).edit(request.data, with_valid=True)
            )

        @extend_schema(
            description=_("Delete document"),
            summary=_("Delete document"),
            operation_id=_("Delete document"),  # type: ignore
            parameters=DocumentDeleteAPI.get_parameters(),
            responses=DocumentDeleteAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_DELETE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_DELETE.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Delete document",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def delete(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            operate = DocumentSerializers.Operate(
                data={"document_id": document_id, "knowledge_id": knowledge_id, "workspace_id": workspace_id}
            )
            operate.is_valid(raise_exception=True)
            return result.success(operate.delete())

    class Split(APIView):
        authentication_classes = [TokenAuth]
        parser_classes = [MultiPartParser]

        @extend_schema(
            methods=["POST"],
            description=_("Segmented document"),
            summary=_("Segmented document"),
            operation_id=_("Segmented document"),  # type: ignore
            parameters=DocumentSplitAPI.get_parameters(),
            request=DocumentSplitAPI.get_request(),
            responses=DocumentSplitAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Split(
                    data={
                        "workspace_id": workspace_id,
                        "knowledge_id": knowledge_id,
                    }
                ).parse(build_document_split_data(request))
            )

    class SplitTask(APIView):
        authentication_classes = [TokenAuth]
        parser_classes = [MultiPartParser]

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str):
            split_data = build_document_split_data(request)
            split_serializer = DocumentSerializers.Split(
                data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
            )
            split_serializer.is_valid(instance=split_data, raise_exception=True)
            DocumentSerializers.Split._validate_model_selection(
                split_data.get("split_strategy") or "",
                split_data.get("model_id"),
                split_data.get("vision_model_id"),
                split_data.get("llm_model_id"),
                split_data.get("quality_optimize"),
                split_data.get("qa_parse_mode"),
            )
            task_id = str(uuid.uuid7())
            input_file_ids = []
            try:
                for uploaded_file in split_data["file"]:
                    input_file = File(
                        file_name=uploaded_file.name,
                        source_type=FileSourceType.TEMPORARY_120_MINUTE.value,
                        source_id=task_id,
                        meta={"split_preview_task_id": task_id},
                    )
                    input_file.save(uploaded_file.read())
                    input_file_ids.append(str(input_file.id))
                create_split_task_state(
                    task_id, request.user.id, workspace_id, knowledge_id
                )
                split_config = {
                    key: value
                    for key, value in split_data.items()
                    if key != "file" and value is not None
                }
                async_result = split_document_preview_task.delay(
                    task_id,
                    str(request.user.id),
                    workspace_id,
                    knowledge_id,
                    input_file_ids,
                    split_config,
                )
                update_split_task_state(task_id, celery_task_id=async_result.id)
            except Exception as e:
                if input_file_ids:
                    File.objects.filter(id__in=input_file_ids).delete()
                update_split_task_state(
                    task_id,
                    status="failed",
                    stage="failed",
                    message="任务提交失败",
                    error=str(e),
                )
                raise
            return result.success({"task_id": task_id, "status": "queued"})

    class SplitTaskStatus(APIView):
        authentication_classes = [TokenAuth]

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def get(
            self,
            request: Request,
            workspace_id: str,
            knowledge_id: str,
            task_id: str,
        ):
            state = get_split_task_state(task_id)
            if state is None or (
                state.get("user_id") != str(request.user.id)
                or state.get("workspace_id") != str(workspace_id)
                or state.get("knowledge_id") != str(knowledge_id)
            ):
                raise AppApiException(404, _("Split preview task expired or does not exist"))
            return result.success(state)

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def delete(
            self,
            request: Request,
            workspace_id: str,
            knowledge_id: str,
            task_id: str,
        ):
            state = get_split_task_state(task_id)
            if state is None or (
                state.get("user_id") != str(request.user.id)
                or state.get("workspace_id") != str(workspace_id)
                or state.get("knowledge_id") != str(knowledge_id)
            ):
                raise AppApiException(404, _("Split preview task expired or does not exist"))
            if state.get("status") in {"completed", "failed", "cancelled"}:
                raise AppApiException(409, _("Split preview task is already finished"))
            try:
                cancelled_state = force_cancel_split_preview_task(task_id)
            except ValueError as e:
                raise AppApiException(409, str(e)) from e
            return result.success(
                {"task_id": task_id, "status": cancelled_state.get("status")}
            )

    class SplitPattern(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Get a list of segment IDs"),
            description=_("Get a list of segment IDs"),
            operation_id=_("Get a list of segment IDs"),  # type: ignore
            parameters=DocumentSplitPatternAPI.get_parameters(),
            responses=DocumentSplitPatternAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.SplitPattern(
                    data={"knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).list()
            )

    class QualityTask(APIView):
        authentication_classes = [TokenAuth]

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def post(
            self, request: Request, workspace_id: str, knowledge_id: str, document_id: str
        ):
            if not QuerySet(Document).filter(
                id=document_id, knowledge_id=knowledge_id
            ).exists():
                raise AppApiException(404, _("Document does not exist"))
            model_id = request.data.get("model_id")
            if not model_id:
                raise AppApiException(500, _("Model is not allowed to be empty"))
            task_id = str(uuid.uuid7())
            create_split_task_state(
                task_id, request.user.id, workspace_id, knowledge_id
            )
            update_split_task_state(task_id, document_id=str(document_id))
            try:
                async_result = optimize_document_quality_task.delay(
                    task_id,
                    str(request.user.id),
                    workspace_id,
                    knowledge_id,
                    document_id,
                    model_id,
                )
            except Exception:
                update_split_task_state(
                    task_id,
                    status="failed",
                    stage="failed",
                    message="质量优化任务启动失败",
                    error="质量优化任务启动失败，请稍后重试",
                )
                raise
            update_split_task_state(task_id, celery_task_id=async_result.id)
            return result.success({"task_id": task_id, "status": "queued"})

    class QualityTaskStatus(APIView):
        authentication_classes = [TokenAuth]

        @staticmethod
        def _state(request, workspace_id, knowledge_id, document_id, task_id):
            state = get_split_task_state(task_id)
            if state is None or (
                state.get("user_id") != str(request.user.id)
                or state.get("workspace_id") != str(workspace_id)
                or state.get("knowledge_id") != str(knowledge_id)
                or state.get("document_id") != str(document_id)
            ):
                raise AppApiException(404, _("Quality optimization task does not exist"))
            return state

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def get(self, request, workspace_id, knowledge_id, document_id, task_id):
            return result.success(
                self._state(request, workspace_id, knowledge_id, document_id, task_id)
            )

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def delete(self, request, workspace_id, knowledge_id, document_id, task_id):
            state = self._state(
                request, workspace_id, knowledge_id, document_id, task_id
            )
            if state.get("status") in {"completed", "failed", "cancelled", "applied"}:
                raise AppApiException(409, _("Quality optimization task is already finished"))
            cancelled = force_cancel_split_preview_task(task_id)
            return result.success(
                {"task_id": task_id, "status": cancelled.get("status")}
            )

    class QualityTaskApply(APIView):
        authentication_classes = [TokenAuth]

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @transaction.atomic
        def post(self, request, workspace_id, knowledge_id, document_id, task_id):
            state = DocumentView.QualityTaskStatus._state(
                request, workspace_id, knowledge_id, document_id, task_id
            )
            if state.get("status") != "completed" or not state.get("result"):
                raise AppApiException(409, _("Quality optimization draft is not ready"))
            document = (
                QuerySet(Document)
                .select_for_update()
                .filter(id=document_id, knowledge_id=knowledge_id)
                .first()
            )
            if document is None:
                raise AppApiException(404, _("Document does not exist"))
            with connection.cursor() as cursor:
                cursor.execute(
                    f"LOCK TABLE {Paragraph._meta.db_table} IN SHARE ROW EXCLUSIVE MODE"
                )
            current = list(
                QuerySet(Paragraph)
                .select_for_update()
                .filter(document_id=document_id, knowledge_id=knowledge_id)
                .order_by("position")
                .values("id", "update_time")
            )
            current_snapshot = [
                {"id": str(item["id"]), "update_time": str(item["update_time"])}
                for item in current
            ]
            if current_snapshot != state["result"].get("snapshot"):
                raise AppApiException(409, _("Document paragraphs changed, regenerate the draft"))

            old_mappings = list(
                QuerySet(ProblemParagraphMapping)
                .filter(document_id=document_id)
                .values("problem_id", "paragraph_id")
            )
            QuerySet(ProblemParagraphMapping).filter(document_id=document_id).delete()
            QuerySet(Embedding).filter(document_id=document_id).delete()
            QuerySet(Paragraph).filter(document_id=document_id).delete()
            paragraphs = [
                Paragraph(
                    id=uuid.uuid7(),
                    document_id=document_id,
                    knowledge_id=knowledge_id,
                    title=item.get("title") or "",
                    content=item.get("content") or "",
                    position=index,
                    is_active=item.get("is_active", True),
                )
                for index, item in enumerate(state["result"]["after"], start=1)
            ]
            Paragraph.objects.bulk_create(paragraphs)
            source_to_new_paragraph = {}
            for paragraph, item in zip(paragraphs, state["result"]["after"]):
                for source_id in item.get("source_paragraph_ids") or []:
                    source_to_new_paragraph.setdefault(str(source_id), []).append(
                        paragraph.id
                    )
            restored_mappings = [
                ProblemParagraphMapping(
                    id=uuid.uuid7(),
                    knowledge_id=knowledge_id,
                    document_id=document_id,
                    problem_id=mapping["problem_id"],
                    paragraph_id=paragraph_id,
                )
                for mapping in old_mappings
                if str(mapping["paragraph_id"]) in source_to_new_paragraph
                for paragraph_id in source_to_new_paragraph[
                    str(mapping["paragraph_id"])
                ]
            ]
            if restored_mappings:
                ProblemParagraphMapping.objects.bulk_create(restored_mappings)
            document.char_length = sum(len(paragraph.content) for paragraph in paragraphs)
            document.save(update_fields=["char_length", "update_time"])
            ListenerManagement.update_status(
                QuerySet(Document).filter(id=document_id),
                TaskType.EMBEDDING,
                State.PENDING,
            )
            ListenerManagement.update_status(
                QuerySet(Paragraph).filter(document_id=document_id).values("id"),
                TaskType.EMBEDDING,
                State.PENDING,
            )
            ListenerManagement.get_aggregation_document_status(document_id)()
            embedding_model_id = get_embedding_model_id_by_knowledge_id(knowledge_id)
            embedding_by_document.run(
                document_id, embedding_model_id, raise_on_error=True
            )
            transaction.on_commit(
                lambda: delete_split_task_state(task_id)
            )
            return result.success({"paragraph_count": len(paragraphs)})

    class BatchEditHitHandling(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            summary=_("Modify document hit processing methods in batches"),
            description=_("Modify document hit processing methods in batches"),
            operation_id=_("Modify document hit processing methods in batches"),  # type: ignore
            request=BatchEditHitHandlingAPI.get_request(),
            parameters=BatchEditHitHandlingAPI.get_parameters(),
            responses=BatchEditHitHandlingAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Modify document hit processing methods in batches",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("id_list")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).batch_edit_hit_handling(request.data)
            )

    class Refresh(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            summary=_("Refresh document vector library"),
            description=_("Refresh document vector library"),
            operation_id=_("Refresh document vector library"),  # type: ignore
            parameters=RefreshAPI.get_parameters(),
            request=RefreshAPI.get_request(),
            responses=RefreshAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Refresh document vector library",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.Operate(
                    data={"document_id": document_id, "knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).refresh(request.data.get("state_list"))
            )

    class Tokenize(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            summary=_("Tokenize document vector library"),
            description=_("Tokenize document vector library"),
            operation_id=_("Tokenize document vector library"),  # type: ignore
            parameters=RefreshAPI.get_parameters(),
            request=RefreshAPI.get_request(),
            responses=RefreshAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Refresh document vector library",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.Operate(
                    data={"document_id": document_id, "knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).tokenize(request.data.get("state_list"))
            )

    class CancelTask(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Cancel task"),
            description=_("Cancel task"),
            operation_id=_("Cancel task"),  # type: ignore
            parameters=CancelTaskAPI.get_parameters(),
            request=CancelTaskAPI.get_request(),
            responses=CancelTaskAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Cancel task",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.Operate(
                    data={"document_id": document_id, "knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).cancel(request.data)
            )

    class BatchCancelTask(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Cancel tasks in batches"),
            description=_("Cancel tasks in batches"),
            operation_id=_("Cancel tasks in batches"),  # type: ignore
            parameters=BatchCancelTaskAPI.get_parameters(),
            request=BatchCancelTaskAPI.get_request(),
            responses=BatchCancelTaskAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Cancel tasks in batches",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("id_list")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"knowledge_id": knowledge_id, "workspace_id": workspace_id}
                ).batch_cancel(request.data)
            )

    class BatchCreate(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            description=_("Create documents in batches"),
            summary=_("Create documents in batches"),
            operation_id=_("Create documents in batches"),  # type: ignore
            request=DocumentBatchCreateAPI.get_request(),
            parameters=DocumentBatchCreateAPI.get_parameters(),
            responses=DocumentBatchCreateAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_permission_workspace_manage_role(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Create documents in batches",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                {"name": f"[{','.join([document.get('name') for document in r.data])}]", "document_list": r.data},
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"knowledge_id": knowledge_id, "workspace_id": workspace_id, "user_id": request.user.id}
                ).batch_save(request.data)
            )

    class BatchDelete(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            description=_("Delete documents in batches"),
            summary=_("Delete documents in batches"),
            operation_id=_("Delete documents in batches"),  # type: ignore
            request=DocumentBatchAPI.get_request(),
            parameters=DocumentBatchAPI.get_parameters(),
            responses=DocumentBatchAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_DELETE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_DELETE.get_workspace_permission_workspace_manage_role(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Delete documents in batches",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("id_list")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
                ).batch_delete(request.data)
            )

    class BatchRefresh(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            summary=_("Batch refresh document vector library"),
            operation_id=_("Batch refresh document vector library"),  # type: ignore
            request=BatchRefreshAPI.get_request(),
            parameters=BatchRefreshAPI.get_parameters(),
            responses=BatchRefreshAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_permission_workspace_manage_role(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Batch refresh document vector library",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("id_list")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
                ).batch_refresh(request.data)
            )

    class BatchTokenize(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            summary=_("Batch tokenize document library"),
            operation_id=_("Batch tokenize document library"),  # type: ignore
            request=BatchRefreshAPI.get_request(),
            parameters=BatchRefreshAPI.get_parameters(),
            responses=BatchRefreshAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_VECTOR.get_workspace_permission_workspace_manage_role(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Batch refresh document vector library",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("id_list")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
                ).batch_tokenize(request.data)
            )

    class BatchAddTag(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["POST"],
            summary=_("Batch add tags to documents"),
            operation_id=_("Batch add tags to documents"),  # type: ignore
            request=DocumentTagsAPI.get_request(),
            parameters=DocumentTagsAPI.get_parameters(),
            responses=DocumentTagsAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Batch add tags to documents",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("document_ids")),
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.Batch(
                    data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
                ).batch_add_tag(request.data)
            )

    class BatchGenerateRelated(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["PUT"],
            summary=_("Batch generate related problems"),
            description=_("Batch generate related problems"),
            operation_id=_("Batch generate related problems"),  # type: ignore
            request=BatchGenerateRelatedAPI.get_request(),
            parameters=BatchGenerateRelatedAPI.get_parameters(),
            responses=BatchGenerateRelatedAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_GENERATE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_GENERATE.get_workspace_permission_workspace_manage_role(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EDIT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Batch generate related problems",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data.get("document_id_list")),
            ),
        )
        def put(self, request: Request, workspace_id: str, knowledge_id: str):
            return result.success(
                DocumentSerializers.BatchGenerateRelated(
                    data={"workspace_id": workspace_id, "knowledge_id": knowledge_id}
                ).batch_generate_related(request.data)
            )

    class BatchExport(APIView):
        authentication_classes = [TokenAuth]

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Export multiple document",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str):
            return DocumentSerializers.Batch(
                data={"workspace_id": workspace_id, "knowledge_id": knowledge_id, "user_id": request.user.id}
            ).batch_export({"id_list": request.data})

    class BatchExportZip(APIView):
        authentication_classes = [TokenAuth]

        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Export multiple document",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str):
            return DocumentSerializers.Batch(
                data={"workspace_id": workspace_id, "knowledge_id": knowledge_id, "user_id": request.user.id}
            ).batch_export_zip({"id_list": request.data})

    class Page(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            methods=["GET"],
            description=_("Get document by pagination"),
            summary=_("Get document by pagination"),
            operation_id=_("Get document by pagination"),  # type: ignore
            parameters=DocumentTreeReadAPI.get_parameters(),
            responses=DocumentTreeReadAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_READ.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str, current_page: int, page_size: int):
            raw_tags = request.query_params.getlist("tags[]")

            return result.success(
                DocumentSerializers.Query(
                    data={
                        "workspace_id": workspace_id,
                        "knowledge_id": knowledge_id,
                        "folder_id": request.query_params.get("folder_id"),
                        "name": request.query_params.get("name"),
                        "tag": request.query_params.get("tag"),
                        "tag_exclude": request.query_params.get("tag_exclude"),
                        "tag_ids": [tag for tag in raw_tags if tag != "NO_TAG"],
                        "no_tag": "NO_TAG" in raw_tags,
                        "desc": request.query_params.get("desc"),
                        "user_id": request.query_params.get("user_id"),
                        "status": request.query_params.get("status"),
                        "is_active": request.query_params.get("is_active"),
                        "hit_handling_method": request.query_params.get("hit_handling_method"),
                        "order_by": request.query_params.get("order_by"),
                        "create_user": request.query_params.get("create_user"),
                    }
                ).page(current_page, page_size)
            )

    class Export(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Export document"),
            operation_id=_("Export document"),  # type: ignore
            parameters=DocumentExportAPI.get_parameters(),
            responses=DocumentExportAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Export document",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return DocumentSerializers.Operate(
                data={"workspace_id": workspace_id, "document_id": document_id, "knowledge_id": knowledge_id}
            ).export()

    class ExportZip(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Export Zip document"),
            operation_id=_("Export Zip document"),  # type: ignore
            parameters=DocumentExportAPI.get_parameters(),
            responses=DocumentExportAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_EXPORT.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Export Zip document",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object(keywords.get("document_id")),
            ),
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return DocumentSerializers.Operate(
                data={"workspace_id": workspace_id, "document_id": document_id, "knowledge_id": knowledge_id}
            ).export_zip()

    class DownloadSourceFile(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Download source file"),
            operation_id=_("Download source file"),  # type: ignore
            parameters=DocumentDownloadSourceAPI.get_parameters(),
            responses=DocumentDownloadSourceAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_DOWNLOAD_SOURCE_FILE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_DOWNLOAD_SOURCE_FILE.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return DocumentSerializers.Operate(
                data={"workspace_id": workspace_id, "document_id": document_id, "knowledge_id": knowledge_id}
            ).download_source_file()

    class ReplaceSourceFile(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Replace source file"),
            operation_id=_("Replace source file"),  # type: ignore
            parameters=DocumentDownloadSourceAPI.get_parameters(),
            responses=DocumentDownloadSourceAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_REPLACE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_REPLACE.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.ReplaceSourceFile(
                    data={
                        "workspace_id": workspace_id,
                        "document_id": document_id,
                        "knowledge_id": knowledge_id,
                        "file": request.FILES.get("file"),
                    }
                ).replace()
            )

    class Tags(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Get document tags"),
            description=_("Get document tags"),
            operation_id=_("Get document tags"),  # type: ignore
            parameters=DocumentTagsAPI.get_parameters(),
            responses=DocumentTagsAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def get(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.Tags(
                    data={
                        "workspace_id": workspace_id,
                        "knowledge_id": knowledge_id,
                        "document_id": document_id,
                        "name": request.query_params.get("name"),
                    }
                ).list()
            )

        @extend_schema(
            summary=_("Add document tags"),
            description=_("Add document tags"),
            operation_id=_("Add document tags"),  # type: ignore
            parameters=DocumentTagsAPI.get_parameters(),
            responses=DocumentTagsAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        def post(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
            return result.success(
                DocumentSerializers.AddTags(
                    data={
                        "workspace_id": workspace_id,
                        "knowledge_id": knowledge_id,
                        "document_id": document_id,
                        "tag_ids": request.data,
                    }
                ).add_tags()
            )

        class BatchDelete(APIView):
            authentication_classes = [TokenAuth]

            @extend_schema(
                summary=_("Delete document tags"),
                description=_("Delete document tags"),
                operation_id=_("Delete document tags"),  # type: ignore
                parameters=DocumentTagsAPI.get_parameters(),
                request=DocumentTagsAPI.get_request(),
                responses=DocumentTagsAPI.get_response(),
                tags=[_("Knowledge Base/Documentation")],  # type: ignore
            )
            @has_permissions(
                PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_knowledge_permission(),
                PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_permission_workspace_manage_role(),
                RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
                ViewPermission(
                    [RoleConstants.USER.get_workspace_role()],
                    [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                    CompareConstants.AND,
                ),
            )
            @log(
                menu="document",
                operate="Delete document tags",
                get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                    get_knowledge_operation_object(keywords.get("knowledge_id")),
                    get_document_operation_object(keywords.get("document_id")),
                ),
            )
            def put(self, request: Request, workspace_id: str, knowledge_id: str, document_id: str):
                return result.success(
                    DocumentSerializers.DeleteTags(
                        data={
                            "workspace_id": workspace_id,
                            "knowledge_id": knowledge_id,
                            "document_id": document_id,
                            "tag_ids": request.data,
                        }
                    ).delete_tags()
                )

        class BatchDeleteDocsTag(APIView):
            authentication_classes = [TokenAuth]

            @extend_schema(
                summary=_("Batch Delete Documents Tag"),
                description=_("Batch Delete Documents Tag"),
                parameters=DocsTagDeleteAPI.get_parameters(),
                request=DocsTagDeleteAPI.get_request(),
                responses=DocsTagDeleteAPI.get_response(),
                tags=[_("Knowledge Base/Tag")],  # type: ignore
            )
            @has_permissions(
                PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_knowledge_permission(),
                PermissionConstants.KNOWLEDGE_DOCUMENT_TAG.get_workspace_permission_workspace_manage_role(),
                RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
                ViewPermission(
                    [RoleConstants.USER.get_workspace_role()],
                    [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                    CompareConstants.AND,
                ),
            )
            @log(
                menu="tag",
                operate="Batch Delete Documents Tag",
                get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                    get_knowledge_operation_object(keywords.get("knowledge_id")),
                    get_document_operation_object_batch(r.data.get("id_list")),
                ),
            )
            def put(self, request: Request, workspace_id: str, knowledge_id: str, tag_id: str):
                return result.success(
                    DocumentSerializers.DeleteDocsTag(
                        data={
                            "workspace_id": workspace_id,
                            "knowledge_id": knowledge_id,
                            "tag_id": tag_id,
                        }
                    ).batch_delete_docs_tag(request.data)
                )

    class Migrate(APIView):
        authentication_classes = [TokenAuth]

        @extend_schema(
            summary=_("Migrate documents in batches"),
            operation_id=_("Migrate documents in batches"),  # type: ignore
            parameters=DocumentMigrateAPI.get_parameters(),
            request=DocumentMigrateAPI.get_request(),
            responses=DocumentMigrateAPI.get_response(),
            tags=[_("Knowledge Base/Documentation")],  # type: ignore
        )
        @has_permissions(
            PermissionConstants.KNOWLEDGE_DOCUMENT_MIGRATE.get_workspace_knowledge_permission(),
            PermissionConstants.KNOWLEDGE_DOCUMENT_MIGRATE.get_workspace_permission_workspace_manage_role(),
            RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
            ViewPermission(
                [RoleConstants.USER.get_workspace_role()],
                [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
                CompareConstants.AND,
            ),
        )
        @log(
            menu="document",
            operate="Migrate documents in batches",
            get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
                get_knowledge_operation_object(keywords.get("knowledge_id")),
                get_document_operation_object_batch(r.data),
            ),
        )
        def put(self, request: Request, workspace_id, knowledge_id: str, target_knowledge_id: str):
            return result.success(
                DocumentSerializers.Migrate(
                    data={
                        "workspace_id": workspace_id,
                        "knowledge_id": knowledge_id,
                        "target_knowledge_id": target_knowledge_id,
                        "document_id_list": request.data,
                    }
                ).migrate()
            )


class QaDocumentView(APIView):
    authentication_classes = [TokenAuth]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary=_("Import QA and create documentation"),
        description=_("Import QA and create documentation"),
        operation_id=_("Import QA and create documentation"),  # type: ignore
        request=QaDocumentCreateAPI.get_request(),
        parameters=QaDocumentCreateAPI.get_parameters(),
        responses=QaDocumentCreateAPI.get_response(),
        tags=[_("Knowledge Base/Documentation")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_knowledge_permission(),
        PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_permission_workspace_manage_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
        ViewPermission(
            [RoleConstants.USER.get_workspace_role()],
            [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
            CompareConstants.AND,
        ),
    )
    @log(
        menu="document",
        operate="Import QA and create documentation",
        get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
            get_knowledge_operation_object(keywords.get("knowledge_id")),
            {
                "name": f"[{','.join([file.name for file in r.FILES.getlist('file')])}]",
                "document_list": [{"name": file.name} for file in r.FILES.getlist("file")],
            },
        ),
    )
    def post(self, request: Request, workspace_id: str, knowledge_id: str):
        return result.success(
            DocumentSerializers.Create(
                data={"knowledge_id": knowledge_id, "workspace_id": workspace_id, "user_id": request.user.id}
            ).save_qa({"file_list": request.FILES.getlist("file")}, with_valid=True)
        )


class TableDocumentView(APIView):
    authentication_classes = [TokenAuth]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary=_("Import tables and create documents"),
        description=_("Import tables and create documents"),
        operation_id=_("Import tables and create documents"),  # type: ignore
        request=TableDocumentCreateAPI.get_request(),
        parameters=TableDocumentCreateAPI.get_parameters(),
        responses=TableDocumentCreateAPI.get_response(),
        tags=[_("Knowledge Base/Documentation")],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_knowledge_permission(),
        PermissionConstants.KNOWLEDGE_DOCUMENT_CREATE.get_workspace_permission_workspace_manage_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
        ViewPermission(
            [RoleConstants.USER.get_workspace_role()],
            [PermissionConstants.KNOWLEDGE.get_workspace_knowledge_permission()],
            CompareConstants.AND,
        ),
    )
    @log(
        menu="document",
        operate="Import tables and create documents",
        get_operation_object=lambda r, keywords: get_knowledge_document_operation_object(
            get_knowledge_operation_object(keywords.get("knowledge_id")),
            {
                "name": f"[{','.join([file.name for file in r.FILES.getlist('file')])}]",
                "document_list": [{"name": file.name} for file in r.FILES.getlist("file")],
            },
        ),
    )
    def post(self, request: Request, workspace_id: str, knowledge_id: str):
        return result.success(
            DocumentSerializers.Create(
                data={"knowledge_id": knowledge_id, "workspace_id": workspace_id, "user_id": request.user.id}
            ).save_table({"file_list": request.FILES.getlist("file")}, with_valid=True)
        )


class Template(APIView):
    authentication_classes = [TokenAuth]

    @extend_schema(
        summary=_("Get QA template"),
        operation_id=_("Get QA template"),  # type: ignore
        parameters=TemplateExportAPI.get_parameters(),
        responses=TemplateExportAPI.get_response(),
        tags=[_("Knowledge Base/Documentation")],  # type: ignore
    )
    def get(self, request: Request):
        return DocumentSerializers.Export(data={"type": request.query_params.get("type")}).export(with_valid=True)


class TableTemplate(APIView):
    authentication_classes = [TokenAuth]

    @extend_schema(
        summary=_("Get form template"),
        operation_id=_("Get form template"),  # type: ignore
        parameters=TemplateExportAPI.get_parameters(),
        responses=TemplateExportAPI.get_response(),
        tags=[_("Knowledge Base/Documentation")],
    )  # type: ignore
    def get(self, request: Request):
        return DocumentSerializers.Export(data={"type": request.query_params.get("type")}).table_export(with_valid=True)
