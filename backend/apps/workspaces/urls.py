from django.urls import path

from apps.workspaces import invitations, views

app_name = "workspaces"

urlpatterns = [
    path("", views.WorkspaceListView.as_view(), name="list"),
    path("<slug:slug>/", views.WorkspaceDetailView.as_view(), name="detail"),
    path("<slug:slug>/members/", views.MemberListView.as_view(), name="members"),
    path(
        "<slug:slug>/members/<int:user_id>/",
        views.MemberDetailView.as_view(),
        name="member",
    ),
    path("<slug:slug>/audit/", views.AuditLogView.as_view(), name="audit"),
    path(
        "<slug:slug>/invitations/",
        invitations.InvitationListView.as_view(),
        name="invitations",
    ),
    path(
        "<slug:slug>/invitations/<int:invitation_id>/",
        invitations.InvitationDetailView.as_view(),
        name="invitation",
    ),
]
