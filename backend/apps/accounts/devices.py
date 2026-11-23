"""Signed-in devices: one row per session, so a person can see where they are signed in and
sign any of it out (docs/architecture.md, Signed-in devices)."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from apps.accounts.models import Device, User
from apps.chat.events import user_group
from apps.core import devices as rules

SESSION_KEY = "device"
# last_seen_at is written at most this often per device, not on every request.
SEEN_EVERY = timedelta(minutes=5)


def _new(request: HttpRequest, user: User) -> Device:
    agent = request.META.get("HTTP_USER_AGENT", "")[: rules.MAX_AGENT]
    device = Device.objects.create(user=user, user_agent=agent, last_seen_at=timezone.now())
    request.session[SESSION_KEY] = device.pk
    return device


@receiver(user_logged_in)
def _signed_in(sender: Any, request: HttpRequest | None, user: User, **kwargs: Any) -> None:
    if request is not None:
        _new(request, user)


@receiver(user_logged_out)
def _signed_out(sender: Any, request: HttpRequest | None, user: User | None, **kwargs: Any) -> None:
    device_id = request.session.get(SESSION_KEY) if request is not None else None
    # A deleted account signs out after its row (and with it every device) is gone.
    if device_id is not None and user is not None and user.pk is not None:
        Device.objects.filter(pk=device_id, user=user).delete()


def _tell_sockets(user_id: int, devices: list[int] | None) -> None:
    """Open sockets of these devices (or all of the person's, for None) close."""

    def send() -> None:
        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(
                user_group(user_id), {"type": "chat.signed_out", "devices": devices}
            )

    transaction.on_commit(send)


def end(user: User, device_id: int) -> bool:
    gone = Device.objects.filter(pk=device_id, user=user).delete()[0] > 0
    if gone:
        _tell_sockets(user.pk, [device_id])
    return gone


def end_others(user: User, keep: int | None) -> int:
    others = Device.objects.filter(user=user)
    if keep is not None:
        others = others.exclude(pk=keep)
    ids = list(others.values_list("pk", flat=True))
    others.delete()
    if ids:
        _tell_sockets(user.pk, ids)
    return len(ids)


def end_all(user: User) -> None:
    Device.objects.filter(user=user).delete()
    _tell_sockets(user.pk, None)


@receiver(pre_save, sender=User)
def _deactivated(sender: Any, instance: User, **kwargs: Any) -> None:
    if instance.pk is None or instance.is_active:
        return
    if User.objects.filter(pk=instance.pk, is_active=True).exists():
        end_all(instance)


class DeviceMiddleware:
    """After AuthenticationMiddleware: a session whose device row is gone is signed out. A
    session from before devices existed gets a row on its next request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = request.user
        if isinstance(user, User):
            device_id = request.session.get(SESSION_KEY)
            if device_id is None:
                _new(request, user)
            else:
                seen = (
                    Device.objects.filter(pk=device_id, user=user)
                    .values_list("last_seen_at", flat=True)
                    .first()
                )
                if seen is None:
                    logout(request)
                    request.user = AnonymousUser()
                elif timezone.now() - seen > SEEN_EVERY:
                    Device.objects.filter(pk=device_id).update(last_seen_at=timezone.now())
        return self.get_response(request)


def prune() -> int:
    """Rows whose session has run out: nothing will sign them out otherwise."""
    cutoff = timezone.now() - timedelta(seconds=settings.SESSION_COOKIE_AGE)
    return Device.objects.filter(last_seen_at__lt=cutoff).delete()[0]
