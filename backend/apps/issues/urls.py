from django.urls import path

from apps.issues import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("<str:key>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<str:key>/labels/", views.LabelListView.as_view(), name="labels"),
    path("<str:key>/labels/<int:label_id>/", views.LabelDetailView.as_view(), name="label"),
    path("<str:key>/issues/", views.IssueListView.as_view(), name="issues"),
    path("<str:key>/issues/<int:number>/", views.IssueDetailView.as_view(), name="issue"),
    path(
        "<str:key>/issues/<int:number>/history/",
        views.IssueHistoryView.as_view(),
        name="issue-history",
    ),
]
