import secrets
from typing import cast

from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils.text import slugify
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.chat.events import access_changed
from apps.chat.services import create_default_channel
from apps.core import roles
from apps.core.roles import Role
from apps.workspaces import audit
from apps.workspaces.access import membership, role_of
from apps.workspaces.models import AuditEvent, Member, Workspace
from apps.workspaces.serializers import (
    AuditEventSerializer,
    AuditPageSerializer,
    MemberSerializer,
    RoleSerializer,
    WorkspaceSerializer,
    WorkspaceWriteSerializer,
)


def _user(request: Request) -> User:
    return cast(User, request.user)


def _new_slug(name: str) -> str:
    base = slugify(name)[:40] or "workspace"
    if not Workspace.objects.filter(slug=base).exists():
        return base
    return f"{base}-{secrets.token_hex(3)}"


def _lock(workspace: Workspace) -> int:
    """Lock the workspace row and return its owner count.

    Role changes and removals take this lock first, so two owners demoting each other at the
    same moment can't leave the workspace with none.
    """
    Workspace.objects.select_for_update().get(pk=workspace.pk)
    return Member.objects.for_workspace(workspace).filter(role=Role.OWNER).count()


class WorkspaceListView(APIView):
    @extend_schema(responses={200: WorkspaceSerializer(many=True)}, summary="My workspaces")
    def get(self, request: Request) -> Response:
        members = (
            Member.objects.filter(user=_user(request))
            .select_related("workspace")
            .order_by("workspace__name", "workspace__id")
        )
        return Response([WorkspaceSerializer(member).data for member in members])

    @extend_schema(
        request=WorkspaceWriteSerializer,
        responses={201: WorkspaceSerializer, 403: DetailSerializer},
        summary="Create a workspace",
    )
    def post(self, request: Request) -> Response:
        user = _user(request)
        if not user.email_verified:
            raise PermissionDenied("Confirm your email before creating a workspace.")
        serializer = WorkspaceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        for _attempt in range(3):
            try:
                with transaction.atomic():
                    workspace = Workspace.objects.create(
                        name=name, slug=_new_slug(name), created_by=user
                    )
                    member = Member.objects.create(workspace=workspace, user=user, role=Role.OWNER)
                    audit.record(workspace, user, "workspace.create", workspace, {"name": name})
                    audit.record(workspace, user, "member.add", member, {"role": Role.OWNER})
                    create_default_channel(workspace, user)
                break
            except IntegrityError:
                # Another request took the same slug between the check and the insert.
                continue
        else:
            raise IntegrityError("Could not find a free workspace slug.")
        return Response(WorkspaceSerializer(member).data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    @extend_schema(responses={200: WorkspaceSerializer}, summary="One workspace")
    def get(self, request: Request, slug: str) -> Response:
        return Response(WorkspaceSerializer(membership(_user(request), slug)).data)

    @extend_schema(
        request=WorkspaceWriteSerializer,
        responses={200: WorkspaceSerializer, 403: DetailSerializer},
        summary="Rename a workspace",
    )
    def patch(self, request: Request, slug: str) -> Response:
        user = _user(request)
        member = membership(user, slug)
        if not roles.can_edit_workspace(role_of(member)):
            raise PermissionDenied("Only owners and admins can change the workspace.")
        serializer = WorkspaceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = member.workspace
        before = {"name": workspace.name}
        workspace.name = serializer.validated_data["name"]
        with transaction.atomic():
            workspace.save(update_fields=["name"])
            changes = audit.diff(before, {"name": workspace.name})
            if changes:
                audit.record(workspace, user, "workspace.update", workspace, changes)
        return Response(WorkspaceSerializer(member).data)


class MemberListView(APIView):
    @extend_schema(responses={200: MemberSerializer(many=True)}, summary="Workspace members")
    def get(self, request: Request, slug: str) -> Response:
        member = membership(_user(request), slug)
        members = (
            Member.objects.for_workspace(member.workspace)
            .select_related("user")
            .order_by("user__username")
        )
        return Response(MemberSerializer(members, many=True).data)


class MemberDetailView(APIView):
    def _target(self, workspace: Workspace, user_id: int) -> Member:
        target = (
            Member.objects.for_workspace(workspace).select_related("user").filter(user_id=user_id)
        ).first()
        if target is None:
            raise Http404
        return target

    @extend_schema(
        request=RoleSerializer,
        responses={200: MemberSerializer, 403: DetailSerializer},
        summary="Change a member's role",
    )
    def patch(self, request: Request, slug: str, user_id: int) -> Response:
        user = _user(request)
        workspace = membership(user, slug).workspace
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new = Role(serializer.validated_data["role"])
        with transaction.atomic():
            owners = _lock(workspace)
            # Read again under the lock: the actor's own role may have just changed.
            actor = membership(user, slug)
            target = self._target(workspace, user_id)
            old = Role(target.role)
            if not roles.can_change_role(role_of(actor), old, new, owners=owners):
                raise PermissionDenied("You can't give this person that role.")
            if new != old:
                target.role = new
                target.save(update_fields=["role"])
                audit.record(workspace, user, "member.update", target, {"role": [old, new]})
                access_changed(target.user_id)
        return Response(MemberSerializer(target).data)

    @extend_schema(
        responses={204: None, 403: DetailSerializer}, summary="Remove a member, or leave"
    )
    def delete(self, request: Request, slug: str, user_id: int) -> Response:
        user = _user(request)
        workspace = membership(user, slug).workspace
        with transaction.atomic():
            owners = _lock(workspace)
            actor = membership(user, slug)
            target = self._target(workspace, user_id)
            allowed = roles.can_remove(
                role_of(actor), Role(target.role), is_self=target.pk == actor.pk, owners=owners
            )
            if not allowed:
                raise PermissionDenied("You can't remove this person.")
            audit.record(workspace, user, "member.remove", target, {"user": target.user.username})
            target.delete()
            access_changed(target.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditPagination(CursorPagination):
    page_size = 50
    ordering = ("-at", "-id")


class AuditLogView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("cursor", str, description="From `next` of the previous page.")
        ],
        responses={200: AuditPageSerializer},
        summary="Audit log, newest first",
    )
    def get(self, request: Request, slug: str) -> Response:
        member = membership(_user(request), slug)
        if not roles.can_see_audit_log(role_of(member)):
            raise PermissionDenied("Only owners and admins can read the audit log.")
        events = AuditEvent.objects.for_workspace(member.workspace).select_related("actor")
        paginator = AuditPagination()
        page = paginator.paginate_queryset(events, request, view=self)
        return paginator.get_paginated_response(AuditEventSerializer(page, many=True).data)
