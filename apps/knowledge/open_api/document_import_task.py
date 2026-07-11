import hashlib
import json
from copy import deepcopy

from django.core.cache import cache
from django.db.models import QuerySet

from common.exception.app_exception import AppApiException
from knowledge.models import Document, File
from knowledge.task.split_preview import (
    SPLIT_TASK_CACHE_TIMEOUT,
    create_split_task_state,
    delete_split_task_state,
    get_split_task_state,
    update_split_task_state,
)


IMPORT_TASK_INDEX_PREFIX = "knowledge-open-api-import-index"
IMPORT_TASK_IDEMPOTENCY_PREFIX = "knowledge-open-api-import-idempotency"
IMPORT_TASK_APPLY_LOCK_PREFIX = "knowledge-open-api-import-apply-lock"


def build_request_digest(data):
    normalized = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _index_key(owner_key_id, workspace_id, knowledge_id):
    return f"{IMPORT_TASK_INDEX_PREFIX}:{owner_key_id}:{workspace_id}:{knowledge_id}"


def _idempotency_key(owner_key_id, workspace_id, knowledge_id, idempotency_key):
    return (
        f"{IMPORT_TASK_IDEMPOTENCY_PREFIX}:{owner_key_id}:{workspace_id}:"
        f"{knowledge_id}:{idempotency_key}"
    )


def create_import_task_state(
    task_id,
    identity,
    workspace_id,
    knowledge_id,
    request_digest,
    idempotency_key=None,
    auto_apply=False,
):
    owner_key_id = str(identity.key.get("id"))
    idempotency_cache_key = None
    if idempotency_key:
        idempotency_cache_key = _idempotency_key(
            owner_key_id, workspace_id, knowledge_id, idempotency_key
        )
        existing = cache.get(idempotency_cache_key)
        if existing:
            if existing.get("request_digest") != request_digest:
                raise AppApiException(
                    409, "The idempotency key has already been used with different parameters"
                )
            state = get_split_task_state(existing.get("task_id"))
            if state is not None:
                return state, False
            raise AppApiException(409, "The idempotent request is being created; retry later")

        reserved = cache.add(
            idempotency_cache_key,
            {"task_id": str(task_id), "request_digest": request_digest},
            timeout=30,
        )
        if not reserved:
            existing = cache.get(idempotency_cache_key) or {}
            if existing.get("request_digest") != request_digest:
                raise AppApiException(
                    409, "The idempotency key has already been used with different parameters"
                )
            state = get_split_task_state(existing.get("task_id"))
            if state is not None:
                return state, False
            raise AppApiException(409, "The idempotent request is being created; retry later")

    try:
        create_split_task_state(task_id, identity.user.id, workspace_id, knowledge_id)
        state = update_split_task_state(
            task_id,
            owner_key_id=owner_key_id,
            open_api=True,
            auto_apply=bool(auto_apply),
            request_digest=request_digest,
            idempotency_key=idempotency_key,
            documents=[],
        )
    except Exception:
        if idempotency_cache_key:
            cache.delete(idempotency_cache_key)
        raise
    index_key = _index_key(owner_key_id, workspace_id, knowledge_id)
    task_ids = cache.get(index_key) or []
    task_ids = [str(task_id), *[row for row in task_ids if row != str(task_id)]]
    cache.set(index_key, task_ids, timeout=SPLIT_TASK_CACHE_TIMEOUT)
    if idempotency_cache_key:
        cache.set(
            idempotency_cache_key,
            {"task_id": str(task_id), "request_digest": request_digest},
            timeout=SPLIT_TASK_CACHE_TIMEOUT,
        )
    return state, True


def get_import_task_state(task_id, owner_key_id=None, workspace_id=None, knowledge_id=None):
    state = get_split_task_state(task_id)
    if state is None or not state.get("open_api"):
        return None
    expected = {
        "owner_key_id": owner_key_id,
        "workspace_id": workspace_id,
        "knowledge_id": knowledge_id,
    }
    if any(
        value is not None and str(state.get(key)) != str(value)
        for key, value in expected.items()
    ):
        return None
    return state


def update_import_task_state(task_id, **fields):
    return update_split_task_state(task_id, **fields)


def list_import_task_states(owner_key_id, workspace_id, knowledge_id):
    index_key = _index_key(owner_key_id, workspace_id, knowledge_id)
    task_ids = cache.get(index_key) or []
    states = []
    valid_task_ids = []
    for task_id in task_ids:
        state = get_import_task_state(
            task_id, owner_key_id, workspace_id, knowledge_id
        )
        if state is not None:
            states.append(state)
            valid_task_ids.append(task_id)
    if valid_task_ids != task_ids:
        cache.set(index_key, valid_task_ids, timeout=SPLIT_TASK_CACHE_TIMEOUT)
    return states


def delete_import_task_state(task_id):
    state = get_import_task_state(task_id)
    if state is None:
        return False
    index_key = _index_key(
        state.get("owner_key_id"), state.get("workspace_id"), state.get("knowledge_id")
    )
    task_ids = cache.get(index_key) or []
    cache.set(
        index_key,
        [row for row in task_ids if row != str(task_id)],
        timeout=SPLIT_TASK_CACHE_TIMEOUT,
    )
    if state.get("idempotency_key"):
        cache.delete(
            _idempotency_key(
                state.get("owner_key_id"),
                state.get("workspace_id"),
                state.get("knowledge_id"),
                state.get("idempotency_key"),
            )
        )
    delete_split_task_state(task_id)
    return True


def apply_import_task(task_id):
    lock_key = f"{IMPORT_TASK_APPLY_LOCK_PREFIX}:{task_id}"
    if not cache.add(lock_key, True, timeout=120):
        raise AppApiException(409, "The task is being applied")
    try:
        return _apply_import_task_locked(task_id)
    finally:
        cache.delete(lock_key)


def _apply_import_task_locked(task_id):
    state = get_import_task_state(task_id)
    if state is None:
        return None
    if state.get("status") == "import_completed":
        return state
    if state.get("status") != "completed" or not state.get("result"):
        raise AppApiException(409, "The task is not ready to apply")

    from knowledge.serializers.document import DocumentSerializers

    preview_result = deepcopy(state.get("result"))
    for document in preview_result:
        document["meta"] = {
            **(document.get("meta") or {}),
            "open_api_import_task_id": str(task_id),
        }

    update_import_task_state(
        task_id,
        status="applying",
        stage="applying",
        progress=99,
        message="正在创建文档并进入向量化队列",
    )
    try:
        documents = DocumentSerializers.Batch(
            data={
                "workspace_id": state.get("workspace_id"),
                "knowledge_id": state.get("knowledge_id"),
                "user_id": state.get("user_id"),
            }
        ).batch_save(preview_result)
        _finalize_import_files(task_id, preview_result)
        return update_import_task_state(
            task_id,
            status="import_completed",
            stage="completed",
            progress=100,
            processed=len(documents),
            total=len(documents),
            message="文档已创建并进入向量化队列",
            documents=documents,
            result=None,
            error=None,
        )
    except Exception:
        try:
            persisted_documents = list(
                QuerySet(Document)
                .filter(meta__open_api_import_task_id=str(task_id))
                .values("id", "name")
            )
        except Exception:
            persisted_documents = []
        if persisted_documents:
            documents = [
                {**document, "id": str(document.get("id"))}
                for document in persisted_documents
            ]
            _finalize_import_files(task_id, preview_result)
            return update_import_task_state(
                task_id,
                status="import_completed",
                stage="completed",
                progress=100,
                processed=len(documents),
                total=len(documents),
                message="文档已创建，但部分向量化任务提交失败，请在文档列表中重试",
                documents=documents,
                result=None,
                error=None,
                embedding_warning=True,
            )
        update_import_task_state(
            task_id,
            status="failed",
            stage="failed",
            message="文档创建失败",
            error="文档创建失败，请稍后重试",
        )
        raise


def _finalize_import_files(task_id, preview_result):
    source_file_ids = [
        str(document.get("source_file_id"))
        for document in preview_result
        if document.get("source_file_id")
    ]
    if source_file_ids:
        QuerySet(File).filter(id__in=source_file_ids).delete()
    for file in QuerySet(File).filter(meta__split_preview_task_id=str(task_id)):
        meta = dict(file.meta or {})
        meta.pop("split_preview_task_id", None)
        QuerySet(File).filter(id=file.id).update(meta=meta)
