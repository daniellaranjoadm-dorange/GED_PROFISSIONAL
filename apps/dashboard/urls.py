from django.urls import path
from .views import dashboard   # agora só existe o master

app_name = "dashboard"

urlpatterns = [
    path("", dashboard, name="dashboard_master"),   # rota principal
]
