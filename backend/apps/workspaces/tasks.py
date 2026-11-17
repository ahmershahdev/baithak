from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.tasks import email_task
from apps.workspaces.invitation_tokens import new_token
from apps.workspaces.models import Invitation


@email_task
def send_invitation_email(invitation_id: int) -> None:
    # The token is made here, in the worker, so it never passes through the broker; a retry
    # makes a new one and the old link stops working.
    invitation = (
        Invitation.objects.select_related("workspace", "invited_by")
        .filter(pk=invitation_id)
        .first()
    )
    if invitation is None or not invitation.is_pending:
        return
    token = new_token(invitation)
    inviter = invitation.invited_by
    who = (inviter.display_name or inviter.username) if inviter else "Someone"
    workspace = invitation.workspace.name
    link = f"{settings.FRONTEND_URL}/invite?token={token}"
    send_mail(
        f"{who} invited you to {workspace} on Baithak",
        f"{who} invited you to join {workspace} on Baithak as {invitation.role}.\n\n"
        f"Open this link to accept:\n\n{link}\n\n"
        "The link works once and expires in 7 days. If you did not expect this, you can ignore "
        "this email.",
        None,
        [invitation.email],
    )
