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
                                "id": file_id,
                                "keep": True,
                                "description": f"说明 {index}",
                                "reason": "知识插图",
                            }
                            for index, file_id in enumerate(image_ids[:4])
                        ]
                    }
                )
            ),
            SimpleNamespace(
                content=json.dumps(
                    {
                        "images": [
                            {
                                "id": image_ids[4],
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
