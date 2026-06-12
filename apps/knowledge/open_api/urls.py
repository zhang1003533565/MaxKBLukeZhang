# coding=utf-8
from django.urls import path

from knowledge.open_api import views

urlpatterns = [
    path("docs", views.KnowledgeOpenAPIDocsView.as_view()),
    path("workspaces/<str:workspace_id>/knowledges", views.KnowledgeOpenAPIKnowledgeView.as_view()),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>",
        views.KnowledgeOpenAPIKnowledgeDetailView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents",
        views.KnowledgeOpenAPIDocumentView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/upload",
        views.KnowledgeOpenAPIUploadDocumentView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/<str:document_id>/paragraphs",
        views.KnowledgeOpenAPIParagraphView.as_view(),
    ),
    path("workspaces/<str:workspace_id>/hit-test", views.KnowledgeOpenAPIHitTestView.as_view()),
]
