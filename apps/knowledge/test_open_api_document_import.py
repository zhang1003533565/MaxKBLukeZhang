from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from common.exception.app_exception import AppApiException


TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "knowledge-open-api-import-tests",
    }
}


@override_settings(CACHES=TEST_CACHES)
class KnowledgeOpenAPIImportTaskTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.identity = SimpleNamespace(
            key={"id": "key-1"}, user=SimpleNamespace(id="user-1")
        )

    def test_task_index_is_scoped_and_delete_is_idempotent(self):
        from knowledge.open_api.document_import_task import (
            create_import_task_state,
            delete_import_task_state,
            list_import_task_states,
        )

        create_import_task_state(
            "task-1", self.identity, "workspace-1", "knowledge-1", "digest-1"
        )

        self.assertEqual(
            len(list_import_task_states("key-1", "workspace-1", "knowledge-1")),
            1,
        )
        self.assertEqual(
            list_import_task_states("key-2", "workspace-1", "knowledge-1"), []
        )
        self.assertTrue(delete_import_task_state("task-1"))
        self.assertFalse(delete_import_task_state("task-1"))

    def test_idempotency_returns_existing_task_and_rejects_conflict(self):
        from knowledge.open_api.document_import_task import create_import_task_state

        first, created = create_import_task_state(
            "task-1",
            self.identity,
            "workspace-1",
            "knowledge-1",
            "digest-1",
            idempotency_key="request-1",
        )
        repeated, repeated_created = create_import_task_state(
            "task-2",
            self.identity,
            "workspace-1",
            "knowledge-1",
            "digest-1",
            idempotency_key="request-1",
        )

        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(first["task_id"], repeated["task_id"])
        with self.assertRaises(AppApiException) as error:
            create_import_task_state(
                "task-3",
                self.identity,
                "workspace-1",
                "knowledge-1",
                "different-digest",
                idempotency_key="request-1",
            )
        self.assertEqual(error.exception.code, 409)

    def test_owner_scope_hides_task(self):
        from knowledge.open_api.document_import_task import (
            create_import_task_state,
            get_import_task_state,
        )

        create_import_task_state(
            "task-1", self.identity, "workspace-1", "knowledge-1", "digest-1"
        )

        self.assertIsNotNone(
            get_import_task_state(
                "task-1", "key-1", "workspace-1", "knowledge-1"
            )
        )
        self.assertIsNone(
            get_import_task_state(
                "task-1", "key-2", "workspace-1", "knowledge-1"
            )
        )

    @patch("knowledge.open_api.document_import_task._finalize_import_files")
    @patch("knowledge.serializers.document.DocumentSerializers.Batch.batch_save")
    def test_apply_is_idempotent_after_documents_are_created(
        self, batch_save, finalize_import_files
    ):
        from knowledge.open_api.document_import_task import (
            apply_import_task,
            create_import_task_state,
            update_import_task_state,
        )

        batch_save.return_value = [{"id": "document-1", "name": "manual.pdf"}]
        create_import_task_state(
            "task-1", self.identity, "workspace-1", "knowledge-1", "digest-1"
        )
        update_import_task_state(
            "task-1", status="completed", stage="completed", result=[{"name": "manual.pdf"}]
        )

        first = apply_import_task("task-1")
        repeated = apply_import_task("task-1")

        self.assertEqual(first["status"], "import_completed")
        self.assertEqual(repeated["documents"], first["documents"])
        batch_save.assert_called_once()
        finalize_import_files.assert_called_once()

    def test_apply_lock_rejects_concurrent_apply(self):
        from knowledge.open_api.document_import_task import (
            IMPORT_TASK_APPLY_LOCK_PREFIX,
            apply_import_task,
        )

        cache.set(f"{IMPORT_TASK_APPLY_LOCK_PREFIX}:task-1", True, timeout=120)

        with self.assertRaises(AppApiException) as error:
            apply_import_task("task-1")
        self.assertEqual(error.exception.code, 409)


class KnowledgeOpenAPIDocumentTest(SimpleTestCase):
    def test_public_markdown_content_and_download(self):
        from knowledge.open_api.views import (
            KnowledgeOpenAPIDocsContentView,
            KnowledgeOpenAPIDocsDownloadView,
        )

        request = RequestFactory().get("/openapi/knowledge/docs/content")
        content_response = KnowledgeOpenAPIDocsContentView.as_view()(request)
        download_response = KnowledgeOpenAPIDocsDownloadView.as_view()(request)

        self.assertEqual(content_response.status_code, 200)
        self.assertTrue(content_response["Content-Type"].startswith("text/markdown"))
        self.assertIn("异步文档导入", content_response.content.decode("utf-8"))
        self.assertIn("attachment", download_response["Content-Disposition"])
        self.assertNotIn("mkb_", content_response.content.decode("utf-8").replace("mkb_your_api_key", ""))

    def test_task_response_does_not_expose_preview_or_credentials(self):
        from knowledge.open_api.views import _task_response

        response = _task_response(
            {
                "task_id": "task-1",
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "result": [{"name": "private-preview"}],
                "request_digest": "secret",
            }
        )

        self.assertEqual(response["status"], "PREVIEW_READY")
        self.assertNotIn("result", response)
        self.assertNotIn("request_digest", response)
