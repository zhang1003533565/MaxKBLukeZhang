# coding=utf-8
"""
轻量查询问法扩展。

这里不做全局同义词库，只为 QA 问答分段生成少量稳定的关联问法。
"""
import re
from itertools import product
from typing import Iterable, List

SYNONYM_GROUPS = [
    ("考试", "考核", "测验", "期末考试", "期末考核", "课程考核"),
    ("不能参加", "不得参加", "不允许参加", "无法参加", "不可参加", "不参加"),
    ("情况", "情形", "条件", "原因"),
    ("办理", "申请", "提出申请"),
    ("退课", "退课手续", "正式退课"),
    ("重修", "重新修读"),
]

QUESTION_INTENT_RULES = [
    {
        "match": "prefix",
        "triggers": (
            "啥情况",
            "什么情况",
            "哪些情况",
            "哪种情况",
            "何种情况",
            "什么情况下",
            "哪些情况下",
            "哪种情况下",
            "什么条件",
            "哪些条件",
            "什么情形",
            "哪些情形",
        ),
        "templates": (
            "什么情况{body}",
            "哪些情况{body}",
            "什么条件{body}",
            "哪些情形{body}",
        ),
    },
    {
        "match": "prefix",
        "triggers": ("为什么", "为何", "什么原因", "哪些原因"),
        "templates": (
            "为什么{body}",
            "什么原因{body}",
            "哪些原因{body}",
        ),
    },
    {
        "match": "prefix",
        "triggers": ("怎么处理", "如何处理", "怎么解决", "如何解决"),
        "templates": (
            "{body}怎么办",
            "{body}怎么处理",
            "如何处理{body}",
        ),
    },
    {
        "match": "suffix",
        "triggers": ("怎么办", "怎么处理", "如何处理", "怎么解决", "如何解决"),
        "templates": (
            "{body}怎么办",
            "{body}怎么处理",
            "如何处理{body}",
        ),
    },
]

QUESTION_WORD_REPLACEMENTS = [
    ("什么情况", ("哪些情况", "什么情形", "哪些情形", "什么条件")),
    ("哪些情况", ("什么情况", "什么情形", "哪些情形", "什么条件")),
    ("什么条件", ("哪些条件", "什么情况", "哪些情形")),
    ("哪些条件", ("什么条件", "哪些情况", "什么情形")),
    ("为什么", ("为何", "什么原因")),
    ("为何", ("为什么", "什么原因")),
    ("如何", ("怎么", "怎样")),
    ("怎么", ("如何", "怎样")),
    ("怎样", ("如何", "怎么")),
    ("是否", ("能否", "可不可以")),
    ("能否", ("是否", "可不可以")),
]


def _dedupe(items: Iterable[str], limit: int = 16) -> List[str]:
    result = []
    seen = set()
    for item in items:
        item = re.sub(r"\s+", " ", str(item or "")).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item[:255])
        if len(result) >= limit:
            break
    return result


def _matched_terms(text: str, group: tuple[str, ...]) -> List[str]:
    return [term for term in group if term in text]


def _replace_by_synonym_groups(text: str, limit: int = 8) -> List[str]:
    variants = [text]
    for group in SYNONYM_GROUPS:
        matched = _matched_terms(text, group)
        if not matched:
            continue
        for source, target in product(matched, group):
            if source != target:
                variants.append(text.replace(source, target))
    return _dedupe(variants, limit=limit)


def _question_intent_variants(query_text: str, limit: int = 8) -> List[str]:
    variants = []
    for rule in QUESTION_INTENT_RULES:
        match = rule["match"]
        for trigger in rule["triggers"]:
            if match == "prefix" and query_text.startswith(trigger):
                body = query_text[len(trigger) :].strip()
                break
            if match == "suffix" and query_text.endswith(trigger):
                body = query_text[: -len(trigger)].strip()
                break
        else:
            continue

        if not body:
            continue

        for template in rule["templates"]:
            for body_variant in _replace_by_synonym_groups(body, limit=6):
                variants.append(template.format(body=body_variant))
                if len(variants) >= limit:
                    return _dedupe(variants, limit=limit)
    return _dedupe(variants, limit=limit)


def _strip_question_mark(query_text: str) -> str:
    return re.sub(r"[？?]\s*$", "", query_text).strip()


def _polite_question_variants(query_text: str, limit: int = 4) -> List[str]:
    body = _strip_question_mark(query_text)
    if not body:
        return []
    variants = [
        f"请问{body}？",
        f"想了解一下，{body}？",
        f"{body}呢？",
    ]
    if not re.search(
        r"(什么|啥|哪些|哪种|为何|为什么|谁|哪里|哪儿|多少|"
        r"怎么|怎样|如何|怎么办|咋办)",
        body,
    ):
        variants.append(f"{body}具体怎么规定？")
    return _dedupe(variants, limit=limit)


def _question_word_variants(query_text: str, limit: int = 8) -> List[str]:
    variants = []
    for source, targets in QUESTION_WORD_REPLACEMENTS:
        if source not in query_text:
            continue
        for target in targets:
            variants.append(query_text.replace(source, target))
            if len(variants) >= limit:
                return _dedupe(variants, limit=limit)
    return _dedupe(variants, limit=limit)


def _policy_basis_variants(query_text: str, limit: int = 6) -> List[str]:
    body = _strip_question_mark(query_text)
    patterns = (
        r"^(?P<subject>.+?)是?根据什么制定的?$",
        r"^(?P<subject>.+?)的制定依据是什么$",
        r"^(?P<subject>.+?)依据哪些.+?制定$",
    )
    subject = ""
    for pattern in patterns:
        match = re.match(pattern, body)
        if match:
            subject = match.group("subject").strip("，, 。")
            break
    if not subject:
        return []
    return _dedupe(
        (
            f"{subject}的制定依据是什么？",
            f"{subject}是根据什么制定的？",
            f"{subject}依据哪些文件制定？",
            f"{subject}根据哪些规定制定？",
            f"制定{subject}的依据有哪些？",
            f"{subject}的制定根据是什么？",
        ),
        limit=limit,
    )


def expand_query_variants(query_text: str, limit: int = 8) -> List[str]:
    """
    根据标准问题生成少量问法变体。
    """
    query_text = str(query_text or "").strip()
    if not query_text:
        return []

    variants = [query_text]
    variants.extend(_question_intent_variants(query_text, limit=limit))
    variants.extend(_question_word_variants(query_text, limit=limit))
    variants.extend(_policy_basis_variants(query_text, limit=limit))
    variants.extend(_polite_question_variants(query_text, limit=limit))
    variants.extend(_replace_by_synonym_groups(query_text, limit=limit))
    return _dedupe(variants, limit=limit)
