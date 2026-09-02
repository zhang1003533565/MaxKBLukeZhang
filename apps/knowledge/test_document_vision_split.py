import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from common.exception.app_exception import AppApiException
from knowledge.serializers.document import DocumentSerializers, FileBufferHandle


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

    def test_qa_split_strategy_requires_model_and_preserves_questions(self):
        with self.assertRaises(AppApiException):
            DocumentSerializers.Split._validate_model_selection("qa")
        DocumentSerializers.Split._validate_model_selection("qa", model_id="qa-model")
        DocumentSerializers.Split._validate_model_selection("qa", qa_parse_mode="rule")
        with self.assertRaises(AppApiException):
            DocumentSerializers.Split._validate_model_selection(
                "qa", qa_parse_mode="rule", quality_optimize=True
            )
        with self.assertRaises(AppApiException):
            DocumentSerializers.Split._normalize_qa_parse_mode("unknown")

        result = self.serializer._normalize_qa_split_result(
            {
                "name": "qa.txt",
                "paragraphs": [
                    {
                        "title": "什么情况不能参加考试？",
                        "content": "未按规定参加课程学习和考核的，不得参加考试。",
                        "problem_list": [{"content": "期末考核"}],
                    }
                ],
            },
            "qa.txt",
        )

        problems = [item["content"] for item in result[0]["content"][0]["problem_list"]]
        self.assertIn("什么情况不能参加考试？", problems)
        self.assertIn("期末考核", problems)
        self.assertTrue(any("考核" in problem for problem in problems))
        self.assertGreaterEqual(
            sum(self.serializer._is_probable_question(problem) for problem in problems),
            5,
        )
        problem_kinds = {
            item["content"]: item.get("kind")
            for item in result[0]["content"][0]["problem_list"]
        }
        self.assertEqual(problem_kinds["什么情况不能参加考试？"], "question")
        self.assertEqual(problem_kinds["期末考核"], "keyword")

    def test_qa_auto_mode_uses_rule_result_without_model(self):
        file = SimpleUploadedFile(
            "qa.txt",
            "问：课程冲突怎么办？\n答：应在规定时间内办理退课或改选手续。".encode(),
        )
        self.serializer._get_model = Mock()

        result = self.serializer._build_qa_split_result(
            file, FileBufferHandle().get_buffer, "auto", None, 500
        )

        self.assertEqual(result[0]["content"][0]["title"], "课程冲突怎么办？")
        self.assertIn("退课或改选手续", result[0]["content"][0]["content"])
        self.serializer._get_model.assert_not_called()

    def test_qa_rule_mode_rejects_non_qa_source(self):
        file = SimpleUploadedFile(
            "plain.txt",
            "学生应按时参加课程学习和考核，特殊情况按学校规定办理。".encode(),
        )

        with self.assertRaises(AppApiException):
            self.serializer._build_qa_split_result(
                file, lambda f: f.read(), "rule", None, 500
            )

    def test_qa_auto_mode_uses_llm_for_regular_document(self):
        expected = [
            {
                "name": "manual.docx",
                "content": [
                    {
                        "title": "什么情况不能参加考试？",
                        "content": "未按规定参加课程学习和考核的，不得参加考试。",
                        "problem_list": [{"content": "期末考核"}],
                    }
                ],
            }
        ]
        self.serializer._parse_qa_rule_split_file = Mock(
            return_value=[{"name": "manual.docx", "content": []}]
        )
        self.serializer._parse_regular_source_file = Mock(
            return_value=[
                {
                    "name": "manual.docx",
                    "content": [
                        {
                            "title": "考试管理",
                            "content": "学生应按规定参加课程学习和考核。",
                        }
                    ],
                }
            ]
        )
        self.serializer._generate_qa_split_result = Mock(return_value=expected)
        file = SimpleUploadedFile("manual.docx", b"docx")

        result = self.serializer._build_qa_split_result(
            file, lambda f: f.read(), "auto", "model-1", 500
        )

        self.assertEqual(result, expected)
        self.serializer._parse_qa_rule_split_file.assert_called_once()
        self.serializer._parse_regular_source_file.assert_called_once()
        self.serializer._generate_qa_split_result.assert_called_once()

    def test_qa_problem_list_keeps_keywords_when_question_variants_are_many(self):
        problem_list = [
            {"content": f"学生应当履行哪些义务{i}？"} for i in range(8)
        ]

        result = self.serializer._normalize_qa_problem_list(
            "学生应当履行哪些义务？",
            problem_list,
            ["学生义务", "学术道德", "遵纪守法"],
        )

        questions = [item for item in result if item.get("kind") == "question"]
        keywords = [item["content"] for item in result if item.get("kind") == "keyword"]
        self.assertLessEqual(len(questions), self.serializer.QA_QUESTION_LIST_LIMIT)
        self.assertLessEqual(len(keywords), self.serializer.QA_KEYWORD_LIST_LIMIT)
        self.assertIn("学生义务", keywords)
        self.assertIn("学术道德", keywords)
        self.assertIn("遵纪守法", keywords)

    def test_qa_problem_list_dedupes_exact_duplicate_questions(self):
        result = self.serializer._normalize_qa_problem_list(
            "\u4ec0\u4e48\u60c5\u51b5\u4e0d\u80fd\u53c2\u52a0\u8003\u8bd5\uff1f",
            [
                {"content": "\u4ec0\u4e48\u60c5\u51b5\u4e0d\u80fd\u53c2\u52a0\u8003\u8bd5\uff1f"},
                {"content": "\u4ec0\u4e48\u60c5\u51b5\u4e0d\u80fd\u53c2\u52a0\u8003\u8bd5\uff1f"},
                {"content": "\u4ec0\u4e48\u60c5\u51b5\u4e0d\u80fd\u53c2\u52a0\u8003\u8bd5\uff1f"},
            ],
            ["\u671f\u672b\u8003\u6838", "\u671f\u672b\u8003\u6838", "\u671f\u672b\u8003\u6838"],
            content="\u672a\u6309\u89c4\u5b9a\u53c2\u52a0\u8bfe\u7a0b\u5b66\u4e60\u548c\u8003\u6838\u7684\uff0c\u4e0d\u5f97\u53c2\u52a0\u8003\u8bd5\u3002",
        )

        questions = [item["content"] for item in result if item.get("kind") == "question"]
        keywords = [item["content"] for item in result if item.get("kind") == "keyword"]
        self.assertEqual(questions.count("\u4ec0\u4e48\u60c5\u51b5\u4e0d\u80fd\u53c2\u52a0\u8003\u8bd5\uff1f"), 1)
        self.assertEqual(keywords.count("\u671f\u672b\u8003\u6838"), 1)
        self.assertLessEqual(len(questions), self.serializer.QA_QUESTION_LIST_LIMIT)

    def test_qa_question_dedupe_removes_semantically_similar_variants(self):
        embedding_model = Mock()
        embedding_model.embed_documents.return_value = [
            [1.0, 0.0],
            [0.999, 0.01],
            [0.0, 1.0],
        ]
        self.serializer._qa_embedding_model = embedding_model

        result = self.serializer._dedupe_qa_question_values(
            [
                "什么情况不能参加考试？",
                "哪些情况不能参加考试？",
                "学生有哪些基本权利？",
            ],
            self.serializer.QA_QUESTION_LIST_LIMIT,
        )

        self.assertEqual(
            result,
            ["什么情况不能参加考试？", "学生有哪些基本权利？"],
        )
        embedding_model.embed_documents.assert_called_once()

    def test_qa_question_dedupe_splits_embedding_requests_within_provider_limit(self):
        embedding_model = Mock()
        embedding_offset = 0

        def embed_documents(values):
            nonlocal embedding_offset
            start = embedding_offset
            embedding_offset += len(values)
            return [
                [float(index == start + position) for index in range(26)]
                for position, _ in enumerate(values)
            ]

        embedding_model.embed_documents.side_effect = embed_documents
        self.serializer._qa_embedding_model = embedding_model

        questions = [f"学生管理规定第{index}项要求是什么？" for index in range(26)]
        result = self.serializer._dedupe_qa_question_values(
            questions, 26
        )

        self.assertEqual(len(result), 26)
        self.assertEqual(
            [len(call.args[0]) for call in embedding_model.embed_documents.call_args_list],
            [20, 6],
        )

    def test_qa_question_dedupe_removes_polite_wrappers(self):
        result = self.serializer._dedupe_qa_question_values(
            [
                "请问学生有哪些权利？",
                "请问一下学生有哪些权利？",
                "想了解一下，学生有哪些权利呢？",
                "学生有哪些权利？",
                "麻烦您，学生有哪些权利吗？",
            ],
            self.serializer.QA_QUESTION_LIST_LIMIT,
        )

        self.assertEqual(result, ["请问学生有哪些权利？"])

    def test_qa_split_generates_questions_keywords_and_variants_with_model(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "qa_pairs": [
                        {
                            "question": "什么情况不能参加考试？",
                            "answer": "未按规定参加课程学习和考核的，不得参加考试。",
                            "keywords": ["期末考核", "考试限制"],
                            "related_questions": ["哪些情况不允许参加考试？"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        result = self.serializer._generate_qa_with_model(
            "手册.docx",
            [{"title": "考试管理", "content": "学生应按规定参加课程学习和考核。"}],
            "qa-model",
            500,
        )

        self.assertEqual(result[0]["title"], "什么情况不能参加考试？")
        self.assertIn("不得参加考试", result[0]["content"])
        problems = [item["content"] for item in result[0]["problem_list"]]
        self.assertIn("期末考核", problems)
        self.assertIn("哪些情况不允许参加考试？", problems)
        problem_kinds = {item["content"]: item.get("kind") for item in result[0]["problem_list"]}
        self.assertEqual(problem_kinds["哪些情况不允许参加考试？"], "question")
        self.assertEqual(problem_kinds["期末考核"], "keyword")
        self.assertIn("哪些情况不允许参加考试？", result[0]["related_questions"])
        self.assertTrue({"期末考核", "考试限制"}.issubset(set(result[0]["keywords"])))
        model.invoke.assert_called_once()

    def test_qa_split_adds_fallback_keywords_when_model_omits_keywords(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "qa_pairs": [
                        {
                            "question": "学生应当履行哪些义务？",
                            "answer": "学生应当履行遵纪守法、维护学校声誉、完成规定学业等义务。",
                            "keywords": [],
                            "related_questions": ["学生有哪些义务？"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        result = self.serializer._generate_qa_with_model(
            "手册.docx",
            [{"title": "学生义务", "content": "学生应当履行遵纪守法等义务。"}],
            "qa-model",
            500,
        )

        keywords = [
            item["content"]
            for item in result[0]["problem_list"]
            if item.get("kind") == "keyword"
        ]
        self.assertTrue({"遵纪守法", "维护学校声誉", "学生义务"} & set(keywords))
        self.assertTrue(result[0]["keywords"])

    def test_qa_split_rejects_section_titles_as_model_questions(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "qa_pairs": [
                        {
                            "question": "第一章 总则",
                            "answer": "本规定适用于全日制研究生、本科、专科生。",
                            "keywords": ["适用范围"],
                            "related_questions": [],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        with self.assertRaises(AppApiException):
            self.serializer._generate_qa_with_model(
                "手册.docx",
                [{"title": "第一章 总则", "content": "本规定适用于全日制研究生、本科、专科生。"}],
                "qa-model",
                500,
            )

        self.assertEqual(model.invoke.call_count, 2)

    def test_qa_split_can_parse_text_extracted_by_regular_splitter(self):
        file = SimpleUploadedFile("qa.docx", b"docx")
        split_handle = Mock()
        split_handle.support.return_value = True
        split_handle.handle.return_value = {
            "name": "qa.docx",
            "content": [
                {
                    "title": "",
                    "content": "问：课程冲突怎么办？\n答：应在规定时间内办理退课或改选手续。",
                }
            ],
        }

        with patch("knowledge.serializers.document.split_handles", [split_handle]):
            result = self.serializer._parse_qa_from_regular_split_file(file, lambda f: f.read())

        self.assertEqual(result[0]["content"][0]["title"], "课程冲突怎么办？")
        self.assertIn("退课或改选手续", result[0]["content"][0]["content"])

    def test_qa_quality_optimization_keeps_qa_shape_and_expands_problem_list(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "qa_pairs": [
                        {
                            "question": "哪些情况不能参加考试？",
                            "answer": "一学期中有规定情形之一的，均不得参加该课程期末考核。",
                            "keywords": ["考试限制", "期末考核"],
                            "related_questions": ["什么情况不能参加考试？"],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_qa_pairs(
            "qa.docx",
            [
                {
                    "title": "啥情况不能考？",
                    "content": "一学期中有规定情形之一的，均不得参加该课程期末考核。",
                    "problem_list": [{"content": "不能参加考试"}],
                }
            ],
            True,
            "model-1",
            500,
        )

        self.assertEqual(paragraphs[0]["title"], "哪些情况不能参加考试？")
        self.assertIn("期末考核", paragraphs[0]["content"])
        problems = [item["content"] for item in paragraphs[0]["problem_list"]]
        self.assertIn("考试限制", problems)
        self.assertIn("什么情况不能参加考试？", problems)
        self.assertGreaterEqual(
            sum(self.serializer._is_probable_question(problem) for problem in problems),
            5,
        )
        self.assertEqual(report["fallback_batches"], 0)
        prompt = model.invoke.call_args.args[0][0].content
        self.assertIn("不能改成普通段落分段", prompt)
        self.assertIn('"qa_pairs"', prompt)
        self.assertIn('"keywords"', prompt)
        self.assertIn("期末考核", prompt)

    def test_qa_quality_optimization_rejects_plain_paragraph_shape(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "paragraphs": [
                        {
                            "title": "普通段落标题",
                            "content": "这不应该作为 QA 优化结果通过。",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_qa_pairs(
            "qa.docx",
            [
                {
                    "title": "什么情况不能参加考试？",
                    "content": "未按规定参加课程学习和考核的，不得参加考试。",
                    "problem_list": [{"content": "期末考核"}],
                }
            ],
            True,
            "model-1",
            500,
        )

        self.assertEqual(paragraphs[0]["title"], "什么情况不能参加考试？")
        self.assertNotEqual(paragraphs[0]["title"], "普通段落标题")
        problems = [item["content"] for item in paragraphs[0]["problem_list"]]
        self.assertIn("期末考核", problems)
        self.assertEqual(report["fallback_batches"], 1)
        self.assertEqual(model.invoke.call_count, 2)

    def test_qa_quality_optimization_rejects_section_title_question(self):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "qa_pairs": [
                        {
                            "question": "第二章 学生权利",
                            "answer": "学生依法享有参加教学活动等权利。",
                            "keywords": ["学生权利"],
                            "related_questions": [],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_qa_pairs(
            "qa.docx",
            [
                {
                    "title": "学生享有哪些权利？",
                    "content": "学生依法享有参加教学活动等权利。",
                    "problem_list": [{"content": "学生权利"}],
                }
            ],
            True,
            "model-1",
            500,
        )

        self.assertEqual(paragraphs[0]["title"], "学生享有哪些权利？")
        self.assertEqual(report["fallback_batches"], 1)
        self.assertEqual(model.invoke.call_count, 2)

    def test_quality_optimization_disabled_only_runs_rule_cleanup(self):
        self.serializer._get_model = Mock()

        paragraphs, report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [{"title": "标题", "content": "正文\n46\nwww.themegallery.com"}],
            False,
            None,
        )

        self.assertEqual(paragraphs[0]["content"], "正文\n46")
        self.assertEqual(report["removed_noise"], 1)
        self.serializer._get_model.assert_not_called()

    def test_quality_optimization_rewrites_generic_title_with_valid_model_result(self):
        content = "可变参数会把后续参数收集为元组。" * 6
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {"paragraphs": [{"title": "Python可变参数", "content": content}]}
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [{"title": "Python实例（二）", "content": content}],
            True,
            "model-1",
        )

        self.assertEqual(paragraphs[0]["title"], "Python可变参数")
        self.assertEqual(report["titles_rewritten"], 1)
        self.assertEqual(report["fallback_batches"], 0)
        model.invoke.assert_called_once()

    def test_quality_optimization_preserves_qa_problem_list(self):
        content = "未按规定参加课程学习和考核的，不得参加考试，课程成绩以零分计。" * 5
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {"paragraphs": [{"title": "不能参加考试情形", "content": content}]},
                ensure_ascii=False,
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_paragraphs(
            "qa.docx",
            [
                {
                    "title": "示例",
                    "content": content,
                    "problem_list": [
                        {"content": "什么情况不能参加考试？"},
                        {"content": "期末考核"},
                    ],
                }
            ],
            True,
            "model-1",
        )

        problems = [item["content"] for item in paragraphs[0]["problem_list"]]
        self.assertEqual(paragraphs[0]["title"], "不能参加考试情形")
        self.assertIn("什么情况不能参加考试？", problems)
        self.assertIn("期末考核", problems)
        self.assertEqual(report["fallback_batches"], 0)

    def test_quality_optimization_skips_normal_paragraph(self):
        content = "这是一个主题完整且长度合适的知识段落。" * 12
        self.serializer._get_model = Mock()

        paragraphs, report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [{"title": "Python模块导入规则", "content": content}],
            True,
            "model-1",
        )

        self.assertEqual(paragraphs[0]["content"], content)
        self.assertEqual(report["total_batches"], 0)
        self.serializer._get_model.assert_not_called()

    def test_quality_optimization_batches_adjacent_duplicate_titles(self):
        first = "第一种帮助查询方式说明。" * 12
        second = "第二种帮助查询方式说明。" * 12
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "paragraphs": [
                        {"title": "使用help查询内置函数", "content": first},
                        {"title": "退出交互式帮助系统", "content": second},
                    ]
                }
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [
                {"id": "p1", "title": "在线帮助和相关资源", "content": first},
                {"id": "p2", "title": "在线帮助和相关资源", "content": second},
            ],
            True,
            "model-1",
        )

        self.assertEqual(report["total_batches"], 1)
        self.assertEqual(model.invoke.call_count, 1)
        self.assertEqual(paragraphs[0]["source_paragraph_ids"], ["p1"])
        self.assertEqual(paragraphs[1]["source_paragraph_ids"], ["p2"])

    def test_quality_optimization_retries_invalid_json_and_merges_adjacent_short_paragraphs(self):
        first = "第一段内容" * 14
        second = "第二段内容" * 14
        model = Mock()
        model.invoke.side_effect = [
            SimpleNamespace(content="not-json"),
            SimpleNamespace(
                content=json.dumps(
                    {"paragraphs": [{"title": "合并后的具体主题", "content": first + second}]}
                )
            ),
        ]
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [
                {"id": "p1", "title": "短段一", "content": first},
                {"id": "p2", "title": "短段二", "content": second},
            ],
            True,
            "model-1",
        )

        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0]["source_paragraph_ids"], ["p1", "p2"])
        self.assertEqual(report["merged_paragraphs"], 1)
        self.assertEqual(model.invoke.call_count, 2)

    def test_quality_optimization_keeps_provenance_separate_without_merge(self):
        first = "第一段内容" * 14
        second = "第二段内容" * 14
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "paragraphs": [
                        {"title": "第一个具体主题", "content": first},
                        {"title": "第二个具体主题", "content": second},
                    ]
                }
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, _report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [
                {"id": "p1", "title": "短段一", "content": first},
                {"id": "p2", "title": "短段二", "content": second},
            ],
            True,
            "model-1",
        )

        self.assertEqual(paragraphs[0]["source_paragraph_ids"], ["p1"])
        self.assertEqual(paragraphs[1]["source_paragraph_ids"], ["p2"])

    def test_quality_optimization_maps_provenance_by_content_span(self):
        first = "第一段内容" * 20
        second = "第二段内容" * 40
        boundary = len(second) // 2
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "paragraphs": [
                        {
                            "title": "跨边界的第一个主题",
                            "content": first + second[:boundary],
                        },
                        {
                            "title": "第二个主题的剩余内容",
                            "content": second[boundary:],
                        },
                    ]
                }
            )
        )
        self.serializer._get_model = Mock(return_value=model)

        paragraphs, _report = self.serializer._quality_optimize_paragraphs(
            "chapter.pdf",
            [
                {"id": "p1", "title": "相同标题", "content": first},
                {"id": "p2", "title": "相同标题", "content": second},
            ],
            True,
            "model-1",
        )

        self.assertEqual(paragraphs[0]["source_paragraph_ids"], ["p1", "p2"])
        self.assertEqual(paragraphs[1]["source_paragraph_ids"], ["p2"])

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
