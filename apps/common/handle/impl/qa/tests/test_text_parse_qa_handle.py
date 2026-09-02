from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from common.handle.impl.qa.text_parse_qa_handle import TextParseQAHandle


class TextParseQAHandleTest(SimpleTestCase):
    def test_parse_plain_text_qa_pairs_with_keywords_and_variants(self):
        content = """问：什么情况不能参加考试？
关键词：期末考核、课程考核、重修
问法：哪些情况不得参加考核？, 什么条件不能参加课程考核？
答：未在规定时间办理退课手续，或不参加课程学习和考核的，课程成绩以零分计。

问：课程冲突怎么办？
答：应当在规定时间内办理退课或改选手续。
"""
        file = SimpleUploadedFile("qa.txt", content.encode("utf-8"))
        handle = TextParseQAHandle()
        result = handle.handle(file, lambda f: f.read(), lambda images: None)

        paragraphs = result["paragraphs"]
        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(paragraphs[0]["title"], "什么情况不能参加考试？")
        self.assertIn("课程成绩以零分计", paragraphs[0]["content"])

        problems = [item["content"] for item in paragraphs[0]["problem_list"]]
        self.assertIn("什么情况不能参加考试？", problems)
        self.assertIn("期末考核", problems)
        self.assertIn("哪些情况不得参加考核？", problems)
        self.assertIn("什么条件不能参加课程考核？", problems)
        self.assertTrue(any("期末" in problem for problem in problems))

    def test_supports_english_qa_prefixes(self):
        content = """Q: How to reset password?
A: Use the account settings page.
"""
        file = SimpleUploadedFile("qa.md", content.encode("utf-8"))
        handle = TextParseQAHandle()
        result = handle.handle(file, lambda f: f.read(), lambda images: None)

        self.assertEqual(result["paragraphs"][0]["title"], "How to reset password?")
        self.assertEqual(result["paragraphs"][0]["content"], "Use the account settings page.")
