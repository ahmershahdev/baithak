import json
import secrets
from typing import cast

from django.db import transaction
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.chat.access import channel_access
from apps.core import github, webhooks
from apps.core.channels import CONVERSATIONS, ChannelKind
from apps.core.roles import Role, is_admin
from apps.integrations import deliveries, tasks
from apps.integrations.models import Webhook
from apps.integrations.serializers import (
    DeliverySerializer,
    IncomingSerializer,
    NewWebhookSerializer,
    WebhookCreateSerializer,
    WebhookSerializer,
)
from apps.integrations.throttles import PerWebhookThrottle
from apps.workspaces import audit
from apps.workspaces.access import membership
from apps.workspaces.models import Member

DELIVERIES_SHOWN = 50


def _admin(request: Request, slug: str) -> tuple[User, Member]:
    user = cast(User, request.user)
    member = membership(user, slug)
    if not is_admin(Role(member.role)):
        raise PermissionDenied("Only owners and admins can manage integrations.")
    return user, member


class WebhookListView(APIView):
    @extend_schema(responses={200: WebhookSerializer(many=True)}, summary="Webhooks")
    def get(self, request: Request, slug: str) -> Response:
        _, member = _admin(request, slug)
        found = (
            Webhook.objects.for_workspace(member.workspace)
            .select_related("created_by")
            .order_by("-pk")
        )
        return Response(WebhookSerializer(found, many=True).data)

    @extend_schema(
        request=WebhookCreateSerializer,
        responses={201: NewWebhookSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Connect a GitHub repository, or make an incoming webhook, for a channel",
    )
    def post(self, request: Request, slug: str) -> Response:
        user, member = _admin(request, slug)
        serializer = WebhookCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        channel = channel_access(user, slug, data["channel_id"]).channel
        if ChannelKind(channel.kind) in CONVERSATIONS or channel.archived:
            raise ValidationError({"channel_id": ["Pick a channel that is not archived."]})
        github_kind = data["kind"] == "github"
        token = webhooks.new_token()
        with transaction.atomic():
            webhook = Webhook.objects.create(
                workspace=member.workspace,
                channel=channel,
                kind=data["kind"],
                repo=data.get("repo", "") if github_kind else "",
                name="" if github_kind else data["name"].strip(),
                token=token if github_kind else webhooks.digest(token),
                secret=secrets.token_urlsafe(32) if github_kind else "",
                created_by=user,
            )
            audit.record(
                member.workspace,
                user,
                "webhook.create",
                webhook,
                {
                    "kind": webhook.kind,
                    "repo": webhook.repo,
                    "name": webhook.name,
                    "channel": channel.name,
                },
            )
        return Response(
            NewWebhookSerializer(webhook, context={"token": token}).data,
            status=status.HTTP_201_CREATED,
        )


class WebhookDetailView(APIView):
    @extend_schema(responses={204: None, 403: DetailSerializer}, summary="Remove a webhook")
    def delete(self, request: Request, slug: str, webhook_id: int) -> Response:
        user, member = _admin(request, slug)
        webhook = Webhook.objects.for_workspace(member.workspace).filter(pk=webhook_id).first()
        if webhook is None:
            raise Http404
        with transaction.atomic():
            audit.record(
                member.workspace,
                user,
                "webhook.delete",
                webhook,
                {"kind": webhook.kind, "repo": webhook.repo, "name": webhook.name},
            )
            webhook.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeliveryListView(APIView):
    @extend_schema(
        responses={200: DeliverySerializer(many=True), 403: DetailSerializer},
        summary="A webhook's latest deliveries and what became of them",
    )
    def get(self, request: Request, slug: str, webhook_id: int) -> Response:
        _, member = _admin(request, slug)
        webhook = Webhook.objects.for_workspace(member.workspace).filter(pk=webhook_id).first()
        if webhook is None:
            raise Http404
        found = webhook.deliveries.order_by("-pk")[:DELIVERIES_SHOWN]
        return Response(DeliverySerializer(found, many=True).data)


QUEUED = {"detail": "Queued."}


class GitHubDeliveryView(APIView):
    """Called by GitHub, not a person: no session (so no CSRF); the signature is the proof."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "hooks"

    @extend_schema(
        request=None,
        parameters=[
            OpenApiParameter("X-GitHub-Event", str, OpenApiParameter.HEADER, required=True),
            OpenApiParameter("X-Hub-Signature-256", str, OpenApiParameter.HEADER, required=True),
            OpenApiParameter("X-GitHub-Delivery", str, OpenApiParameter.HEADER),
        ],
        responses={200: DetailSerializer, 202: DetailSerializer, 400: DetailSerializer},
        summary="Receive a GitHub delivery (called by GitHub)",
    )
    def post(self, request: Request, token: str) -> Response:
        webhook = (
            Webhook.objects.filter(token=token, kind="github").select_related("channel").first()
        )
        if webhook is None:
            raise Http404
        body = request.body
        # Checked on the raw bytes before anything in them is read (AGENTS.md). Unsigned calls
        # are not logged, so nobody can fill the log without the secret.
        if not github.signature_ok(
            webhook.secret, body, request.headers.get("X-Hub-Signature-256")
        ):
            return Response(
                {"detail": "Signature does not match."}, status=status.HTTP_401_UNAUTHORIZED
            )
        event = request.headers.get("X-GitHub-Event", "")[:40]
        external_id = request.headers.get("X-GitHub-Delivery", "")[:64]
        if event == "ping":
            deliveries.finished(webhook, event, "ignored", "Connected.", external_id)
            return Response({"detail": "Connected."})
        try:
            payload = json.loads(body)
        except ValueError:
            deliveries.finished(webhook, event, "failed", "Not JSON.", external_id)
            return Response({"detail": "Not JSON."}, status=status.HTTP_400_BAD_REQUEST)
        text = github.describe(event, payload)
        if github.repository(payload) != webhook.repo:
            reason = "Another repository."
        elif text is None:
            reason = "Not an event that is posted."
        else:
            tasks.queue(webhook, event, text, external_id)
            return Response(QUEUED, status=status.HTTP_202_ACCEPTED)
        deliveries.finished(webhook, event, "ignored", reason, external_id)
        return Response({"detail": f"Ignored: {reason}"}, status=status.HTTP_202_ACCEPTED)


class IncomingDeliveryView(APIView):
    """Called by another tool with the secret URL; the URL is the proof (no session, no CSRF)."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (PerWebhookThrottle,)

    @extend_schema(
        request=IncomingSerializer,
        responses={202: DetailSerializer, 400: DetailSerializer, 409: DetailSerializer},
        summary="Post a message through an incoming webhook (called by other tools)",
    )
    def post(self, request: Request, token: str) -> Response:
        webhook = (
            Webhook.objects.filter(token=webhooks.digest(token), kind="incoming")
            .select_related("channel")
            .first()
        )
        if webhook is None:
            raise Http404
        serializer = IncomingSerializer(data=request.data)
        if not serializer.is_valid():
            deliveries.finished(webhook, "message", "failed", "No usable text.")
            raise ValidationError(serializer.errors)
        if webhook.channel.archived:
            deliveries.finished(webhook, "message", "ignored", "The channel is archived.")
            return Response({"detail": "The channel is archived."}, status=status.HTTP_409_CONFLICT)
        tasks.queue(webhook, "message", serializer.validated_data["text"])
        return Response(QUEUED, status=status.HTTP_202_ACCEPTED)
