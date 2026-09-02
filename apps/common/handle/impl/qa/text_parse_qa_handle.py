# coding=utf-8
"""
    @project: maxkb
    @file： text_parse_qa_handle.py
    @desc: Parse plain text QA pairs into paragraph records.
"""
import re
import traceback

from charset_normalizer import detect

from common.handle.base_parse_qa_handle import BaseParseQAHandle
from common.utils.logger import maxkb_logger
from common.utils.query_expansion import expand_query_variants

QUESTION_PATTERN = re.compile(
    r"^\s*(?:[-*]\s*)?(?:#{1,6}\s*)?(?:Q|q|问|问题)\s*\d*[.、:：]\s*(.+?)\s*$"
)
ANSWER_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?(?:A|a|答|答案)\s*\d*[.、:：]\s*(.*)\s*$")
RELATED_PATTERN = re.compile(r"^\s*(?:问题变体|关联问题|相关问题|同义问法|问法)\s*[:：]\s*(.+?)\s*$")
KEYWORD_PATTERN = re.compile(r"^\s*(?:关键词|关键字|标签)\s*[:：]\s*(.+?)\s*$")
VALUE_SEPARATOR_PATTERN = re.compile(r"[\n,，、;；|]+")


def _split_values(value):
    return [item.strip() for item in VALUE_SEPARATOR_PATTERN.split(str(value or "")) if item.strip()]


def _problem_items(question, related_values):
    values = [question]
    values.extend(related_values)
    values.extend(expand_query_variants(question, limit=6))
    result = []
    seen = set()
    for value in values:
        value = str(value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append({"content": value[:255]})
    return result


class TextParseQAHandle(BaseParseQAHandle):
    def support(self, file, get_buffer):
        file_name = file.name.lower()
        if file_name.endswith((".txt", ".md", ".markdown")):
            return True
        buffer = get_buffer(file)
        result = detect(buffer)
        return bool(result.get("encoding") and result.get("confidence") and result.get("confidence") > 0.5)

    def handle(self, file, get_buffer, save_image):
        buffer = get_buffer(file)
        try:
            encoding = detect(buffer).get("encoding") or "utf-8"
            content = buffer.decode(encoding, errors="ignore")
            return {"name": file.name, "paragraphs": self._parse_content(content)}
        except Exception as e:
            maxkb_logger.error(f"Error processing QA text file {file.name}: {e}, {traceback.format_exc()}")
            return {"name": file.name, "paragraphs": []}

    def _parse_content(self, content):
        paragraphs = []
        current = None

        def flush():
            nonlocal current
            if not current:
                return
            answer = "\n".join(current["content_lines"]).strip()
            if current["question"] and answer:
                paragraphs.append(
                    {
                        "title": current["question"][:255],
                        "content": answer[:102400],
                        "problem_list": _problem_items(current["question"], current["related_values"]),
                    }
                )
            current = None

        for raw_line in str(content or "").splitlines():
            line = raw_line.strip()
            question_match = QUESTION_PATTERN.match(line)
            if question_match:
                flush()
                current = {
                    "question": question_match.group(1).strip(),
                    "content_lines": [],
                    "related_values": [],
                }
                continue

            if not current:
                continue

            answer_match = ANSWER_PATTERN.match(line)
            if answer_match:
                answer = answer_match.group(1).strip()
                if answer:
                    current["content_lines"].append(answer)
                continue

            related_match = RELATED_PATTERN.match(line)
            if related_match:
                current["related_values"].extend(_split_values(related_match.group(1)))
                continue

            keyword_match = KEYWORD_PATTERN.match(line)
            if keyword_match:
                current["related_values"].extend(_split_values(keyword_match.group(1)))
                continue

            current["content_lines"].append(raw_line)

        flush()
        return paragraphs
