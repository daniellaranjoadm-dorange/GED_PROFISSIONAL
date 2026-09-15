from django.urls import path

from . import document_360_views, document_center_views, views

app_name = "api"

urlpatterns = [
    path(
        "document-center/<int:document_id>/",
        document_360_views.document_360_detail,
        name="document-center-detail",
    ),
    path("projects/", views.project_list, name="project-list"),
    path("projects/<int:id>/", views.project_detail, name="project-detail"),
    path("documents/", views.document_list, name="document-list"),
    path("documents/<int:id>/", views.document_detail, name="document-detail"),
    path(
        "document-center/",
        document_center_views.document_center_list,
        name="document-center-list",
    ),
    path(
        "document-center/metrics/",
        document_center_views.document_center_metrics,
        name="document-center-metrics",
    ),
    path(
        "document-center/filters/",
        document_center_views.document_center_filters,
        name="document-center-filters",
    ),
]
