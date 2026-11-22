from typing import ClassVar

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.core.channels import ChannelKind
from apps.workspaces.models import Workspace, WorkspaceScopedManager

channel_name_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9_-]{0,79}$",
    "Use lowercase letters, digits, hyphens or underscores, starting with a letter or digit.",
)


class Channel(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=80, validators=[channel_name_validator])
    kind = models.CharField(max_length=10, choices=[(k.value, k.name.title()) for k in ChannelKind])
    topic = models.CharField(max_length=250, blank=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    # Both move only under a lock on this row (apps/chat/messages.py). last_seq numbers messages
    # (order, unread counts); last_event numbers every change, edits and deletes included, so a
    # client catching up after a reconnect asks for events after the last one it saw.
    last_seq = models.BigIntegerField(default=0)
    last_event = models.BigIntegerField(default=0)

    objects = WorkspaceScopedManager["Channel"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["workspace", "name"], name="channel_name_per_workspace")
        ]

    def __str__(self) -> str:
        return f"#{self.name}"

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


class ChannelMember(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="channel_memberships"
    )
    last_read_seq = models.BigIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["channel", "user"], name="channel_member_once")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.channel_id}"


class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="messages")
    # Its place in the channel. None for a thread reply not also sent to the channel, so replies
    # don't change unread counts or channel history.
    seq = models.BigIntegerField(null=True, blank=True)
    event = models.BigIntegerField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    thread_seq = models.BigIntegerField(null=True, blank=True)
    also_in_channel = models.BooleanField(default=False)
    # Counts deleted replies too: it numbers them (thread_seq), and deleted rows stay.
    reply_count = models.IntegerField(default=0)
    last_reply_at = models.DateTimeField(null=True, blank=True)
    # Worked out from the body on every save (apps/chat/mentions.py): only people who can read
    # the channel.
    mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="+")
    mentions_channel = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    body = models.TextField(blank=True)
    # "activity": an issue change, written for the author (docs/architecture.md, Issues).
    # "integration": posted by an app such as GitHub, with no author and `sender_name` shown.
    kind = models.CharField(
        max_length=12,
        choices=[("message", "Message"), ("activity", "Activity"), ("integration", "Integration")],
        default="message",
    )
    sender_name = models.CharField(max_length=40, blank=True)
    # Chosen by the sender's device so a send retried after a dropped connection is stored once.
    client_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["channel", "seq"], name="message_seq_per_channel"),
            models.UniqueConstraint(fields=["channel", "event"], name="message_event_per_channel"),
            models.UniqueConstraint(fields=["parent", "thread_seq"], name="reply_seq_per_thread"),
        ]
        indexes: ClassVar = [
            models.Index(fields=["channel", "author", "client_id"], name="message_client_id"),
        ]

    def __str__(self) -> str:
        if self.parent_id is not None:
            return f"{self.channel_id}#{self.parent_id}/{self.thread_seq}"
        return f"{self.channel_id}#{self.seq}"

    @property
    def deleted(self) -> bool:
        return self.deleted_at is not None


class Reaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    emoji = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["message", "user", "emoji"], name="reaction_once_per_person"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.emoji} on {self.message_id}"
