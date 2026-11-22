from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Q, QuerySet
from django.http import Http404

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember
from apps.core import channels as rules
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.workspaces.access import membership
from apps.workspaces.models import Member


@dataclass(frozen=True)
class ChannelAccess:
    member: Member
    channel: Channel
    is_member: bool

    @property
    def role(self) -> Role:
        return Role(self.member.role)

    @property
    def kind(self) -> ChannelKind:
        return ChannelKind(self.channel.kind)


def readable_channels(member: Member) -> QuerySet[Channel]:
    """Every channel `member` may read, with `is_member` annotated.

    The same rule as apps.core.channels.can_read, written as a query; tests/chat/test_access.py
    checks the two agree for every role, kind and membership.
    """
    mine = ChannelMember.objects.filter(channel=OuterRef("pk"), user_id=member.user_id)
    channels = Channel.objects.for_workspace(member.workspace).annotate(is_member=Exists(mine))
    if Role(member.role) == Role.GUEST:
        return channels.filter(is_member=True, kind__in=rules.CONVERSATIONS)
    return channels.filter(Q(kind=ChannelKind.PUBLIC) | Q(is_member=True))


def channel_access(user: User, slug: str, channel_id: int) -> ChannelAccess:
    """The channel if the person may read it; otherwise 404, the same as a missing channel."""
    member = membership(user, slug)
    channel = Channel.objects.for_workspace(member.workspace).filter(pk=channel_id).first()
    if channel is None:
        raise Http404
    is_member = ChannelMember.objects.filter(channel=channel, user=user).exists()
    if not rules.can_read(Role(member.role), ChannelKind(channel.kind), is_member=is_member):
        raise Http404
    return ChannelAccess(member=member, channel=channel, is_member=is_member)
