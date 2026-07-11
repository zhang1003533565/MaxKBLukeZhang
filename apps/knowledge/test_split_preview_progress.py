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
        self.assertEqual(calculate_split_progress("quality_cleaning", 0, 0), 5)
        self.assertEqual(calculate_split_progress("quality_analyzing", 0, 0), 10)
        self.assertEqual(calculate_split_progress("quality_optimizing", 2, 4), 50)
        self.assertEqual(calculate_split_progress("quality_validating", 4, 4), 95)
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

    @patch("knowledge.task.split_preview.cache")
    def test_cancelled_task_state_cannot_be_overwritten_by_worker(self, cache):
        from knowledge.task.split_preview import update_split_task_state

        cancelled = {
            "task_id": "task-1",
            "status": "cancelled",
            "stage": "cancelled",
            "progress": 34,
            "processed": 11,
            "total": 46,
        }
        cache.get.return_value = cancelled

        updated = update_split_task_state(
            "task-1", status="failed", stage="failed", message="failed"
        )

        self.assertEqual(updated, cancelled)
        cache.set.assert_not_called()

    @patch("knowledge.task.split_preview.cache")
    def test_cancel_split_task_state_preserves_progress_and_clears_result(self, cache):
        from knowledge.task.split_preview import cancel_split_task_state

        cache.get.return_value = {
            "task_id": "task-1",
            "status": "processing",
            "stage": "vision",
            "progress": 34,
            "processed": 11,
            "total": 46,
            "result": ["preview"],
            "error": "old",
        }

        updated = cancel_split_task_state("task-1")

        self.assertEqual(updated["status"], "cancelled")
        self.assertEqual(updated["stage"], "cancelled")
        self.assertEqual(updated["progress"], 34)
        self.assertIsNone(updated["result"])
        self.assertIsNone(updated["error"])
        self.assertEqual(cache.set.call_count, 2)

    @patch("knowledge.task.split_preview.cache")
    def test_cancel_tombstone_masks_stale_worker_completion(self, cache):
        from knowledge.task.split_preview import get_split_task_state

        cache.get.side_effect = [
            {
                "task_id": "task-1",
                "status": "completed",
                "stage": "completed",
                "result": ["stale-result"],
            },
            True,
        ]

        state = get_split_task_state("task-1")

        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(state["stage"], "cancelled")
        self.assertIsNone(state["result"])

    @patch("knowledge.task.split_preview.QuerySet")
    def test_cleanup_split_preview_files_deletes_only_task_owned_files(self, query_set):
        from knowledge.task.split_preview import cleanup_split_preview_files

        cleanup_split_preview_files("task-1")

        filters = [call.kwargs for call in query_set.return_value.filter.call_args_list]
        self.assertIn(
            {
                "source_type": "TEMPORARY_120_MINUTE",
                "source_id": "task-1",
            },
            filters,
        )
        self.assertIn({"meta__split_preview_task_id": "task-1"}, filters)
        self.assertEqual(query_set.return_value.filter.return_value.delete.call_count, 2)

    @patch("knowledge.task.split_preview.cleanup_split_preview_files")
    def test_delayed_cleanup_task_uses_idempotent_cleanup(self, cleanup):
        from knowledge.task.split_preview import cleanup_split_preview_files_task

        cleanup_split_preview_files_task.run("task-1")

        cleanup.assert_called_once_with("task-1")

    @patch("knowledge.task.split_preview.cleanup_split_preview_files_task.apply_async")
    @patch("knowledge.task.split_preview.cleanup_split_preview_files")
    @patch("knowledge.task.split_preview.celery_app.control.revoke")
    @patch("knowledge.task.split_preview.cache")
    def test_force_cancel_revokes_worker_and_runs_two_cleanup_passes(
        self, cache, revoke, cleanup, delayed_cleanup
    ):
        from knowledge.task.split_preview import force_cancel_split_preview_task

        cache.get.return_value = {
            "task_id": "task-1",
            "status": "processing",
            "stage": "vision",
            "celery_task_id": "celery-1",
            "progress": 34,
        }

        state = force_cancel_split_preview_task("task-1")

        self.assertEqual(state["status"], "cancelled")
        revoke.assert_called_once_with("celery-1", terminate=True, signal="SIGTERM")
        cleanup.assert_called_once_with("task-1")
        delayed_cleanup.assert_called_once_with(args=["task-1"], countdown=5)

    @patch("knowledge.task.split_preview.cleanup_split_preview_files_task.apply_async")
    @patch("knowledge.task.split_preview.cleanup_split_preview_files")
    @patch("knowledge.task.split_preview.celery_app.control.revoke")
    @patch("knowledge.task.split_preview.cache")
    def test_force_cancel_stays_successful_when_delayed_cleanup_cannot_be_scheduled(
        self, cache, _revoke, _cleanup, delayed_cleanup
    ):
        from knowledge.task.split_preview import force_cancel_split_preview_task

        cache.get.return_value = {
            "task_id": "task-1",
            "status": "processing",
            "celery_task_id": "celery-1",
        }
        delayed_cleanup.side_effect = RuntimeError("broker unavailable")

        state = force_cancel_split_preview_task("task-1")

        self.assertEqual(state["status"], "cancelled")

    @patch("knowledge.task.split_preview.cache")
    def test_explicit_overall_progress_is_used_for_multi_file_tasks(self, cache):
        from knowledge.task.split_preview import update_split_task_state

        cache.get.return_value = {
            "task_id": "task-1",
            "progress": 5,
            "stage": "filtering",
            "processed": 0,
            "total": 10,
        }

        updated = update_split_task_state(
            "task-1", stage="filtering", progress=52, processed=10, total=18
        )

        self.assertEqual(updated["progress"], 52)
        self.assertEqual(updated["remaining"], 8)

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

    @patch("knowledge.serializers.document.DocumentSerializers.Split")
    @patch("knowledge.task.split_preview.update_split_task_state")
    @patch("knowledge.task.split_preview.QuerySet")
    def test_celery_task_accumulates_stage_counts_across_files(
        self, query_set, update_state, split_serializer
    ):
        from knowledge.task.split_preview import split_document_preview_task

        input_files = [
            SimpleNamespace(id="file-1", file_name="one.pdf", get_bytes=lambda: b"one"),
            SimpleNamespace(id="file-2", file_name="two.pdf", get_bytes=lambda: b"two"),
        ]
        filtered = MagicMock()
        filtered.__iter__.return_value = input_files
        query_set.return_value.filter.return_value = filtered

        def parse(_parse_data):
            callback = split_serializer.call_args.kwargs["context"]["progress_callback"]
            callback("filtering", 0, 10, "filtering one")
            callback("filtering", 10, 10, "filtering one")
            callback("splitting", 0, 2, "splitting one")
            callback("splitting", 2, 2, "splitting one")
            callback("filtering", 0, 8, "filtering two")
            callback("filtering", 3, 8, "filtering two")
            return []

        split_serializer.return_value.parse.side_effect = parse

        split_document_preview_task.run(
            "task-1",
            "user-1",
            "workspace-1",
            "knowledge-1",
            ["file-1", "file-2"],
            {"split_strategy": ""},
        )

        second_file_call = next(
            call
            for call in update_state.call_args_list
            if call.kwargs.get("message") == "filtering two"
            and call.kwargs.get("processed") == 13
        )
        self.assertEqual(second_file_call.kwargs["total"], 18)
        self.assertGreater(second_file_call.kwargs["progress"], 50)

    @patch("knowledge.serializers.document.DocumentSerializers.Split")
    @patch("knowledge.task.split_preview.update_split_task_state")
    @patch("knowledge.task.split_preview.QuerySet")
    def test_quality_stages_have_explicit_upload_progress(
        self, query_set, update_state, split_serializer
    ):
        from knowledge.task.split_preview import split_document_preview_task

        input_file = SimpleNamespace(
            id="file-1", file_name="one.pdf", get_bytes=lambda: b"one"
        )
        filtered = MagicMock()
        filtered.__iter__.return_value = [input_file]
        query_set.return_value.filter.return_value = filtered

        def parse(_parse_data):
            callback = split_serializer.call_args.kwargs["context"]["progress_callback"]
            callback("splitting", 1, 1, "splitting")
            callback("quality_cleaning", 0, 0, "cleaning")
            callback("quality_analyzing", 0, 0, "analyzing")
            callback("quality_optimizing", 1, 2, "optimizing")
            callback("quality_validating", 2, 2, "validating")
            return []

        split_serializer.return_value.parse.side_effect = parse

        split_document_preview_task.run(
            "task-1",
            "user-1",
            "workspace-1",
            "knowledge-1",
            ["file-1"],
            {"split_strategy": "llm_text", "quality_optimize": True},
        )

        progress_by_message = {
            call.kwargs.get("message"): call.kwargs.get("progress")
            for call in update_state.call_args_list
        }
        self.assertLess(progress_by_message["splitting"], progress_by_message["cleaning"])
        self.assertLess(progress_by_message["analyzing"], progress_by_message["optimizing"])
        self.assertLess(progress_by_message["optimizing"], progress_by_message["validating"])
