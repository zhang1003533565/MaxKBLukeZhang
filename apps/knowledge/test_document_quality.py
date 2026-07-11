from django.test import SimpleTestCase


class DocumentQualityTest(SimpleTestCase):
    def test_clean_content_removes_noise_and_is_idempotent(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        source = (
            "标题\n 要点一\n46\n第 15 页\nwww.themegallery.com\n\n\n\n"
            ">>> print('ok')\nhttps://python.org\n"
            "![image](./oss/file/11111111-1111-1111-1111-111111111111)"
        )

        cleaned, report = clean_paragraph_content(source)
        cleaned_again, _ = clean_paragraph_content(cleaned)

        self.assertNotIn("www.themegallery.com", cleaned)
        self.assertIn("\n46\n", f"\n{cleaned}\n")
        self.assertNotIn("第 15 页", cleaned)
        self.assertIn("- 要点一", cleaned)
        self.assertIn(">>> print('ok')", cleaned)
        self.assertIn("https://python.org", cleaned)
        self.assertIn("![image]", cleaned)
        self.assertEqual(cleaned_again, cleaned)
        self.assertEqual(report["removed_noise"], 2)

    def test_clean_content_preserves_fenced_code_exactly(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        fenced = "```text\n46\n raw output\n第 15 页\nwww.themegallery.com\n```"
        cleaned, report = clean_paragraph_content(f"正文\n{fenced}")

        self.assertIn(fenced, cleaned)
        self.assertEqual(report["removed_noise"], 0)

    def test_clean_content_removes_decorative_and_adjacent_duplicate_lines(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        cleaned, report = clean_paragraph_content(
            "主题\n主题\n--------\n图片说明：架构图\n图片说明：架构图\n正文"
        )

        self.assertEqual(cleaned, "主题\n图片说明：架构图\n正文")
        self.assertEqual(report["removed_noise"], 3)

    def test_image_ids_are_hidden_from_prompt_and_restored(self):
        from knowledge.quality.document_quality import (
            build_quality_prompt,
            replace_image_ids_with_aliases,
            restore_image_aliases,
        )

        image_id = "11111111-1111-1111-1111-111111111111"
        source = [{"title": "图", "content": f"![image](./oss/file/{image_id})"}]
        aliased, mapping = replace_image_ids_with_aliases(source)

        self.assertNotIn(image_id, build_quality_prompt("doc", aliased))
        self.assertIn("img_0", build_quality_prompt("doc", aliased))
        self.assertEqual(restore_image_aliases(aliased, mapping), source)

    def test_analyze_paragraph_flags_length_title_and_fallback_images(self):
        from knowledge.quality.document_quality import analyze_paragraph

        paragraph = {
            "title": "Python实例（一）",
            "content": (
                "图片说明：视觉模型未能识别，已保留原始插图\n"
                "![image](./oss/file/11111111-1111-1111-1111-111111111111)"
            ),
        }

        metrics = analyze_paragraph(paragraph)

        self.assertTrue(metrics["generic_title"])
        self.assertTrue(metrics["too_short"])
        self.assertEqual(metrics["image_count"], 1)
        self.assertEqual(metrics["fallback_image_count"], 1)

    def test_protected_items_detect_changes(self):
        from knowledge.quality.document_quality import validate_optimized_batch

        source = [{"title": "安装", "content": "pip install pandas\nhttps://pypi.org\n![image](./oss/file/a)"}]
        valid = [{"title": "Pandas安装", "content": source[0]["content"]}]
        invalid = [{"title": "Pandas安装", "content": "pip install numpy\nhttps://pypi.org"}]

        self.assertEqual(validate_optimized_batch(source, valid), (True, ""))
        passed, reason = validate_optimized_batch(source, invalid)
        self.assertFalse(passed)
        self.assertEqual(reason, "protected_items_changed")

    def test_quality_gate_rejects_generic_title_and_oversized_paragraph(self):
        from knowledge.quality.document_quality import validate_optimized_batch

        source = [{"title": "主题", "content": "知识内容" * 300}]
        result = [{"title": "示例", "content": "知识内容" * 300}]

        passed, reason = validate_optimized_batch(source, result)

        self.assertFalse(passed)
        self.assertEqual(reason, "generic_title")

    def test_quality_gate_rejects_same_length_factual_rewrite(self):
        from knowledge.quality.document_quality import validate_optimized_batch

        source = [{"title": "版本信息", "content": "Python 2 于 2020 年停止维护。" * 5}]
        result = [{"title": "版本信息", "content": "Python 2 于 2030 年停止维护。" * 5}]

        passed, reason = validate_optimized_batch(source, result)

        self.assertFalse(passed)
        self.assertEqual(reason, "content_changed")

    def test_quality_gate_preserves_semantic_whitespace(self):
        from knowledge.quality.document_quality import validate_optimized_batch

        source = [{"title": "返回值", "content": 'return "a b"' * 8}]
        result = [{"title": "返回值", "content": 'return "ab" ' * 8}]

        passed, reason = validate_optimized_batch(source, result)

        self.assertFalse(passed)
        self.assertEqual(reason, "content_changed")

    def test_clean_paragraphs_returns_aggregate_report(self):
        from knowledge.quality.document_quality import clean_paragraphs

        cleaned, report = clean_paragraphs(
            [
                {"title": "标题", "content": "正文\n1\nwww.themegallery.com"},
                {"title": "Python实例（二）", "content": "短内容"},
            ]
        )

        self.assertEqual(len(cleaned), 2)
        self.assertEqual(report["removed_noise"], 1)
        self.assertEqual(report["generic_titles"], 1)
        self.assertEqual(report["paragraphs_before"], 2)
        self.assertEqual(report["paragraphs_after"], 2)
