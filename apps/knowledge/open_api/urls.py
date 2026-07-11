# coding=utf-8
from django.urls import path

from knowledge.open_api import views

urlpatterns = [
    path("docs", views.KnowledgeOpenAPIDocsPageView.as_view()),
    path("docs/schema", views.KnowledgeOpenAPIDocsView.as_view()),
    path("docs/content", views.KnowledgeOpenAPIDocsContentView.as_view()),
    path("docs/download", views.KnowledgeOpenAPIDocsDownloadView.as_view()),
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
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/upload-tasks",
        views.KnowledgeOpenAPIUploadTaskListView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/upload-tasks/<str:task_id>",
        views.KnowledgeOpenAPIUploadTaskView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/upload-tasks/<str:task_id>/preview",
        views.KnowledgeOpenAPIUploadTaskPreviewView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/upload-tasks/<str:task_id>/apply",
        views.KnowledgeOpenAPIUploadTaskApplyView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/upload-tasks/<str:task_id>/cancel",
        views.KnowledgeOpenAPIUploadTaskCancelView.as_view(),
    ),
    path(
        "workspaces/<str:workspace_id>/knowledges/<str:knowledge_id>/documents/<str:document_id>/paragraphs",
        views.KnowledgeOpenAPIParagraphView.as_view(),
    ),
    path("workspaces/<str:workspace_id>/hit-test", views.KnowledgeOpenAPIHitTestView.as_view()),
]
