import traceback

from django.db.models import QuerySet

from common.utils.logger import maxkb_logger
from knowledge.models import Document, Paragraph
from knowledge.task.split_preview import update_split_task_state
from ops import celery_app


class DocumentQualityTaskStopped(Exception):
    pass


@celery_app.task(name="celery:optimize_document_quality")
def optimize_document_quality_task(
    task_id, user_id, workspace_id, knowledge_id, document_id, model_id
):
    from knowledge.serializers.document import DocumentSerializers

    def progress_callback(stage, processed, total, message):
        state = update_split_task_state(
            task_id,
            status="processing",
            stage=stage,
            processed=processed,
            total=total,
            message=message,
        )
        if state is None or state.get("status") == "cancelled":
            raise DocumentQualityTaskStopped

    try:
        initial_state = update_split_task_state(
            task_id,
            status="processing",
            stage="quality_analyzing",
            message="正在分析段落质量",
        )
        if initial_state is None or initial_state.get("status") == "cancelled":
            return
        document = QuerySet(Document).filter(
            id=document_id, knowledge_id=knowledge_id
        ).first()
        if document is None:
            raise ValueError("Document does not exist")
        before = list(
            QuerySet(Paragraph)
            .filter(document_id=document_id, knowledge_id=knowledge_id)
            .order_by("position")
            .values(
                "id", "title", "content", "position", "is_active", "update_time"
            )
        )
        serializer = DocumentSerializers.Split(
            context={"progress_callback": progress_callback}
        )
        serializer._data = {
            "workspace_id": workspace_id,
            "knowledge_id": knowledge_id,
        }
        after, report = serializer._quality_optimize_paragraphs(
            document.name, before, True, model_id
        )
        snapshot = [
            {"id": str(item["id"]), "update_time": str(item["update_time"])}
            for item in before
        ]
        serializable_before = [
            {
                **item,
                "id": str(item["id"]),
                "update_time": str(item["update_time"]),
            }
            for item in before
        ]
        update_split_task_state(
            task_id,
            status="completed",
            stage="completed",
            progress=100,
            message="质量优化草稿已生成",
            result={
                "before": serializable_before,
                "after": after,
                "report": report,
                "snapshot": snapshot,
            },
            error=None,
        )
    except DocumentQualityTaskStopped:
        return
    except Exception as e:
        maxkb_logger.error(
            f"Document quality task {task_id} failed: {e}, {traceback.format_exc()}"
        )
        update_split_task_state(
            task_id,
            status="failed",
            stage="failed",
            message="质量优化失败",
            error="质量优化失败，请检查模型配置或稍后重试",
            result=None,
        )
