"""Builds the invented demo teams (demo_content.py) through the same services the app uses, so
sequence numbers, threads, mentions, unread counts and issue activity all hold together.

Dates are spread over the last `days` days. Seed users never get email (notify_by_email off,
addresses on the reserved .example domain).
"""

import random
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.channels import ChannelKind
from apps.core.issues import Priority, Status
from apps.core.roles import Role
from apps.issues.models import Issue, Label, Project
from apps.issues.services import create_issue
from apps.notifications.models import Notification
from apps.workspaces import audit
from apps.workspaces.demo_content import REACTIONS, REPLIES, TEAMS, ChannelPlan, Team
from apps.workspaces.models import AuditEvent, Member, Workspace

# Messages a channel gets on a busy weekday, at most; weekends are quieter.
BUSY_DAY = 6


def email_of(handle: str, team: Team) -> str:
    return f"{handle}@{team.slug}.example"


def existing() -> list[str]:
    """What a fresh seed would clash with: the demo workspaces, or a taken handle or email."""
    slugs = [team.slug for team in TEAMS]
    found = list(Workspace.objects.filter(slug__in=slugs).values_list("slug", flat=True))
    for team in TEAMS:
        for person in team.people:
            if User.objects.filter(username=person.handle).exists():
                found.append(f"@{person.handle}")
    return found


def remove() -> None:
    with transaction.atomic():
        Workspace.objects.filter(slug__in=[team.slug for team in TEAMS]).delete()
        for team in TEAMS:
            User.objects.filter(email__in=[email_of(p.handle, team) for p in team.people]).delete()


class Builder:
    def __init__(self, team: Team, password: str, days: int, rng: random.Random) -> None:
        self.team = team
        self.password = password
        self.days = days
        self.rng = rng
        self.users: dict[str, User] = {}
        self.channels: dict[str, Channel] = {}
        self.start = timezone.now() - timedelta(days=days)
        # The busiest channel after #general, where every third issue was first raised.
        self.talk = team.channels[1].name
        self.sources: dict[int, Message] = {}

    def build(self) -> Workspace:
        with transaction.atomic():
            workspace = self._workspace()
            for plan in self.team.channels:
                self._channel(workspace, plan)
            self._issues(workspace)
            self._settle(workspace)
        return workspace

    def _workspace(self) -> Workspace:
        for person in self.team.people:
            user = User(
                username=person.handle,
                email=email_of(person.handle, self.team),
                display_name=person.name,
                email_verified_at=self.start,
                notify_by_email=False,
                time_zone="Asia/Karachi",
            )
            user.set_password(self.password)
            user.save()
            self.users[person.handle] = user
        owner = self.users[self.team.people[0].handle]
        workspace = Workspace.objects.create(
            name=self.team.name, slug=self.team.slug, created_by=owner
        )
        audit.record(workspace, owner, "workspace.create", workspace, {"name": workspace.name})
        for person in self.team.people:
            member = Member.objects.create(
                workspace=workspace, user=self.users[person.handle], role=Role(person.role)
            )
            audit.record(workspace, owner, "member.add", member, {"role": person.role})
        Workspace.objects.filter(pk=workspace.pk).update(created_at=self.start)
        AuditEvent.objects.for_workspace(workspace).update(at=self.start)
        return workspace

    def _channel(self, workspace: Workspace, plan: ChannelPlan) -> None:
        owner = self.users[self.team.people[0].handle]
        handles = plan.members or [p.handle for p in self.team.people if p.role != "guest"]
        channel = Channel.objects.create(
            workspace=workspace,
            name=plan.name,
            kind=ChannelKind.PRIVATE if plan.private else ChannelKind.PUBLIC,
            topic=plan.topic,
            is_default=plan.name == "general",
            created_by=owner,
        )
        Channel.objects.filter(pk=channel.pk).update(created_at=self.start)
        ChannelMember.objects.bulk_create(
            ChannelMember(channel=channel, user=self.users[h]) for h in handles
        )
        self.channels[plan.name] = channel
        people = [self.users[h] for h in handles]
        raised = {self._issue_time(i): i for i in range(0, len(self.team.issues), 3)}
        moments = self._moments() + (list(raised) if plan.name == self.talk else [])
        for moment in sorted(moments):
            author = self.rng.choice(people)
            if plan.name == self.talk and moment in raised:
                index = raised[moment]
                title = self.team.issues[index]
                text = f"We should track this: {title}"
                self.sources[index] = self._post(channel, author, text, moment)
                continue
            message = self._post(channel, author, self._line(plan.lines, author, people), moment)
            roll = self.rng.random()
            if roll < 0.12:
                self._thread(channel, message, people, moment)
            elif roll < 0.3:
                for emoji in self.rng.sample(REACTIONS, self.rng.randint(1, 2)):
                    messages.react(message, self.rng.choice(people), emoji, on=True)

    def _moments(self) -> list[datetime]:
        """When a channel's messages were sent, oldest first, in Karachi office hours."""
        moments: list[datetime] = []
        for day in range(self.days):
            date = self.start + timedelta(days=day)
            busy = BUSY_DAY if date.weekday() < 5 else 1
            for _ in range(self.rng.randint(0, busy)):
                # 04:00 to 14:00 UTC is 9 to 7 in Karachi.
                minute = self.rng.randint(4 * 60, 14 * 60)
                moments.append(date.replace(hour=0, minute=0) + timedelta(minutes=minute))
        return sorted(moments)

    def _issue_time(self, index: int) -> datetime:
        return self.start + timedelta(days=self.days * index / len(self.team.issues), hours=6)

    def _line(self, lines: list[str], author: User, people: list[User]) -> str:
        others = [p for p in people if p != author] or people
        return self.rng.choice(lines).format(who="@" + self.rng.choice(others).username)

    def _post(
        self, channel: Channel, author: User, body: str, at: datetime, parent: Message | None = None
    ) -> Message:
        message, _ = messages.post(channel, author, body, parent=parent)
        Message.objects.filter(pk=message.pk).update(created_at=at)
        Notification.objects.filter(message=message).update(created_at=at)
        return message

    def _thread(self, channel: Channel, parent: Message, people: list[User], at: datetime) -> None:
        for step in range(self.rng.randint(1, 3)):
            when = at + timedelta(minutes=5 + 7 * step)
            author = self.rng.choice(people)
            self._post(channel, author, self._line(REPLIES, author, people), when, parent)
            Message.objects.filter(pk=parent.pk).update(last_reply_at=when)

    def _issues(self, workspace: Workspace) -> None:
        owner = self.users[self.team.people[0].handle]
        project = Project.objects.create(
            workspace=workspace,
            key=self.team.project_key,
            name=self.team.project_name,
            created_by=owner,
        )
        labels = [
            Label.objects.create(workspace=workspace, project=project, name=name, color=color)
            for name, color in self.team.labels
        ]
        workers = [self.users[p.handle] for p in self.team.people if p.role != "guest"]
        for index, title in enumerate(self.team.issues):
            at = self._issue_time(index)
            source = self.sources.get(index)
            author = source.author if source and source.author else self.rng.choice(workers)
            status = self.rng.choice(list(Status))
            data: dict[str, object] = {
                "title": title,
                "status": status,
                "priority": self.rng.choice(list(Priority)),
                "assignee": self.rng.choice([*workers, None]),
                "labels": self.rng.sample(labels, self.rng.randint(0, 2)),
            }
            if source is not None:
                data["message"] = source
            issue = create_issue(project, author, data)
            Issue.objects.filter(pk=issue.pk).update(
                created_at=at, closed_at=at + timedelta(days=2) if issue.closed_at else None
            )
            AuditEvent.objects.for_workspace(workspace).filter(
                model="issue", object_id=str(issue.pk)
            ).update(at=at)
            if issue.message_id is not None:
                Message.objects.filter(parent_id=issue.message_id, kind="activity").update(
                    created_at=at + timedelta(minutes=1)
                )

    def _settle(self, workspace: Workspace) -> None:
        """Everyone has read up to the end, except the owner in two channels, so the demo opens
        with something unread; only the last three days' notifications stay unread."""
        owner = self.users[self.team.people[0].handle]
        for channel in Channel.objects.for_workspace(workspace):
            ChannelMember.objects.filter(channel=channel).update(last_read_seq=channel.last_seq)
        for name in [plan.name for plan in self.team.channels[1:3]]:
            channel = Channel.objects.get(pk=self.channels[name].pk)
            ChannelMember.objects.filter(channel=channel, user=owner).update(
                last_read_seq=max(channel.last_seq - 4, 0)
            )
        Notification.objects.for_workspace(workspace).filter(
            created_at__lt=timezone.now() - timedelta(days=3)
        ).update(read_at=timezone.now())


def seed(password: str, days: int, seed_value: int) -> list[Workspace]:
    rng = random.Random(seed_value)  # noqa: S311 - invented demo data, not security
    return [Builder(team, password, days, rng).build() for team in TEAMS]
