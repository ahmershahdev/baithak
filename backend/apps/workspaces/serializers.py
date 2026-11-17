from rest_framework import serializers

from apps.core.roles import Role
from apps.workspaces.models import AuditEvent, Member

ROLE_CHOICES = [role.value for role in Role]
INVITABLE_ROLE_CHOICES = [role.value for role in Role if role != Role.OWNER]


class WorkspaceSerializer(serializers.Serializer[Member]):
    """A workspace as seen by one member: built from that member's row."""

    slug = serializers.SlugField(source="workspace.slug", read_only=True)
    name = serializers.CharField(source="workspace.name", read_only=True)
    created_at = serializers.DateTimeField(source="workspace.created_at", read_only=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, read_only=True)


class WorkspaceWriteSerializer(serializers.Serializer[None]):
    name = serializers.CharField(max_length=80)

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the workspace a name.")
        return value


class MemberSerializer(serializers.ModelSerializer[Member]):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, read_only=True)

    class Meta:
        model = Member
        fields = ("user_id", "username", "display_name", "role", "joined_at")
        read_only_fields = fields


class RoleSerializer(serializers.Serializer[None]):
    role = serializers.ChoiceField(choices=ROLE_CHOICES)


class AuditEventSerializer(serializers.ModelSerializer[AuditEvent]):
    actor = serializers.CharField(source="actor.username", read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = ("id", "actor", "action", "model", "object_id", "changes", "at")
        read_only_fields = fields


class AuditPageSerializer(serializers.Serializer[None]):
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AuditEventSerializer(many=True)
