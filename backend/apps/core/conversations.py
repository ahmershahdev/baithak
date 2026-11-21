"""Direct and group conversations: who can start one, and how one set of people maps to
exactly one conversation.
"""

from collections.abc import Iterable

from apps.core.channels import ChannelKind

# People in a group conversation, the starter included. Bigger groups belong in a channel.
MAX_PEOPLE = 9


def kind_for(people: int) -> ChannelKind | None:
    """`people` counts everyone in it, the starter included. None when no conversation fits."""
    if people == 2:
        return ChannelKind.DIRECT
    if 3 <= people <= MAX_PEOPLE:
        return ChannelKind.GROUP
    return None


def key(user_ids: Iterable[int]) -> str:
    """The conversation's channel name: the same people always give the same key, so starting
    a conversation finds the one that exists. "~" can't appear in a channel name a person
    picks, so a key never clashes with one."""
    ids = sorted(set(user_ids))
    return "~" + "-".join(str(user_id) for user_id in ids)
