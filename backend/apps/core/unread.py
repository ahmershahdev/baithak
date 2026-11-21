"""Read markers and unread counts, per person and channel.

A marker is the seq of the newest message the person has read. It only moves forward, so a
device that reports late can't make another device's messages unread again.
"""


def marker_after(current: int, requested: int, last_seq: int) -> int:
    """Where the marker lands when a device reports reading up to `requested`."""
    return max(current, min(requested, last_seq))


def unread_count(last_seq: int, last_read_seq: int, deleted_unread: int) -> int:
    """`deleted_unread` is how many messages after the marker were deleted; they don't count."""
    return max(0, last_seq - last_read_seq - deleted_unread)
