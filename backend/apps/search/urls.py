from django.urls import path

from apps.search import views

app_name = "search"

urlpatterns = [
    path("messages/", views.MessageSearchView.as_view(), name="messages"),
    path("files/", views.FileSearchView.as_view(), name="files"),
    path("issues/", views.IssueSearchView.as_view(), name="issues"),
]
