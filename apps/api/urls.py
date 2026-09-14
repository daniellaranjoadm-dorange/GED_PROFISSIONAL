from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("projects/", views.project_list, name="project-list"),
    path("projects/<int:id>/", views.project_detail, name="project-detail"),
    path("documents/", views.document_list, name="document-list"),
    path("documents/<int:id>/", views.document_detail, name="document-detail"),
]
