import traceback

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet

from common.utils.logger import maxkb_logger
from ops import celery_app

from knowledge.models import File, FileSourceType

SPLIT_TASK_CACHE_TIMEOUT = 60 * 60 * 2
SPLIT_TASK_CACHE_PREFIX = "split-preview"


def get_split_task_cache_key(task_id):
    return f"{SPLIT_TASK_CACHE_PREFIX}:{task_id}"


def calculate_split_progress(stage, processed=0, total=0):
    if stage == "completed":
        return 100
    if stage == "splitting":
        return 80 + int(19 * processed / total) if total else 80
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
    return cache.get(get_split_task_cache_key(task_id))


def update_split_task_state(task_id, **fields):
    cache_key = get_split_task_cache_key(task_id)
    state = cache.get(cache_key)
    if state is None:
        return None
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

        stage_start, stage_weight = {
            "filtering": (0.05, 0.1),
            "vision": (0.15, 0.65),
            "splitting": (0.8, 0.19),
        }.get(stage, (0.0, 0.0))
        stage_fraction = processed / total if total else 0
        file_fraction = min(stage_start + stage_weight * stage_fraction, 0.99)
        overall_progress = int(
            5 + 94 * min((completed_files + file_fraction) / file_count, 1)
        )

        if total and processed >= total and not active_complete:
            active_complete = True
            stage_occurrences[stage] = active_base + total
            if stage == "splitting":
                completed_files = min(completed_files + 1, file_count)

        update_split_task_state(
            task_id,
            status="processing",
            stage=stage,
            progress=overall_progress,
            processed=cumulative_processed,
            total=stage_occurrences[stage],
            message=message,
        )

    try:
        update_split_task_state(
            task_id,
            status="processing",
            stage="parsing",
            processed=0,
            total=len(input_file_ids),
            message="正在解析上传文件",
        )
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
        }
        if split_config.get("patterns") is not None:
            parse_data["patterns"] = split_config.get("patterns")
        if split_config.get("with_filter") is not None:
            parse_data["with_filter"] = split_config.get("with_filter")
        preview_result = DocumentSerializers.Split(
            data={
                "workspace_id": workspace_id,
                "knowledge_id": knowledge_id,
            },
            context={"progress_callback": progress_callback},
        ).parse(parse_data)
        update_split_task_state(
            task_id,
            status="completed",
            stage="completed",
            processed=1,
            total=1,
            message="分段预览已生成",
            result=preview_result,
            error=None,
        )
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
