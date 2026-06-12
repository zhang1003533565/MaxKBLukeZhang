# coding=utf-8


import re

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from common.utils.logger import maxkb_logger
from knowledge.models.knowledge import Knowledge


def save_problem(knowledge_id, document_id, paragraph_id, problem):
    from knowledge.serializers.paragraph import ParagraphSerializers

    # print(f"knowledge_id: {knowledge_id}")
    # print(f"document_id: {document_id}")
    # print(f"paragraph_id: {paragraph_id}")
    # print(f"problem: {problem}")
    problem = re.sub(r"^\d+\.\s*", "", problem)
    match = re.search(r"<question>(.*?)<\/question>", problem, flags=re.DOTALL)
    problem = match.group(1) if match else None
    if problem is None or len(problem) == 0:
        return
    try:
        workspace_id = QuerySet(Knowledge).filter(id=knowledge_id).first().workspace_id
        ParagraphSerializers.Problem(
            data={
                "workspace_id": workspace_id,
                "knowledge_id": knowledge_id,
                "document_id": document_id,
                "paragraph_id": paragraph_id,
            }
        ).save(instance={"content": problem}, with_valid=True)
    except Exception as e:
        maxkb_logger.error(_("Association problem failed {error}").format(error=str(e)))
