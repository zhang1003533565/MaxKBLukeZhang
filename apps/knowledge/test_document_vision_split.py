import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from PIL import Image

from common.exception.app_exception import AppApiException
from knowledge.serializers.document import DocumentSerializers


def image_bytes(mode="RGB", color="white", size=(64, 64), pattern=False):
    image = Image.new(mode, size, color=color)
    if pattern:
        pixels = image.load()
        for x in range(size[0]):
            for y in range(size[1]):
                pixels[x, y] = (x * 3 % 255, y * 5 % 255, (x + y) * 7 % 255)
    output = BytesIO()
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


class DocumentVisionSplitTest(SimpleTestCase):
    def setUp(self):
        self.serializer = DocumentSerializers.Split(data={})

    def test_image_candidate_filter_rejects_artifacts_and_keeps_diagram(self):
        self.assertFalse(self.serializer._is_meaningful_image_candidate(image_bytes(size=(1, 1))))
        self.assertFalse(
            self.serializer._is_meaningful_image_candidate(
                image_bytes(mode="RGBA", color=(255, 255, 255, 0))
            )
        )
        self.assertFalse(self.serializer._is_meaningful_image_candidate(image_bytes(color="white")))
        self.assertTrue(self.serializer._is_meaningful_image_candidate(image_bytes(pattern=True)))

    def test_split_preview_file_meta_is_only_added_for_async_task_context(self):
        async_serializer = DocumentSerializers.Split(
            data={}, context={"split_preview_task_id": "task-1"}
        )

        self.assertEqual(
            async_serializer._split_preview_file_meta(),
            {"split_preview_task_id": "task-1"},
        )
        self.assertEqual(self.serializer._split_preview_file_meta(), {})

    @patch("knowledge.serializers.document.QuerySet")
    def test_split_save_image_marks_async_preview_file_for_cleanup(self, query_set):
        serializer = DocumentSerializers.Split(
            context={"split_preview_task_id": "task-1"}
        )
        serializer._data = {"knowledge_id": "knowledge-1"}
        serializer._request_image_ids = set()
        query_set.return_value.filter.return_value.values.return_value = []
        image_file = SimpleNamespace(
            id="image-1",
            meta={"content": b"image"},
            source_type=None,
            source_id=None,
            save=Mock(),
        )

        serializer.save_image([image_file])

        self.assertEqual(image_file.meta["split_preview_task_id"], "task-1")
        self.assertEqual(image_file.meta["knowledge_id"], "knowledge-1")
        image_file.save.assert_called_once_with(b"image")
        self.assertEqual(serializer._request_image_ids, {"image-1"})

    def test_vision_split_requires_both_models_and_text_split_keeps_legacy_model(self):
        with self.assertRaises(AppApiException):
            self.serializer._validate_model_selection("llm_vision", vision_model_id="vision")
        with self.assertRaises(AppApiException):
            self.serializer._validate_model_selection("llm_vision", llm_model_id="llm")
        self.serializer._validate_model_selection(
            "llm_vision", vision_model_id="vision", llm_model_id="llm"
        )
        self.serializer._validate_model_selection("llm_text", model_id="legacy-llm")

    def test_validate_vision_payload_requires_exact_ids_and_descriptions(self):
        payload = {
            "images": [
                {"id": "a", "keep": True, "description": "流程图", "reason": "有知识内容"},
                {"id": "b", "keep": False, "description": "", "reason": "背景"},
            ]
        }

        result = self.serializer._normalize_vision_images(payload, ["a", "b"])

        self.assertEqual(result["a"]["description"], "流程图")
        self.assertFalse(result["b"]["keep"])

    def test_validate_vision_payload_rejects_missing_unknown_and_duplicate_ids(self):
        invalid_payloads = [
            {"images": [{"id": "a", "keep": False, "description": "", "reason": "背景"}]},
            {
                "images": [
                    {"id": "a", "keep": False, "description": "", "reason": "背景"},
                    {"id": "c", "keep": False, "description": "", "reason": "背景"},
                ]
            },
            {
                "images": [
                    {"id": "a", "keep": False, "description": "", "reason": "背景"},
                    {"id": "a", "keep": False, "description": "", "reason": "背景"},
                ]
            },
            {
                "images": [
                    {"id": "a", "keep": True, "description": "", "reason": "有内容"},
                    {"id": "b", "keep": False, "description": "", "reason": "背景"},
                ]
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=json.dumps(payload, ensure_ascii=False)):
                with self.assertRaises(AppApiException):
                    self.serializer._normalize_vision_images(payload, ["a", "b"])

    def test_validate_image_references_requires_exact_multiset(self):
        source = "说明\n![image](./oss/file/11111111-1111-1111-1111-111111111111)"
        valid = [{"title": "标题", "content": source}]
        duplicate = [{"title": "标题", "content": f"{source}\n{source}"}]

        self.serializer._validate_image_references([{"content": source}], valid)
        with self.assertRaises(AppApiException):
            self.serializer._validate_image_references([{"content": source}], duplicate)

    def test_image_description_replacement_treats_backslashes_as_text(self):
        file_id = "11111111-1111-1111-1111-111111111111"
        content = f"![image](./oss/file/{file_id})"

        result = self.serializer._replace_image_reference(
            content, file_id, r"Windows 路径 C:\temp\1"
        )

        self.assertIn(r"图片说明：Windows 路径 C:\temp\1", result)
        self.assertEqual(result.count(file_id), 1)

    @patch("knowledge.serializers.document.QuerySet")
    def test_vision_enrichment_batches_four_images_and_drops_background(self, query_set):
        image_ids = [f"11111111-1111-1111-1111-{index:012d}" for index in range(5)]
        content = "页面正文\n" + "\n".join(
            f"![image](./oss/file/{file_id})" for file_id in image_ids
        )
        image_files = [
            SimpleNamespace(
                get_bytes=lambda: image_bytes(pattern=True),
                sha256_hash=f"hash-{index}",
            )
            for index in range(5)
        ]
        self.serializer._request_image_ids = set(image_ids)
        progress_events = []
        self.serializer._context = {
            "progress_callback": lambda stage, processed, total, message: progress_events.append(
                (stage, processed, total, message)
            )
        }
        query_set.return_value.filter.return_value.first.side_effect = image_files
        vision_model = Mock()
        vision_model.invoke.side_effect = [
            SimpleNamespace(
                content=json.dumps(
                    {
                        "images": [
                            {
                                "id": f"img_{index + 1}",
                                "keep": True,
                                "description": f"说明 {index}",
                                "reason": "知识插图",
                            }
                            for index in range(4)
                        ]
                    }
                )
            ),
            SimpleNamespace(
                content=json.dumps(
                    {
                        "images": [
                            {
                                "id": "img_1",
                                "keep": False,
                                "description": "",
                                "reason": "背景",
                            }
                        ]
                    }
                )
            ),
        ]

        enriched, rejected_ids, descriptions = self.serializer._enrich_paragraphs_with_vision(
            "chapter.pdf",
            [{"title": "页面标题", "content": content, "page_number": 1}],
            vision_model,
        )

        self.assertEqual(vision_model.invoke.call_count, 2)
        self.assertIn("图片说明：说明 0", enriched[0]["content"])
        self.assertNotIn(image_ids[4], enriched[0]["content"])
        self.assertEqual(rejected_ids, {image_ids[4]})
        self.assertEqual(descriptions[image_ids[0]], "说明 0")
        self.assertIn(("filtering", 5, 5), [event[:3] for event in progress_events])
        self.assertIn(("vision", 2, 2), [event[:3] for event in progress_events])

        first_request = vision_model.invoke.call_args_list[0].args[0][0]
        request_text = "\n".join(
            item.get("text", "")
            for item in first_request.content
            if item.get("type") == "text"
        )
        self.assertIn("候选图片ID：img_1, img_2, img_3, img_4", request_text)
        self.assertNotIn(image_ids[0], request_text)

    @patch("knowledge.serializers.document.QuerySet")
    def test_vision_enrichment_retries_invalid_ids_then_uses_valid_result(self, query_set):
        file_id = "11111111-1111-1111-1111-111111111111"
        self.serializer._request_image_ids = {file_id}
        query_set.return_value.filter.return_value.first.return_value = SimpleNamespace(
            get_bytes=lambda: image_bytes(pattern=True),
            sha256_hash="hash-1",
        )
        vision_model = Mock()
        vision_model.invoke.side_effect = [
            SimpleNamespace(
                content=json.dumps(
                    {"images": [{"id": "wrong-id", "keep": False, "description": ""}]}
                )
            ),
            SimpleNamespace(
                content=json.dumps(
                    {
                        "images": [
                            {
                                "id": "img_1",
                                "keep": True,
                                "description": "有效图片说明",
                                "reason": "知识插图",
                            }
                        ]
                    }
                )
            ),
        ]

        enriched, rejected_ids, descriptions = self.serializer._enrich_paragraphs_with_vision(
            "chapter.pdf",
            [{"title": "标题", "content": f"![image](./oss/file/{file_id})"}],
            vision_model,
        )

        self.assertEqual(vision_model.invoke.call_count, 2)
        self.assertIn("图片说明：有效图片说明", enriched[0]["content"])
        self.assertEqual(rejected_ids, set())
        self.assertEqual(descriptions[file_id], "有效图片说明")

    @patch("knowledge.serializers.document.QuerySet")
    def test_vision_enrichment_keeps_original_image_when_retry_still_invalid(self, query_set):
        file_id = "11111111-1111-1111-1111-111111111111"
        image_reference = f"![image](./oss/file/{file_id})"
        self.serializer._request_image_ids = {file_id}
        query_set.return_value.filter.return_value.first.return_value = SimpleNamespace(
            get_bytes=lambda: image_bytes(pattern=True),
            sha256_hash="hash-1",
        )
        vision_model = Mock()
        vision_model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {"images": [{"id": "wrong-id", "keep": False, "description": ""}]}
            )
        )

        enriched, rejected_ids, descriptions = self.serializer._enrich_paragraphs_with_vision(
            "chapter.pdf",
            [{"title": "标题", "content": image_reference}],
            vision_model,
        )

        self.assertEqual(vision_model.invoke.call_count, 2)
        self.assertIn(image_reference, enriched[0]["content"])
        self.assertIn("图片说明：视觉模型未能识别，已保留原始插图", enriched[0]["content"])
        self.assertEqual(rejected_ids, set())
        self.assertEqual(descriptions[file_id], "视觉模型未能识别，已保留原始插图")

    @patch("knowledge.serializers.document.QuerySet")
    def test_vision_split_keeps_image_only_page_when_vision_response_stays_invalid(
        self, query_set
    ):
        file_id = "11111111-1111-1111-1111-111111111111"
        image_reference = f"![image](./oss/file/{file_id})"
        self.serializer._request_image_ids = {file_id}
        query_set.return_value.filter.return_value.first.return_value = SimpleNamespace(
            get_bytes=lambda: image_bytes(pattern=True),
            sha256_hash="hash-1",
        )
        vision_model = Mock()
        vision_model.invoke.return_value = SimpleNamespace(content="not-json")
        llm_model = Mock()

        def echo_split_content(messages):
            prompt = messages[0].content
            content = prompt.split("待切分内容：\n", 1)[1]
            return SimpleNamespace(
                content=json.dumps({"paragraphs": [{"title": "", "content": content}]})
            )

        llm_model.invoke.side_effect = echo_split_content
        self.serializer._get_model = Mock(side_effect=[vision_model, llm_model])

        result, rejected_ids = self.serializer._split_vision_content(
            "chapter.pdf", [{"title": "", "content": image_reference}], "vision", "llm", 500
        )

        self.assertEqual(vision_model.invoke.call_count, 2)
        self.assertIn(image_reference, result[0]["content"])
        self.assertIn("图片说明：视觉模型未能识别，已保留原始插图", result[0]["content"])
        self.assertEqual(rejected_ids, set())

    @patch("knowledge.serializers.document.QuerySet")
    def test_vision_enrichment_rejects_image_ids_not_created_by_upload(self, query_set):
        file_id = "11111111-1111-1111-1111-111111111111"
        self.serializer._request_image_ids = set()

        with self.assertRaises(AppApiException):
            self.serializer._enrich_paragraphs_with_vision(
                "chapter.md",
                [{"title": "标题", "content": f"![image](./oss/file/{file_id})"}],
                Mock(),
            )

        query_set.assert_not_called()
