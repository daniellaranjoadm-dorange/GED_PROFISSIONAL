from django.urls import path
from .views import dashboard_index

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_index, name="index"),
]
