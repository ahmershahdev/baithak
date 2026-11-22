from collections.abc import Sequence
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Q, QuerySet, Value, When
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.chat.access import channel_access, readable_channels
from apps.chat.models import Message
from apps.core import issues as rules
from apps.core.issues import CLOSED, Priority
from apps.core.roles import Role
from apps.issues import services
from apps.issues.access import project_access, projects_member
from apps.issues.models import Issue, Label, Project
from apps.issues.serializers import (
    IssueCreateSerializer,
    IssuePageSerializer,
    IssueSerializer,
    IssueWriteSerializer,
    LabelSerializer,
    ProjectCreateSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
)
from apps.workspaces import audit
from apps.workspaces.models import Member

PAGE_SIZE = 50
BOARD_COLUMN_SIZE = 100
KEY_TAKEN = "A project with this key already exists."
LABEL_TAKEN = "This project already has a label with that name."
NOT_FOR_ISSUE = "Only a message in a channel, not deleted, can have an issue."


def _user(request: Request) -> User:
    return cast(User, request.user)


def _with_counts(projects: QuerySet[Project]) -> QuerySet[Project]:
    return projects.annotate(
        open_issues=Count("issues", filter=~Q(issues__status__in=list(CLOSED)))
    )


def _check_manage(member: Member) -> None:
    if not rules.can_manage_projects(Role(member.role)):
        raise PermissionDenied("Only admins and owners can change projects and labels.")


class ProjectListView(APIView):
    @extend_schema(responses={200: ProjectSerializer(many=True)}, summary="Projects")
    def get(self, request: Request, slug: str) -> Response:
        member = projects_member(_user(request), slug)
        projects = _with_counts(Project.objects.for_workspace(member.workspace)).order_by("key")
        return Response(ProjectSerializer(projects, many=True).data)

    @extend_schema(
        request=ProjectCreateSerializer,
        responses={201: ProjectSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Create a project",
    )
    def post(self, request: Request, slug: str) -> Response:
        user = _user(request)
        member = projects_member(user, slug)
        _check_manage(member)
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                project = Project.objects.create(
                    workspace=member.workspace,
                    key=data["key"],
                    name=data["name"],
                    description=data.get("description", ""),
                    created_by=user,
                )
                audit.record(
                    member.workspace,
                    user,
                    "project.create",
                    project,
                    {"key": project.key, "name": project.name},
                )
        except IntegrityError as error:
            raise ValidationError({"key": [KEY_TAKEN]}) from error
        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    @extend_schema(responses={200: ProjectSerializer}, summary="One project")
    def get(self, request: Request, slug: str, key: str) -> Response:
        _, project = project_access(_user(request), slug, key)
        counted = _with_counts(Project.objects.filter(pk=project.pk)).get()
        return Response(ProjectSerializer(counted).data)

    @extend_schema(
        request=ProjectUpdateSerializer,
        responses={200: ProjectSerializer, 403: DetailSerializer},
        summary="Rename, describe, archive or unarchive a project",
    )
    def patch(self, request: Request, slug: str, key: str) -> Response:
        user = _user(request)
        member, project = project_access(user, slug, key)
        _check_manage(member)
        serializer = ProjectUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        before = {
            "name": project.name,
            "description": project.description,
            "archived": project.archived,
        }
        if "name" in data:
            project.name = data["name"]
        if "description" in data:
            project.description = data["description"]
        if "archived" in data and data["archived"] != project.archived:
            project.archived_at = timezone.now() if data["archived"] else None
        after = {
            "name": project.name,
            "description": project.description,
            "archived": project.archived,
        }
        changes = audit.diff(before, after)
        with transaction.atomic():
            project.save(update_fields=["name", "description", "archived_at"])
            if changes:
                audit.record(member.workspace, user, "project.update", project, changes)
        counted = _with_counts(Project.objects.filter(pk=project.pk)).get()
        return Response(ProjectSerializer(counted).data)


class LabelListView(APIView):
    @extend_schema(responses={200: LabelSerializer(many=True)}, summary="A project's labels")
    def get(self, request: Request, slug: str, key: str) -> Response:
        _, project = project_access(_user(request), slug, key)
        return Response(LabelSerializer(project.labels.order_by("name"), many=True).data)

    @extend_schema(
        request=LabelSerializer,
        responses={201: LabelSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Add a label",
    )
    def post(self, request: Request, slug: str, key: str) -> Response:
        user = _user(request)
        member, project = project_access(user, slug, key)
        _check_manage(member)
        serializer = LabelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                label = Label.objects.create(
                    workspace=member.workspace, project=project, **serializer.validated_data
                )
                audit.record(
                    member.workspace,
                    user,
                    "label.create",
                    label,
                    {"project": project.key, "name": label.name, "color": label.color},
                )
        except IntegrityError as error:
            raise ValidationError({"name": [LABEL_TAKEN]}) from error
        return Response(LabelSerializer(label).data, status=status.HTTP_201_CREATED)


class LabelDetailView(APIView):
    def _label(self, request: Request, slug: str, key: str, label_id: int) -> tuple[Member, Label]:
        member, project = project_access(_user(request), slug, key)
        label = (
            Label.objects.for_workspace(member.workspace)
            .filter(project=project, pk=label_id)
            .first()
        )
        if label is None:
            raise Http404
        _check_manage(member)
        return member, label

    @extend_schema(
        request=LabelSerializer,
        responses={200: LabelSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Rename or recolor a label",
    )
    def patch(self, request: Request, slug: str, key: str, label_id: int) -> Response:
        member, label = self._label(request, slug, key, label_id)
        serializer = LabelSerializer(label, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = {"name": label.name, "color": label.color}
        try:
            with transaction.atomic():
                serializer.save()
                changes = audit.diff(before, {"name": label.name, "color": label.color})
                if changes:
                    audit.record(member.workspace, _user(request), "label.update", label, changes)
        except IntegrityError as error:
            raise ValidationError({"name": [LABEL_TAKEN]}) from error
        return Response(LabelSerializer(label).data)

    @extend_schema(responses={204: None, 403: DetailSerializer}, summary="Delete a label")
    def delete(self, request: Request, slug: str, key: str, label_id: int) -> Response:
        member, label = self._label(request, slug, key, label_id)
        with transaction.atomic():
            audit.record(
                member.workspace, _user(request), "label.delete", label, {"name": label.name}
            )
            label.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _issues(project: Project) -> QuerySet[Issue]:
    return (
        Issue.objects.for_workspace(project.workspace)
        .filter(project=project)
        .select_related("project", "assignee", "created_by", "message")
        .prefetch_related("labels")
    )


def _show(member: Member, issues: Sequence[Issue]) -> list[dict[str, Any]]:
    """Serialize issues, showing each one's thread only to people who can read its channel."""
    linked = {issue.message.channel_id for issue in issues if issue.message is not None}
    readable = (
        set(readable_channels(member).filter(pk__in=linked).values_list("pk", flat=True))
        if linked
        else set()
    )
    return list(IssueSerializer(issues, many=True, context={"readable": readable}).data)


def _source_message(user: User, slug: str, data: dict[str, int]) -> Message:
    """The message to open an issue from: 404 if the person can't read it, like any message."""
    access = channel_access(user, slug, data["channel_id"])
    message = (
        Message.objects.filter(channel=access.channel, seq=data["seq"])
        .select_related("issue__project")
        .first()
    )
    if message is None:
        raise Http404
    if message.parent_id is not None or message.deleted:
        raise ValidationError({"from_message": [NOT_FOR_ISSUE]})
    existing = getattr(message, "issue", None)
    if existing is not None:
        raise ValidationError(
            {
                "from_message": [
                    f"This message already has {existing.project.key}-{existing.number}."
                ]
            }
        )
    return message


def _write_data(member: Member, project: Project, data: dict[str, Any]) -> dict[str, Any]:
    """Turn ids into rows, checking each belongs where it should."""
    out = {k: v for k, v in data.items() if k not in ("assignee_id", "label_ids")}
    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is None:
            out["assignee"] = None
        else:
            target = (
                Member.objects.for_workspace(member.workspace)
                .select_related("user")
                .filter(user_id=assignee_id)
                .first()
            )
            if target is None or not rules.can_be_assigned(Role(target.role)):
                raise ValidationError({"assignee_id": ["Pick a member of this workspace."]})
            out["assignee"] = target.user
    if "label_ids" in data:
        ids = set(data["label_ids"])
        labels = list(
            Label.objects.for_workspace(member.workspace).filter(project=project, pk__in=ids)
        )
        if len(labels) != len(ids):
            raise ValidationError({"label_ids": ["Use this project's labels."]})
        out["labels"] = labels
    return out


def _check_work(member: Member, project: Project) -> None:
    if not rules.can_work_on_issues(Role(member.role), archived=project.archived):
        raise PermissionDenied("This project is archived.")


class IssueListView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, description="Comma-separated statuses."),
            OpenApiParameter("open", bool, description="Only open (true) or closed (false)."),
            OpenApiParameter("assignee", str, description="A @handle, or 'none'."),
            OpenApiParameter("label", int, description="A label id."),
            OpenApiParameter("priority", str),
            OpenApiParameter("before", int, description="Issues numbered below this."),
            OpenApiParameter(
                "order",
                str,
                enum=["number", "priority"],
                description="priority: most pressing first, up to 100 (a board column).",
            ),
        ],
        responses={200: IssuePageSerializer},
        summary="A project's issues, newest first",
        operation_id="workspaces_projects_issues_list",
    )
    def get(self, request: Request, slug: str, key: str) -> Response:
        member, project = project_access(_user(request), slug, key)
        found = _issues(project)
        params = request.query_params
        if params.get("status"):
            found = found.filter(status__in=params["status"].split(","))
        if params.get("open") in ("true", "false"):
            closed = found.filter(status__in=list(CLOSED))
            found = (
                found.exclude(pk__in=closed.values("pk")) if params["open"] == "true" else closed
            )
        if params.get("assignee") == "none":
            found = found.filter(assignee__isnull=True)
        elif params.get("assignee"):
            found = found.filter(assignee__username=params["assignee"].lstrip("@").lower())
        if params.get("label", "").isdigit():
            found = found.filter(labels__pk=int(params["label"]))
        if params.get("priority"):
            found = found.filter(priority=params["priority"])
        total = found.count()
        if params.get("order") == "priority":
            # A board column: the most pressing first, one page, and the total for "N more".
            ranked = found.annotate(
                rank=Case(
                    *[When(priority=p, then=Value(rules.priority_rank(p))) for p in Priority],
                    output_field=IntegerField(),
                )
            )
            column = list(ranked.order_by("-rank", "-number")[:BOARD_COLUMN_SIZE])
            return Response({"results": _show(member, column), "next": None, "total": total})
        if params.get("before", "").isdigit():
            found = found.filter(number__lt=int(params["before"]))
        page = list(found.order_by("-number")[: PAGE_SIZE + 1])
        more = len(page) > PAGE_SIZE
        page = page[:PAGE_SIZE]
        return Response(
            {
                "results": _show(member, page),
                "next": page[-1].number if more else None,
                "total": total,
            }
        )

    @extend_schema(
        request=IssueCreateSerializer,
        responses={201: IssueSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Open an issue, on its own or from a message",
    )
    def post(self, request: Request, slug: str, key: str) -> Response:
        user = _user(request)
        member, project = project_access(user, slug, key)
        _check_work(member, project)
        serializer = IssueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        source = data.pop("from_message", None)
        fields = _write_data(member, project, data)
        if source is not None:
            fields["message"] = _source_message(user, slug, source)
        try:
            issue = services.create_issue(project, user, fields)
        except IntegrityError as error:
            # Another issue took the same message first; the one-to-one column refused this.
            raise ValidationError(
                {"from_message": ["This message already has an issue."]}
            ) from error
        return Response(
            _show(member, [_issues(project).get(pk=issue.pk)])[0],
            status=status.HTTP_201_CREATED,
        )


class IssueDetailView(APIView):
    @extend_schema(responses={200: IssueSerializer}, summary="One issue")
    def get(self, request: Request, slug: str, key: str, number: int) -> Response:
        member, project = project_access(_user(request), slug, key)
        issue = _issues(project).filter(number=number).first()
        if issue is None:
            raise Http404
        return Response(_show(member, [issue])[0])

    @extend_schema(
        request=IssueWriteSerializer,
        responses={200: IssueSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Change an issue",
    )
    def patch(self, request: Request, slug: str, key: str, number: int) -> Response:
        user = _user(request)
        member, project = project_access(user, slug, key)
        issue = _issues(project).filter(number=number).first()
        if issue is None:
            raise Http404
        _check_work(member, project)
        serializer = IssueWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_issue(issue, user, _write_data(member, project, serializer.validated_data))
        return Response(_show(member, [_issues(project).get(pk=issue.pk)])[0])
