import traceback

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet

from common.utils.logger import maxkb_logger
from ops import celery_app

from knowledge.models import File, FileSourceType

SPLIT_TASK_CACHE_TIMEOUT = 60 * 60 * 2
SPLIT_TASK_CACHE_PREFIX = "split-preview"
SPLIT_TASK_CANCELLED_CACHE_PREFIX = "split-preview-cancelled"


class SplitPreviewTaskExpired(Exception):
    pass


def get_split_task_cache_key(task_id):
    return f"{SPLIT_TASK_CACHE_PREFIX}:{task_id}"


def get_split_task_cancelled_cache_key(task_id):
    return f"{SPLIT_TASK_CANCELLED_CACHE_PREFIX}:{task_id}"


def _as_cancelled_state(state):
    if state is None:
        return None
    cancelled = dict(state)
    cancelled.update(
        {
            "status": "cancelled",
            "stage": "cancelled",
            "message": "任务已终止",
            "result": None,
            "error": None,
        }
    )
    return cancelled


def calculate_split_progress(stage, processed=0, total=0):
    if stage == "completed":
        return 100
    if stage == "splitting":
        return 80 + int(19 * processed / total) if total else 80
    if stage == "quality_validating":
        return 95
    if stage == "quality_optimizing":
        return 10 + int(80 * processed / total) if total else 10
    if stage == "quality_analyzing":
        return 10
    if stage == "quality_cleaning":
        return 5
    if stage == "vision":
        return 20 + int(60 * processed / total) if total else 20
    if stage == "filtering":
        return 10 + int(10 * processed / total) if total else 10
    if stage == "parsing":
        return 5
    return 0


def create_split_task_state(task_id, user_id, workspace_id, knowledge_id):
    state = {
        "task_id": str(task_id),
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
        "knowledge_id": str(knowledge_id),
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "processed": 0,
        "total": 0,
        "remaining": 0,
        "message": "等待处理",
        "result": None,
        "error": None,
    }
    cache.set(get_split_task_cache_key(task_id), state, timeout=SPLIT_TASK_CACHE_TIMEOUT)
    return state


def get_split_task_state(task_id):
    state = cache.get(get_split_task_cache_key(task_id))
    if cache.get(get_split_task_cancelled_cache_key(task_id)) is True:
        return _as_cancelled_state(state)
    return state


def delete_split_task_state(task_id):
    cache.delete_many(
        [
            get_split_task_cache_key(task_id),
            get_split_task_cancelled_cache_key(task_id),
        ]
    )


def update_split_task_state(task_id, **fields):
    cache_key = get_split_task_cache_key(task_id)
    state = cache.get(cache_key)
    if state is None:
        return None
    if cache.get(get_split_task_cancelled_cache_key(task_id)) is True:
        return _as_cancelled_state(state)
    if state.get("status") == "cancelled" and fields.get("status") != "cancelled":
        return state
    explicit_progress = fields.pop("progress", None)
    state.update(fields)
    processed = int(state.get("processed") or 0)
    total = int(state.get("total") or 0)
    state["remaining"] = max(total - processed, 0)
    calculated_progress = calculate_split_progress(state.get("stage"), processed, total)
    next_progress = calculated_progress if explicit_progress is None else int(explicit_progress)
    state["progress"] = max(int(state.get("progress") or 0), next_progress)
    cache.set(cache_key, state, timeout=SPLIT_TASK_CACHE_TIMEOUT)
    return state


def cancel_split_task_state(task_id):
    cache_key = get_split_task_cache_key(task_id)
    cache.set(
        get_split_task_cancelled_cache_key(task_id),
        True,
        timeout=SPLIT_TASK_CACHE_TIMEOUT,
    )
    state = cache.get(cache_key)
    if state is None:
        return None
    state = _as_cancelled_state(state)
    cache.set(cache_key, state, timeout=SPLIT_TASK_CACHE_TIMEOUT)
    return state


def cleanup_split_preview_files(task_id):
    QuerySet(File).filter(
        source_type=FileSourceType.TEMPORARY_120_MINUTE.value,
        source_id=str(task_id),
    ).delete()
    QuerySet(File).filter(meta__split_preview_task_id=str(task_id)).delete()


@celery_app.task(name="celery:cleanup_split_preview_files")
def cleanup_split_preview_files_task(task_id):
    cleanup_split_preview_files(task_id)


def force_cancel_split_preview_task(task_id):
    state = get_split_task_state(task_id)
    if state is None:
        return None
    if state.get("status") in {"completed", "failed", "cancelled"}:
        raise ValueError("Split preview task is already finished")

    state = cancel_split_task_state(task_id)
    celery_task_id = state.get("celery_task_id") if state else None
    if celery_task_id:
        try:
            celery_app.control.revoke(
                celery_task_id, terminate=True, signal="SIGTERM"
            )
        except Exception as e:
            maxkb_logger.error(f"Failed to revoke split preview task {task_id}: {e}")
    try:
        cleanup_split_preview_files(task_id)
    except Exception as e:
        maxkb_logger.error(f"Failed to clean split preview task {task_id}: {e}")
    try:
        cleanup_split_preview_files_task.apply_async(
            args=[str(task_id)], countdown=5
        )
    except Exception as e:
        maxkb_logger.error(
            f"Failed to schedule delayed cleanup for split preview task {task_id}: {e}"
        )
    return state


@celery_app.task(name="celery:split_document_preview")
def split_document_preview_task(
    task_id,
    user_id,
    workspace_id,
    knowledge_id,
    input_file_ids,
    split_config,
):
    from knowledge.serializers.document import DocumentSerializers

    file_count = max(len(input_file_ids), 1)
    completed_files = 0
    stage_occurrences = {}
    active_stage = None
    active_base = 0
    active_complete = False

    def progress_callback(stage, processed, total, message):
        nonlocal active_base, active_complete, active_stage, completed_files
        processed = int(processed or 0)
        total = int(total or 0)
        if stage != active_stage or (active_complete and processed == 0):
            active_stage = stage
            active_base = stage_occurrences.get(stage, 0)
            active_complete = False

        cumulative_processed = active_base + processed
        cumulative_total = active_base + total
        stage_occurrences[stage] = max(stage_occurrences.get(stage, 0), cumulative_total)

        quality_enabled = bool(split_config.get("quality_optimize"))
        stage_weights = (
            {
                "filtering": (0.05, 0.1),
                "vision": (0.15, 0.53),
                "splitting": (0.68, 0.14),
                "quality_cleaning": (0.83, 0.02),
                "quality_analyzing": (0.85, 0.02),
                "quality_optimizing": (0.87, 0.11),
                "quality_validating": (0.98, 0.01),
            }
            if quality_enabled
            else {
                "filtering": (0.05, 0.1),
                "vision": (0.15, 0.65),
                "splitting": (0.8, 0.19),
            }
        )
        stage_start, stage_weight = stage_weights.get(stage, (0.0, 0.0))
        stage_fraction = processed / total if total else 0
        file_fraction = min(stage_start + stage_weight * stage_fraction, 0.99)
        overall_progress = int(
            5 + 94 * min((completed_files + file_fraction) / file_count, 1)
        )

        if quality_enabled and stage == "quality_validating" and not active_complete:
            active_complete = True
            completed_files = min(completed_files + 1, file_count)
        elif total and processed >= total and not active_complete:
            active_complete = True
            stage_occurrences[stage] = active_base + total
            if stage == "splitting" and not quality_enabled:
                completed_files = min(completed_files + 1, file_count)

        state = update_split_task_state(
            task_id,
            status="processing",
            stage=stage,
            progress=overall_progress,
            processed=cumulative_processed,
            total=stage_occurrences[stage],
            message=message,
        )
        if state is None or state.get("status") == "cancelled":
            raise SplitPreviewTaskExpired("Split preview task stopped")
    try:
        state = update_split_task_state(
            task_id,
            status="processing",
            stage="parsing",
            processed=0,
            total=len(input_file_ids),
            message="正在解析上传文件",
        )
        if state is None or state.get("status") == "cancelled":
            raise SplitPreviewTaskExpired("Split preview task stopped")
        file_map = {
            str(file.id): file
            for file in QuerySet(File).filter(
                id__in=input_file_ids,
                source_type=FileSourceType.TEMPORARY_120_MINUTE.value,
                source_id=str(task_id),
            )
        }
        if len(file_map) != len(input_file_ids):
            raise ValueError("Split preview input file does not exist")
        uploaded_files = [
            SimpleUploadedFile(
                file_map[str(file_id)].file_name,
                file_map[str(file_id)].get_bytes(),
            )
            for file_id in input_file_ids
        ]
        parse_data = {
            "file": uploaded_files,
            "limit": split_config.get("limit", 4096),
            "split_strategy": split_config.get("split_strategy") or "",
            "model_id": split_config.get("model_id"),
            "vision_model_id": split_config.get("vision_model_id"),
            "llm_model_id": split_config.get("llm_model_id"),
            "quality_optimize": split_config.get("quality_optimize", False),
        }
        if split_config.get("patterns") is not None:
            parse_data["patterns"] = split_config.get("patterns")
        if split_config.get("with_filter") is not None:
            parse_data["with_filter"] = split_config.get("with_filter")
        split_serializer = DocumentSerializers.Split(
            data={
                "workspace_id": workspace_id,
                "knowledge_id": knowledge_id,
            },
            context={
                "progress_callback": progress_callback,
                "split_preview_task_id": str(task_id),
            },
        )
        preview_result = split_serializer.parse(parse_data)
        state = update_split_task_state(
            task_id,
            status="completed",
            stage="completed",
            processed=1,
            total=1,
            message="分段预览已生成",
            result=preview_result,
            error=None,
        )
        if state is None or state.get("status") == "cancelled":
            generated_file_ids = set(
                getattr(split_serializer, "_request_source_file_ids", set())
            ) | set(getattr(split_serializer, "_request_image_ids", set()))
            if generated_file_ids:
                QuerySet(File).filter(id__in=generated_file_ids).delete()
            raise SplitPreviewTaskExpired("Split preview task stopped")
        if state.get("open_api") is True:
            try:
                cleanup_split_preview_files_task.apply_async(
                    args=[str(task_id)], countdown=SPLIT_TASK_CACHE_TIMEOUT
                )
            except Exception as e:
                maxkb_logger.error(
                    f"Failed to schedule Open API import cleanup {task_id}: {e}"
                )
        if state.get("open_api") is True and state.get("auto_apply") is True:
            from knowledge.open_api.document_import_task import apply_import_task

            apply_import_task(task_id)
    except SplitPreviewTaskExpired:
        pass
    except Exception as e:
        maxkb_logger.error(
            f"Split preview task {task_id} failed: {e}, {traceback.format_exc()}"
        )
        update_split_task_state(
            task_id,
            status="failed",
            stage="failed",
            message="分段预览生成失败",
            error="处理失败，请检查模型配置或稍后重试",
            result=None,
        )
    finally:
        QuerySet(File).filter(
            id__in=input_file_ids,
            source_type=FileSourceType.TEMPORARY_120_MINUTE.value,
            source_id=str(task_id),
        ).delete()
