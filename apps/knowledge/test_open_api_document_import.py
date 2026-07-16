import json
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

    @patch("knowledge.open_api.views.create_import_task_state")
    @patch("knowledge.open_api.views.DocumentSerializers.Split._validate_model_selection")
    @patch("knowledge.open_api.views.check_knowledge_permission")
    @patch("knowledge.open_api.views.authenticate_open_api_key")
    def test_upload_task_id_uses_uuid7_compatibility_layer(
        self, authenticate, check_knowledge_permission, validate_model_selection, create_import_task_state
    ):
        from knowledge.open_api.views import KnowledgeOpenAPIUploadDocumentView

        class RequestValues(dict):
            def getlist(self, key):
                value = self.get(key)
                if value is None:
                    return []
                return value if isinstance(value, list) else [value]

        authenticate.return_value = SimpleNamespace(
            key={"id": "key-1"}, user=SimpleNamespace(id="user-1")
        )
        create_import_task_state.return_value = (
            {"task_id": "existing-task", "status": "queued", "stage": "queued"},
            False,
        )
        path = "/openapi/knowledge/v1/workspaces/default/knowledges/knowledge-1/documents/upload"
        request = SimpleNamespace(
            FILES=RequestValues(),
            data=RequestValues({"file_id": "file-1", "idempotency_key": "request-1"}),
            headers={},
            path=path,
            build_absolute_uri=lambda request_path: f"http://testserver{request_path}",
        )

        response = KnowledgeOpenAPIUploadDocumentView().post(
            request, workspace_id="default", knowledge_id="knowledge-1"
        )

        self.assertEqual(response.status_code, 200)
        create_import_task_state.assert_called_once()
        generated_task_id = create_import_task_state.call_args.args[0]
        self.assertNotEqual(generated_task_id, "existing-task")

    @patch("knowledge.open_api.views.check_workspace")
    @patch("knowledge.open_api.views.authenticate_open_api_key")
    @patch("knowledge.open_api.views.ModelSerializer.Query.model_list")
    def test_model_list_returns_safe_workspace_and_shared_models(
        self, model_list, authenticate, check_workspace
    ):
        from knowledge.open_api.views import KnowledgeOpenAPIModelView
        from rest_framework.request import Request

        authenticate.return_value = SimpleNamespace(user=SimpleNamespace(id="user-1"))
        model_list.return_value = {
            "model": [{
                "id": "llm-1", "name": "通义千问", "model_name": "qwen-plus",
                "model_type": "LLM", "provider": "Qwen", "credential": {"api_key": "secret"}
            }],
            "shared_model": [{
                "id": "llm-2", "name": "共享模型", "model_name": "shared-chat",
                "model_type": "LLM", "provider": "OpenAI", "model_params_form": ["secret"]
            }],
        }
        request = Request(RequestFactory().get(
            "/openapi/knowledge/v1/workspaces/default/models", {"model_type": "LLM"}
        ))

        response = KnowledgeOpenAPIModelView().get(request, workspace_id="default")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"][0]["scope"], "workspace")
        self.assertEqual(payload["data"][1]["scope"], "shared")
        self.assertNotIn("credential", payload["data"][0])
        self.assertNotIn("model_params_form", payload["data"][1])
        check_workspace.assert_called_once_with(authenticate.return_value, "default")
        model_list.assert_called_once_with(workspace_id="default", with_valid=True)

    @patch("knowledge.open_api.views.check_workspace")
    @patch("knowledge.open_api.views.authenticate_open_api_key")
    def test_model_list_rejects_unsupported_model_type_after_workspace_check(
        self, authenticate, check_workspace
    ):
        from knowledge.open_api.views import KnowledgeOpenAPIModelView
        from rest_framework.request import Request

        authenticate.return_value = SimpleNamespace(
            key={"workspace_id": "default"}, user=SimpleNamespace(id="user-1")
        )
        request = Request(RequestFactory().get(
            "/openapi/knowledge/v1/workspaces/default/models", {"model_type": "EMBEDDING"}
        ))

        with self.assertRaises(AppApiException) as error:
            KnowledgeOpenAPIModelView().get(request, workspace_id="default")

        check_workspace.assert_called_once_with(authenticate.return_value, "default")
        self.assertEqual(error.exception.code, 400)

    @patch("knowledge.open_api.views.check_workspace")
    @patch("knowledge.open_api.views.authenticate_open_api_key")
    def test_model_list_rejects_wrong_workspace_before_model_type_validation(
        self, authenticate, check_workspace
    ):
        from common.exception.app_exception import AppUnauthorizedFailed
        from knowledge.open_api.views import KnowledgeOpenAPIModelView
        from rest_framework.request import Request

        authenticate.return_value = SimpleNamespace(
            key={"workspace_id": "workspace-a"}, user=SimpleNamespace(id="user-1")
        )
        check_workspace.side_effect = AppUnauthorizedFailed(403, "No permission to access")
        request = Request(RequestFactory().get(
            "/openapi/knowledge/v1/workspaces/workspace-b/models", {"model_type": "EMBEDDING"}
        ))

        with self.assertRaises(AppUnauthorizedFailed) as error:
            KnowledgeOpenAPIModelView().get(request, workspace_id="workspace-b")

        check_workspace.assert_called_once_with(authenticate.return_value, "workspace-b")
        self.assertEqual(error.exception.code, 403)
