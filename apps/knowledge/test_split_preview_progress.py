from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase


class SplitPreviewProgressTest(SimpleTestCase):
    def test_progress_stage_boundaries(self):
        from knowledge.task.split_preview import calculate_split_progress

        self.assertEqual(calculate_split_progress("queued", 0, 0), 0)
        self.assertEqual(calculate_split_progress("parsing", 0, 0), 5)
        self.assertEqual(calculate_split_progress("filtering", 5, 10), 15)
        self.assertEqual(calculate_split_progress("vision", 1, 4), 35)
        self.assertEqual(calculate_split_progress("splitting", 1, 2), 89)
        self.assertEqual(calculate_split_progress("completed", 1, 1), 100)

    @patch("knowledge.task.split_preview.cache")
    def test_task_state_uses_two_hour_ttl_and_calculates_remaining(self, cache):
        from knowledge.task.split_preview import create_split_task_state, update_split_task_state

        cache.get.return_value = None
        state = create_split_task_state("task-1", "user-1", "workspace-1", "knowledge-1")

        self.assertEqual(state["status"], "queued")
        cache.set.assert_called_with("split-preview:task-1", state, timeout=7200)

        cache.get.return_value = state
        updated = update_split_task_state(
            "task-1",
            status="processing",
            stage="vision",
            processed=3,
            total=8,
            message="vision",
        )

        self.assertEqual(updated["remaining"], 5)
        self.assertEqual(updated["progress"], 42)
        cache.set.assert_called_with("split-preview:task-1", updated, timeout=7200)

    @patch("knowledge.task.split_preview.cache")
    def test_task_progress_never_moves_backwards(self, cache):
        from knowledge.task.split_preview import update_split_task_state

        cache.get.return_value = {
            "task_id": "task-1",
            "progress": 80,
            "stage": "splitting",
            "processed": 0,
            "total": 2,
        }

        updated = update_split_task_state(
            "task-1", stage="vision", processed=1, total=10
        )

        self.assertEqual(updated["progress"], 80)

    @patch("knowledge.task.split_preview.cache", new=Mock())
    def test_get_task_state_returns_cached_value(self):
        from knowledge.task import split_preview

        split_preview.cache.get.return_value = {"task_id": "task-1"}
        self.assertEqual(split_preview.get_split_task_state("task-1"), {"task_id": "task-1"})

    @patch("knowledge.serializers.document.DocumentSerializers.Split")
    @patch("knowledge.task.split_preview.update_split_task_state")
    @patch("knowledge.task.split_preview.QuerySet")
    def test_celery_task_caches_result_and_cleans_temporary_inputs(
        self, query_set, update_state, split_serializer
    ):
        from knowledge.task.split_preview import split_document_preview_task

        input_file = SimpleNamespace(
            id="file-1", file_name="chapter.pdf", get_bytes=lambda: b"pdf"
        )
        filtered = MagicMock()
        filtered.__iter__.return_value = [input_file]
        query_set.return_value.filter.return_value = filtered
        split_serializer.return_value.parse.return_value = [{"name": "chapter.pdf", "content": []}]

        split_document_preview_task.run(
            "task-1",
            "user-1",
            "workspace-1",
            "knowledge-1",
            ["file-1"],
            {"split_strategy": ""},
        )

        completed_call = next(
            call for call in update_state.call_args_list if call.kwargs.get("status") == "completed"
        )
        self.assertEqual(completed_call.kwargs["result"][0]["name"], "chapter.pdf")
        filtered.delete.assert_called_once()

    @patch("knowledge.serializers.document.DocumentSerializers.Split")
    @patch("knowledge.task.split_preview.update_split_task_state")
    @patch("knowledge.task.split_preview.QuerySet")
    def test_celery_task_caches_failure_and_cleans_temporary_inputs(
        self, query_set, update_state, split_serializer
    ):
        from knowledge.task.split_preview import split_document_preview_task

        input_file = SimpleNamespace(
            id="file-1", file_name="chapter.pdf", get_bytes=lambda: b"pdf"
        )
        filtered = MagicMock()
        filtered.__iter__.return_value = [input_file]
        query_set.return_value.filter.return_value = filtered
        split_serializer.return_value.parse.side_effect = RuntimeError("model failed")

        split_document_preview_task.run(
            "task-1",
            "user-1",
            "workspace-1",
            "knowledge-1",
            ["file-1"],
            {"split_strategy": ""},
        )

        failed_call = next(
            call for call in update_state.call_args_list if call.kwargs.get("status") == "failed"
        )
        self.assertEqual(failed_call.kwargs["error"], "处理失败，请检查模型配置或稍后重试")
        filtered.delete.assert_called_once()
