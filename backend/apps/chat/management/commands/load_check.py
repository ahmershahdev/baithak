"""The M4 load check: many clients in one channel, message delivery time measured.

Runs against a running server (the dev stack, or a staging deploy). It makes an invented
workspace, "load-check", with users load-0001 and up, signs each in with a session of its own,
opens one real WebSocket per user, then posts messages the normal way (saved, then broadcast)
and times each one from the moment it is sent until every client has it.

    python manage.py load_check --clients 500 --messages 20
"""

import asyncio
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember
from apps.chat.services import create_default_channel
from apps.core.roles import Role
from apps.workspaces.models import Member, Workspace

SLUG = "load-check"
# Handshakes at once. Each costs session, user and channel queries on Django's one database
# thread plus presence work in Redis, so a crowd all at once mostly measures that queue.
CONNECTING_AT_ONCE = 10


def percentile(ordered: list[float], fraction: float) -> float:
    """Nearest-rank percentile of an already sorted list."""
    if not ordered:
        return math.nan
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def summarize(latencies_ms: list[float]) -> dict[str, float]:
    ordered = sorted(latencies_ms)
    return {
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "p99": percentile(ordered, 0.99),
        "max": ordered[-1] if ordered else math.nan,
    }


@dataclass
class Run:
    clients: int
    channel_id: int
    connected: int = 0
    failed: int = 0
    # Connected, then closed by the server before the run ended.
    dropped: int = 0
    connect_seconds: float = 0.0
    sent: dict[int, float] = field(default_factory=dict)
    arrivals: dict[int, list[float]] = field(default_factory=lambda: defaultdict(list))


class Command(BaseCommand):
    help = "Open many WebSockets in one channel and measure message delivery time."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--clients", type=int, default=500)
        parser.add_argument("--messages", type=int, default=20)
        parser.add_argument("--interval", type=float, default=0.5, help="Seconds between sends.")
        parser.add_argument(
            "--settle",
            type=float,
            default=10.0,
            help="Seconds to wait after connecting: every join is announced to everyone (presence),"
            " and messages sent before that drains measure the joins, not delivery.",
        )
        parser.add_argument("--url", default="ws://127.0.0.1:8000")
        parser.add_argument("--origin", default="http://localhost")
        parser.add_argument("--cleanup", action="store_true", help="Delete the load-check data.")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["cleanup"]:
            self._cleanup()
            return
        owner, channel, keys = self._prepare(options["clients"])
        run = Run(clients=options["clients"], channel_id=channel.pk)
        started = time.perf_counter()
        asyncio.run(self._run(run, owner, channel, keys, options))
        self._report(run, options["messages"], time.perf_counter() - started)

    def _prepare(self, count: int) -> tuple[User, Channel, list[str]]:
        owner, _ = User.objects.get_or_create(
            username="load-owner",
            defaults={"email": "load-owner@example.invalid", "email_verified_at": timezone.now()},
        )
        workspace, created = Workspace.objects.get_or_create(
            slug=SLUG, defaults={"name": "Load check", "created_by": owner}
        )
        if created:
            Member.objects.create(workspace=workspace, user=owner, role=Role.OWNER)
            create_default_channel(workspace, owner)
        channel = Channel.objects.for_workspace(workspace).get(is_default=True)
        names = [f"load-{number:04d}" for number in range(1, count + 1)]
        existing = set(User.objects.filter(username__in=names).values_list("username", flat=True))
        new = []
        for name in names:
            if name not in existing:
                user = User(
                    username=name,
                    email=f"{name}@example.invalid",
                    email_verified_at=timezone.now(),
                    # No password at all: these accounts can only be signed in from here.
                    notify_by_email=False,
                )
                user.set_unusable_password()
                new.append(user)
        User.objects.bulk_create(new)
        users = list(User.objects.filter(username__in=names))
        Member.objects.bulk_create(
            [Member(workspace=workspace, user=u, role=Role.MEMBER) for u in users],
            ignore_conflicts=True,
        )
        ChannelMember.objects.bulk_create(
            [ChannelMember(channel=channel, user=u, last_read_seq=channel.last_seq) for u in users],
            ignore_conflicts=True,
        )
        store = import_module(settings.SESSION_ENGINE).SessionStore
        keys = []
        for user in users:
            session = store()
            session[SESSION_KEY] = str(user.pk)
            session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
            session[HASH_SESSION_KEY] = user.get_session_auth_hash()
            session.create()
            keys.append(session.session_key)
        return owner, channel, keys

    async def _run(
        self, run: Run, owner: User, channel: Channel, keys: list[str], options: dict[str, Any]
    ) -> None:
        from websockets.asyncio.client import connect
        from websockets.exceptions import WebSocketException

        url = f"{options['url']}/ws/workspaces/{SLUG}/"
        gate = asyncio.Semaphore(CONNECTING_AT_ONCE)
        all_in = asyncio.Event()
        done = asyncio.Event()
        expected = options["messages"]

        async def client(key: str) -> None:
            try:
                async with gate:
                    socket = await connect(
                        url,
                        origin=options["origin"],
                        additional_headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={key}"},
                        open_timeout=180,
                        max_queue=None,
                    )
            except (OSError, WebSocketException, TimeoutError):
                count_in(failed=True)
                return
            try:
                async with socket:
                    async for raw in socket:
                        event = json.loads(raw)
                        if event["type"] == "subscribed":
                            count_in(failed=False)
                        elif event["type"] == "message" and event["channel"] == run.channel_id:
                            seq = event["message"]["seq"]
                            # It can land before post() returns and its send time is noted.
                            if seq is not None:
                                run.arrivals[seq].append(time.perf_counter())
                        if done.is_set():
                            return
            except WebSocketException:
                run.dropped += 1

        def count_in(*, failed: bool) -> None:
            if failed:
                run.failed += 1
            else:
                run.connected += 1
            if run.connected + run.failed == run.clients:
                all_in.set()

        tasks = [asyncio.create_task(client(key)) for key in keys]
        connecting = time.perf_counter()
        await asyncio.wait_for(all_in.wait(), timeout=900)
        run.connect_seconds = time.perf_counter() - connecting
        self.stdout.write(
            f"{run.connected} connected, {run.failed} failed in {run.connect_seconds:.1f} s. "
            "Settling."
        )
        await asyncio.sleep(options["settle"])
        self.stdout.write("Sending.")
        post = sync_to_async(messages.post)
        for number in range(expected):
            before = time.perf_counter()
            message, _ = await post(channel, owner, f"load check {number + 1}")
            if message.seq is not None:
                run.sent[message.seq] = before
            await asyncio.sleep(options["interval"])
        # Let the last messages land.
        deadline = time.perf_counter() + 15
        while time.perf_counter() < deadline:
            if all(len(run.arrivals[seq]) >= run.connected for seq in run.sent):
                break
            await asyncio.sleep(0.1)
        done.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _report(self, run: Run, expected: int, seconds: float) -> None:
        latencies = [
            (arrived - run.sent[seq]) * 1000
            for seq, times in run.arrivals.items()
            if seq in run.sent
            for arrived in times
        ]
        wanted = run.connected * len(run.sent)
        stats = summarize(latencies)
        self.stdout.write(
            f"Clients: {run.connected} connected of {run.clients} ({run.failed} failed)\n"
            f"Messages: {len(run.sent)} of {expected}\n"
            f"Deliveries: {len(latencies)} of {wanted}\n"
            f"Delivery time (send to arrival), ms: p50 {stats['p50']:.1f}, "
            f"p95 {stats['p95']:.1f}, p99 {stats['p99']:.1f}, max {stats['max']:.1f}\n"
            f"Whole run: {seconds:.1f} s"
        )

    def _cleanup(self) -> None:
        Workspace.objects.filter(slug=SLUG).delete()
        deleted, _ = User.objects.filter(username__startswith="load-").delete()
        self.stdout.write(f"Removed the load-check workspace and {deleted} rows.")
