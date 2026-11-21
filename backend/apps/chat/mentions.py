from django.db.models import Q

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember
from apps.core import channels as rules
from apps.core.channels import ChannelKind
from apps.core.mentions import can_mention_channel, parse
from apps.core.roles import Role
from apps.workspaces.models import Member


def resolve(channel: Channel, author_id: int | None, body: str) -> tuple[list[User], bool]:
    """Who `body` mentions, and whether it mentions the whole channel.

    Only people who can read the channel count, by the same rule as everywhere else, so a
    mention can't tell anyone a private channel exists.
    """
    found = parse(body)
    if not found.handles and not found.channel:
        return [], False
    members = list(
        Member.objects.for_workspace(channel.workspace)
        .select_related("user")
        .filter(Q(user_id=author_id) | Q(user__username__in=found.handles))
    )
    author_member = next((m for m in members if m.user_id == author_id), None)
    everyone = (
        found.channel
        and author_member is not None
        and can_mention_channel(Role(author_member.role))
    )
    named = [m for m in members if m.user.username in found.handles]
    if not named:
        return [], everyone
    inside = set(
        ChannelMember.objects.filter(
            channel=channel, user_id__in=[m.user_id for m in named]
        ).values_list("user_id", flat=True)
    )
    kind = ChannelKind(channel.kind)
    readers = [
        m.user for m in named if rules.can_read(Role(m.role), kind, is_member=m.user_id in inside)
    ]
    return sorted(readers, key=lambda user: user.username), everyone
