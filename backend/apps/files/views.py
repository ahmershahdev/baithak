from typing import cast

from django.db import transaction
from django.http import FileResponse, Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.chat.access import channel_access
from apps.chat.models import ChannelMember
from apps.core import channels as rules
from apps.core import files as file_rules
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.files import links, storage
from apps.files.models import Attachment, Scan
from apps.files.serializers import AttachmentSerializer, UploadSerializer
from apps.files.tasks import scan_file
from apps.workspaces.access import membership

# A downloaded file must never run anything on this origin, even if a browser guesses its type.
FILE_CSP = "default-src 'none'; img-src 'self'; sandbox"


def _user(request: Request) -> User:
    return cast(User, request.user)


class UploadView(APIView):
    parser_classes = (MultiPartParser,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "upload"

    @extend_schema(
        request={"multipart/form-data": UploadSerializer},
        responses={201: AttachmentSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Upload a file to attach to your next message in this channel",
    )
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        allowed = rules.can_post(
            access.role, access.kind, is_member=access.is_member, archived=access.channel.archived
        )
        if not allowed:
            raise PermissionDenied("Join the channel to share files in it.")
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        content_type = None
        if 0 < upload.size <= file_rules.MAX_SIZE:
            content_type = file_rules.sniff(upload.read(file_rules.HEAD))
            upload.seek(0)
        refused = file_rules.problem(upload.size, content_type)
        if refused or content_type is None:
            raise ValidationError({"file": [refused]})
        key = storage.save(upload)
        with transaction.atomic():
            attachment = Attachment.objects.create(
                workspace=access.member.workspace,
                channel=access.channel,
                uploader=user,
                name=file_rules.safe_name(upload.name or ""),
                content_type=content_type,
                size=upload.size,
                storage_key=key,
            )
            transaction.on_commit(lambda: scan_file.delay(attachment.pk))
        attachment.workspace = access.member.workspace
        return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


class DownloadView(APIView):
    @extend_schema(
        responses={(200, "application/octet-stream"): bytes},
        summary="Download a file through its signed link",
    )
    def get(self, request: Request, slug: str, token: str) -> FileResponse:
        user = _user(request)
        member = membership(user, slug)
        signed = links.read(token)
        if signed is None:
            raise Http404
        attachment_id, variant = signed
        attachment = (
            Attachment.objects.for_workspace(member.workspace)
            .select_related("channel")
            .filter(pk=attachment_id)
            .first()
        )
        if attachment is None:
            raise Http404
        # The same rule as reading the channel; a file not yet sent is its uploader's alone.
        is_member = ChannelMember.objects.filter(channel=attachment.channel, user=user).exists()
        readable = rules.can_read(
            Role(member.role), ChannelKind(attachment.channel.kind), is_member=is_member
        )
        if not readable or (attachment.message_id is None and attachment.uploader_id != user.pk):
            raise Http404
        # Not scanned yet, or refused: there is nothing anyone may download.
        if attachment.scan != Scan.CLEAN:
            raise Http404
        if variant == links.PREVIEW:
            if not attachment.preview_key:
                raise Http404
            response = FileResponse(
                storage.open_file(attachment.preview_key, encrypted=attachment.encrypted),
                content_type="image/webp",
            )
        else:
            response = FileResponse(
                storage.open_file(attachment.storage_key, encrypted=attachment.encrypted),
                content_type=attachment.content_type,
                as_attachment=not file_rules.shown_inline(attachment.content_type),
                filename=attachment.name,
            )
            response.headers["Content-Length"] = str(attachment.size)
        response.headers["Content-Security-Policy"] = FILE_CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        # The link itself expires; the browser may keep what it fetched for an hour.
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response
