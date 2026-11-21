from rest_framework import serializers

from apps.chat.serializers import AuthorSerializer
from apps.core.issues import LABEL_COLORS, Priority, Status, valid_key
from apps.issues.models import Issue, Label, Project

STATUS_CHOICES = [s.value for s in Status]
PRIORITY_CHOICES = [p.value for p in Priority]


class ProjectSerializer(serializers.ModelSerializer[Project]):
    archived = serializers.BooleanField(read_only=True)
    open_issues = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = ("key", "name", "description", "archived", "open_issues", "created_at")
        read_only_fields = fields


class ProjectCreateSerializer(serializers.Serializer[None]):
    key = serializers.CharField(max_length=10, help_text="2 to 10 letters or digits; KEY-12.")
    name = serializers.CharField(max_length=80)
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_key(self, value: str) -> str:
        key = value.strip().upper()
        if not valid_key(key):
            raise serializers.ValidationError(
                "Use 2 to 10 letters or digits, starting with a letter."
            )
        return key


class ProjectUpdateSerializer(serializers.Serializer[None]):
    name = serializers.CharField(max_length=80, required=False)
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    archived = serializers.BooleanField(required=False)


class LabelSerializer(serializers.ModelSerializer[Label]):
    color = serializers.ChoiceField(choices=list(LABEL_COLORS))

    class Meta:
        model = Label
        fields = ("id", "name", "color")
        read_only_fields = ("id",)


class IssueSerializer(serializers.ModelSerializer[Issue]):
    """Needs `project`, `assignee`, `created_by` loaded and `labels` prefetched."""

    ref = serializers.SerializerMethodField(help_text="KEY-12")
    status = serializers.ChoiceField(choices=STATUS_CHOICES, read_only=True)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, read_only=True)
    assignee = AuthorSerializer(read_only=True, allow_null=True)
    created_by = AuthorSerializer(read_only=True, allow_null=True)
    labels = LabelSerializer(many=True, read_only=True)

    class Meta:
        model = Issue
        fields = (
            "number",
            "ref",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "due",
            "labels",
            "created_by",
            "created_at",
            "updated_at",
            "closed_at",
        )
        read_only_fields = fields

    def get_ref(self, issue: Issue) -> str:
        return f"{issue.project.key}-{issue.number}"


class IssueWriteSerializer(serializers.Serializer[None]):
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=10000)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False)
    assignee_id = serializers.IntegerField(required=False, allow_null=True)
    due = serializers.DateField(required=False, allow_null=True)
    label_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, max_length=20
    )


class IssuePageSerializer(serializers.Serializer[None]):
    results = IssueSerializer(many=True)
    next = serializers.IntegerField(allow_null=True, help_text="`before` for the next page.")
    total = serializers.IntegerField(help_text="How many match the filters, on every page.")
