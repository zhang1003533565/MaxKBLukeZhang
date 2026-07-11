import json
import re
from collections import Counter


PRIVATE_BULLETS = "◆●○"
GENERIC_TITLE_PATTERN = re.compile(
    r"^(?:示例|实例|案例|其他|概述|总结|未命名|Python实例[（(]?[一二三四五六七八九十0-9]+[）)]?)$",
    re.IGNORECASE,
)
IMAGE_PATTERN = re.compile(r"!\[[^]]*\]\(\./oss/(?:image|file)/[^)]+\)")
IMAGE_ID_PATTERN = re.compile(r"(!\[[^]]*\]\(\./oss/(?:image|file)/)([^)]+)(\))")
URL_PATTERN = re.compile(r"https?://[^\s)]+")
IMAGE_DESCRIPTION_PATTERN = re.compile(r"^图片说明：.+$", re.MULTILINE)
CODE_LINE_PATTERN = re.compile(
    r"^(?:>>>|\.\.\.|import\s|from\s|def\s|class\s|print\s*\(|pip\s+install\s|[\w.-]+\s*=).+$",
    re.MULTILINE,
)
FENCED_CODE_PATTERN = re.compile(r"```[\s\S]*?```")


def _is_noise_line(line):
    stripped = line.strip()
    return bool(
        re.fullmatch(r"第\s*\d{1,3}\s*页", stripped)
        or stripped.lower() == "www.themegallery.com"
    )


def _is_decorative_separator(line):
    return bool(re.fullmatch(r"[\s\-_=*·•—–]{4,}", line))


def clean_paragraph_content(content):
    removed_noise = 0
    cleaned_lines = []
    in_fenced_code = False
    previous_line = None
    for line in str(content or "").splitlines():
        if line.lstrip().startswith("```"):
            in_fenced_code = not in_fenced_code
            cleaned_lines.append(line)
            continue
        if in_fenced_code:
            cleaned_lines.append(line)
            continue
        if _is_noise_line(line):
            removed_noise += 1
            continue
        if _is_decorative_separator(line):
            removed_noise += 1
            continue
        normalized = re.sub(
            rf"^\s*[{re.escape(PRIVATE_BULLETS)}]\s*", "- ", line.rstrip()
        )
        stripped = normalized.strip()
        if (
            stripped
            and stripped == previous_line
            and (len(stripped) <= 80 or stripped.startswith("图片说明："))
        ):
            removed_noise += 1
            continue
        cleaned_lines.append(normalized)
        previous_line = stripped or previous_line
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, {"removed_noise": removed_noise}


def is_generic_title(title):
    return bool(GENERIC_TITLE_PATTERN.fullmatch(str(title or "").strip()))


def analyze_paragraph(paragraph):
    content = str(paragraph.get("content") or "")
    length = len(content)
    return {
        "length": length,
        "image_count": len(IMAGE_PATTERN.findall(content)),
        "fallback_image_count": content.count("视觉模型未能识别，已保留原始插图"),
        "noise_count": sum(_is_noise_line(line) for line in content.splitlines()),
        "generic_title": is_generic_title(paragraph.get("title")),
        "too_short": length < 120,
        "too_long": length > 900,
        "hard_too_long": length > 1400,
    }


def clean_paragraphs(paragraphs):
    cleaned = []
    report = {
        "paragraphs_before": len(paragraphs),
        "paragraphs_after": len(paragraphs),
        "removed_noise": 0,
        "generic_titles": 0,
        "fallback_images": 0,
    }
    for paragraph in paragraphs:
        item = dict(paragraph)
        item["content"], clean_report = clean_paragraph_content(item.get("content"))
        metrics = analyze_paragraph(item)
        report["removed_noise"] += clean_report["removed_noise"]
        report["generic_titles"] += int(metrics["generic_title"])
        report["fallback_images"] += metrics["fallback_image_count"]
        cleaned.append(item)
    return cleaned, report


def extract_protected_items(content):
    text = str(content or "")
    items = []
    for kind, pattern in [
        ("image", IMAGE_PATTERN),
        ("url", URL_PATTERN),
        ("image_description", IMAGE_DESCRIPTION_PATTERN),
        ("fenced_code", FENCED_CODE_PATTERN),
        ("code", CODE_LINE_PATTERN),
    ]:
        items.extend((kind, match.group(0).strip()) for match in pattern.finditer(text))
    return Counter(items)


def validate_optimized_batch(source, result):
    if not result or any(not str(item.get("content") or "").strip() for item in result):
        return False, "empty_result"
    source_contents = [str(item.get("content") or "") for item in source]
    result_contents = [str(item.get("content") or "") for item in result]
    source_content = "\n".join(source_contents)
    result_content = "\n".join(result_contents)
    if extract_protected_items(source_content) != extract_protected_items(result_content):
        return False, "protected_items_changed"
    canonical_source = "".join(content.strip() for content in source_contents).replace(
        "\r\n", "\n"
    )
    canonical_result = "".join(content.strip() for content in result_contents).replace(
        "\r\n", "\n"
    )
    if canonical_source != canonical_result:
        return False, "content_changed"
    for item in result:
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if is_generic_title(title):
            return False, "generic_title"
        if not 4 <= len(title) <= 40:
            return False, "invalid_title_length"
        if len(content) > 1400:
            return False, "paragraph_too_long"
        if len(content) < 80 and not (IMAGE_PATTERN.search(content) or CODE_LINE_PATTERN.search(content)):
            return False, "paragraph_too_short"
    source_length = max(len(source_content), 1)
    if abs(len(result_content) - len(source_content)) / source_length > 0.15:
        return False, "content_length_changed"
    return True, ""


def build_quality_prompt(document_name, paragraphs):
    return (
        "你是知识库段落质量优化器。只做主题拆分、相邻合并和标题重写，不总结、不扩写、不纠正事实。\n"
        "必须原样保留图片引用、图片说明、URL、代码和命令；每段只表达一个主题，标题4到40个字符。\n"
        '只输出JSON：{"paragraphs":[{"title":"具体知识点标题","content":"原文内容"}]}\n'
        f"文档名：{document_name}\n待优化段落：\n"
        f"{json.dumps(paragraphs, ensure_ascii=False)}"
    )


def replace_image_ids_with_aliases(paragraphs):
    alias_to_image_id = {}

    def replace(match):
        image_id = match.group(2)
        alias = next(
            (key for key, value in alias_to_image_id.items() if value == image_id),
            None,
        )
        if alias is None:
            alias = f"img_{len(alias_to_image_id)}"
            alias_to_image_id[alias] = image_id
        return f"{match.group(1)}{alias}{match.group(3)}"

    aliased = []
    for paragraph in paragraphs:
        item = dict(paragraph)
        item["content"] = IMAGE_ID_PATTERN.sub(replace, str(item.get("content") or ""))
        aliased.append(item)
    return aliased, alias_to_image_id


def restore_image_aliases(paragraphs, alias_to_image_id):
    restored = []
    for paragraph in paragraphs:
        item = dict(paragraph)

        def replace(match):
            image_id = alias_to_image_id.get(match.group(2))
            return (
                f"{match.group(1)}{image_id}{match.group(3)}"
                if image_id is not None
                else match.group(0)
            )

        item["content"] = IMAGE_ID_PATTERN.sub(replace, str(item.get("content") or ""))
        restored.append(item)
    return restored


def normalize_quality_result(payload):
    paragraphs = payload.get("paragraphs") if isinstance(payload, dict) else None
    if not isinstance(paragraphs, list):
        return []
    return [
        {
            "title": str(item.get("title") or "").strip(),
            "content": str(item.get("content") or "").strip(),
        }
        for item in paragraphs
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
