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
            "主题\n主题\n--------\n图片说明：架构图\n图片说明：架构图\n正文",
            "主题",
        )

        self.assertEqual(cleaned, "图片说明：架构图\n正文")
        self.assertEqual(report["removed_noise"], 4)

    def test_clean_content_removes_repeated_paragraph_title_and_tracks_report(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        cleaned, report = clean_paragraph_content(
            "### 在线帮助和相关资源\n在线帮助和相关资源\n正文",
            "在线帮助和相关资源",
        )

        self.assertEqual(cleaned, "正文")
        self.assertEqual(report["removed_duplicates"], 2)

    def test_clean_content_uses_page_context_for_standalone_numbers(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        cleaned, report = clean_paragraph_content(
            "有效数字\n46\n正文\n38\n### 第 39 页\n下一页正文"
        )

        self.assertIn("46", cleaned)
        self.assertIn("\n38\n", f"\n{cleaned}\n")
        self.assertNotIn("第 39 页", cleaned)
        self.assertEqual(report["removed_page_numbers"], 1)
        self.assertEqual(report["preserved_numeric_lines"], 2)

    def test_clean_content_does_not_treat_fact_or_code_page_text_as_page_context(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        cleaned, report = clean_paragraph_content(
            "状态码\n404\n### 第 39 页\n```text\n第 405 页\n```\n405"
        )

        self.assertIn("404", cleaned)
        self.assertIn("405", cleaned)
        self.assertEqual(report["removed_page_numbers"], 1)

    def test_clean_content_joins_plain_chinese_pdf_line_breaks_only(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        source = (
            "Python功能全\n面、易学易用。\n"
            "图片说明：这是一张\n说明图\n"
            "https://example.com/a\nb\n"
            "```python\nvalue = 'a\nb'\n```"
        )
        cleaned, report = clean_paragraph_content(source, join_pdf_lines=True)

        self.assertIn("Python功能全面、易学易用。", cleaned)
        self.assertIn("图片说明：这是一张\n说明图", cleaned)
        self.assertIn("https://example.com/a\nb", cleaned)
        self.assertIn("value = 'a\nb'", cleaned)
        self.assertEqual(report["joined_pdf_lines"], 1)

    def test_clean_content_does_not_join_non_pdf_or_duplicate_fact_lines(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        source = "库存 0\n库存 0\n姓名\n张三"
        cleaned, report = clean_paragraph_content(source)

        self.assertEqual(cleaned, source)
        self.assertEqual(report["removed_duplicates"], 0)
        self.assertEqual(report["joined_pdf_lines"], 0)

    def test_pdf_line_join_protects_common_code_and_query_prefixes(self):
        from knowledge.quality.document_quality import clean_paragraph_content

        source = "if 条件\n执行函数\nreturn 中文值\n下一语句\nSELECT 用户名\nFROM 用户表"
        cleaned, report = clean_paragraph_content(source, join_pdf_lines=True)

        self.assertEqual(cleaned, source)
        self.assertEqual(report["joined_pdf_lines"], 0)

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

    def test_analyze_paragraph_detects_multiple_markdown_headings(self):
        from knowledge.quality.document_quality import analyze_paragraph

        metrics = analyze_paragraph(
            {
                "title": "模块导入",
                "content": "### import方式\n正文内容\n### from方式\n更多正文",
            }
        )

        self.assertTrue(metrics["multiple_headings"])

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
        self.assertIn(reason, {"content_changed", "protected_items_changed"})

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
        self.assertEqual(report["preserved_numeric_lines"], 1)
