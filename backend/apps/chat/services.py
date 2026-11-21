from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.workspaces import audit
from apps.workspaces.models import Workspace

DEFAULT_CHANNEL = "general"


def create_default_channel(workspace: Workspace, creator: User) -> Channel:
    """#general, made with the workspace. Call inside the workspace's create transaction."""
    channel = Channel.objects.create(
        workspace=workspace,
        name=DEFAULT_CHANNEL,
        kind=ChannelKind.PUBLIC,
        is_default=True,
        created_by=creator,
    )
    ChannelMember.objects.create(channel=channel, user=creator)
    audit.record(workspace, creator, "channel.create", channel, {"name": channel.name})
    return channel


def join_default_channels(workspace: Workspace, user: User, role: Role) -> None:
    """New members sit in the default channels; guests only where they are added."""
    if role == Role.GUEST:
        return
    for channel in Channel.objects.for_workspace(workspace).filter(
        is_default=True, archived_at=None
    ):
        _, created = ChannelMember.objects.get_or_create(
            channel=channel, user=user, defaults={"last_read_seq": channel.last_seq}
        )
        if created:
            audit.record(workspace, user, "channel.join", channel, {"name": channel.name})
