from django.urls import path

from apps.workspaces import invitations

app_name = "invitations"

urlpatterns = [
    path("preview/", invitations.InvitationPreviewView.as_view(), name="preview"),
    path("accept/", invitations.InvitationAcceptView.as_view(), name="accept"),
]
