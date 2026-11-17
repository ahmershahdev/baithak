from datetime import timedelta
from typing import cast

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.core import roles
from apps.core.roles import Role
from apps.workspaces import audit
from apps.workspaces.access import membership, role_of
from apps.workspaces.invitation_tokens import hash_token
from apps.workspaces.models import Invitation, Member
from apps.workspaces.serializers import (
    INVITABLE_ROLE_CHOICES,
    ROLE_CHOICES,
    WorkspaceSerializer,
)
from apps.workspaces.tasks import send_invitation_email

INVITATION_DAYS = 7
BAD_INVITATION = "This invitation is not valid any more. Ask for a new one."


def pending_by_token(token: str) -> Invitation | None:
    # The hash column has no secret in it, so a plain lookup leaks nothing through timing.
    invitation = (
        Invitation.objects.select_related("workspace", "invited_by")
        .filter(token_hash=hash_token(token))
        .first()
    )
    if invitation is None or not token or not invitation.is_pending:
        return None
    return invitation


def mask_email(email: str) -> str:
    """a***@example.com: enough to recognise your own address, not enough to harvest one."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


class InvitationSerializer(serializers.ModelSerializer[Invitation]):
    invited_by = serializers.CharField(
        source="invited_by.username", read_only=True, allow_null=True
    )
    role = serializers.ChoiceField(choices=ROLE_CHOICES, read_only=True)

    class Meta:
        model = Invitation
        fields = ("id", "email", "role", "invited_by", "created_at", "expires_at")
        read_only_fields = fields


class InviteSerializer(serializers.Serializer[None]):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=INVITABLE_ROLE_CHOICES)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class TokenSerializer(serializers.Serializer[None]):
    token = serializers.CharField(max_length=128)


class InvitationPreviewSerializer(serializers.Serializer[None]):
    workspace = serializers.CharField()
    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    invited_by = serializers.CharField(allow_null=True)
    email = serializers.CharField(help_text="The invited address, masked.")


def _user(request: Request) -> User:
    return cast(User, request.user)


class InvitationListView(APIView):
    throttle_scope = "invite"

    def _admin(self, request: Request, slug: str) -> Member:
        member = membership(_user(request), slug)
        if not roles.is_admin(role_of(member)):
            raise PermissionDenied("Only owners and admins can manage invitations.")
        return member

    @extend_schema(responses={200: InvitationSerializer(many=True)}, summary="Pending invitations")
    def get(self, request: Request, slug: str) -> Response:
        member = self._admin(request, slug)
        pending = (
            Invitation.objects.for_workspace(member.workspace)
            .filter(accepted_at=None, revoked_at=None, expires_at__gt=timezone.now())
            .select_related("invited_by")
            .order_by("-created_at")
        )
        return Response(InvitationSerializer(pending, many=True).data)

    @extend_schema(
        request=InviteSerializer,
        responses={201: InvitationSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Invite someone by email",
    )
    def post(self, request: Request, slug: str) -> Response:
        user = _user(request)
        member = self._admin(request, slug)
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        role = Role(serializer.validated_data["role"])
        if not roles.can_invite(role_of(member), role):
            raise PermissionDenied("You can't invite someone with that role.")
        workspace = member.workspace
        if Member.objects.for_workspace(workspace).filter(user__email=email).exists():
            return Response(
                {"detail": "This person is already in the workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        with transaction.atomic():
            # Inviting the same address again replaces the old invitation, so only the newest
            # link works.
            Invitation.objects.for_workspace(workspace).filter(
                email=email, accepted_at=None, revoked_at=None
            ).update(revoked_at=now)
            invitation = Invitation.objects.create(
                workspace=workspace,
                email=email,
                role=role,
                invited_by=user,
                expires_at=now + timedelta(days=INVITATION_DAYS),
            )
            audit.record(
                workspace, user, "invitation.create", invitation, {"email": email, "role": role}
            )
            transaction.on_commit(lambda: send_invitation_email.delay(invitation.pk))
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationDetailView(APIView):
    @extend_schema(responses={204: None, 403: DetailSerializer}, summary="Revoke an invitation")
    def delete(self, request: Request, slug: str, invitation_id: int) -> Response:
        user = _user(request)
        member = membership(user, slug)
        if not roles.is_admin(role_of(member)):
            raise PermissionDenied("Only owners and admins can manage invitations.")
        workspace = member.workspace
        with transaction.atomic():
            invitation = (
                Invitation.objects.for_workspace(workspace)
                .select_for_update()
                .filter(pk=invitation_id, accepted_at=None, revoked_at=None)
                .first()
            )
            if invitation is None:
                raise Http404
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=["revoked_at"])
            audit.record(
                workspace, user, "invitation.revoke", invitation, {"email": invitation.email}
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationPreviewView(APIView):
    permission_classes = (AllowAny,)
    throttle_scope = "auth"

    @extend_schema(
        request=TokenSerializer,
        responses={200: InvitationPreviewSerializer, 404: DetailSerializer},
        summary="What an invitation link is for",
    )
    def post(self, request: Request) -> Response:
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = pending_by_token(serializer.validated_data["token"])
        if invitation is None:
            return Response({"detail": BAD_INVITATION}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "workspace": invitation.workspace.name,
                "role": invitation.role,
                "invited_by": invitation.invited_by.username if invitation.invited_by else None,
                "email": mask_email(invitation.email),
            }
        )


class InvitationAcceptView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = "auth"

    @extend_schema(
        request=TokenSerializer,
        responses={200: WorkspaceSerializer, 403: DetailSerializer, 404: DetailSerializer},
        summary="Accept an invitation",
    )
    def post(self, request: Request) -> Response:
        user = _user(request)
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_hash = hash_token(serializer.validated_data["token"])
        with transaction.atomic():
            # Locked so the same link can't be accepted twice at once.
            invitation = (
                Invitation.objects.select_for_update()
                .select_related("workspace")
                .filter(token_hash=token_hash)
                .first()
            )
            if invitation is None or not invitation.is_pending:
                return Response({"detail": BAD_INVITATION}, status=status.HTTP_404_NOT_FOUND)
            if invitation.email != user.email:
                return Response(
                    {
                        "detail": "This invitation was sent to another email address. Sign in "
                        "with that address to accept it."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            # The link came to this address, so it proves the person reads that inbox.
            if not user.email_verified:
                user.email_verified_at = timezone.now()
                user.save(update_fields=["email_verified_at"])
            workspace = invitation.workspace
            member, created = Member.objects.get_or_create(
                workspace=workspace, user=user, defaults={"role": invitation.role}
            )
            invitation.accepted_at = timezone.now()
            invitation.accepted_by = user
            invitation.save(update_fields=["accepted_at", "accepted_by"])
            audit.record(workspace, user, "invitation.accept", invitation, {"email": user.email})
            if created:
                audit.record(workspace, user, "member.add", member, {"role": member.role})
        return Response(WorkspaceSerializer(member).data)
