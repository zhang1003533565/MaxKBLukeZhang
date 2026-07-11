from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class DocumentQualityTaskTest(SimpleTestCase):
    @patch("common.event.listener_manage.RedisLock")
    def test_strict_embedding_raises_when_document_lock_is_unavailable(self, redis_lock):
        from common.event.listener_manage import ListenerManagement

        redis_lock.return_value.try_lock.return_value = False

        with self.assertRaises(RuntimeError):
            ListenerManagement.embedding_by_document(
                "document-1", MagicMock(), raise_on_error=True
            )

    @patch("knowledge.task.document_quality.update_split_task_state")
    @patch("knowledge.task.document_quality.QuerySet")
    @patch("knowledge.serializers.document.DocumentSerializers.Split")
    def test_quality_task_stores_before_after_and_report(
        self, split_serializer, query_set, update_state
    ):
        from knowledge.task.document_quality import optimize_document_quality_task

        document_query = MagicMock()
        paragraph_query = MagicMock()
        query_set.side_effect = [document_query, paragraph_query]
        document_query.filter.return_value.first.return_value = SimpleNamespace(
            id="document-1", name="chapter.pdf"
        )
        paragraph_query.filter.return_value.order_by.return_value.values.return_value = [
            {
                "id": "paragraph-1",
                "title": "Python实例（一）",
                "content": "正文",
                "position": 1,
                "is_active": True,
                "update_time": "time-1",
            }
        ]
        split_serializer.return_value._quality_optimize_paragraphs.return_value = (
            [{"title": "具体标题", "content": "正文", "is_active": True}],
            {"titles_rewritten": 1},
        )

        optimize_document_quality_task.run(
            "task-1", "user-1", "workspace-1", "knowledge-1", "document-1", "model-1"
        )

        completed = next(
            call for call in update_state.call_args_list if call.kwargs.get("status") == "completed"
        )
        self.assertEqual(completed.kwargs["result"]["after"][0]["title"], "具体标题")
        self.assertEqual(completed.kwargs["result"]["report"]["titles_rewritten"], 1)
        self.assertEqual(completed.kwargs["result"]["snapshot"][0]["id"], "paragraph-1")
