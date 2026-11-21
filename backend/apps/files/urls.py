from django.urls import path

from apps.files import views

app_name = "files"

urlpatterns = [
    path("<str:token>/", views.DownloadView.as_view(), name="download"),
]
