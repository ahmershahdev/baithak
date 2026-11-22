# Run by `npm run screenshots` inside the backend container (manage.py shell reads it from
# stdin). Prints, as one line of JSON, a session for the demo owner and where the pictures are.
import json
from importlib import import_module

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY

from apps.accounts.models import User
from apps.chat.models import Channel, Message
from apps.issues.models import Issue

user = User.objects.get(email="amna@chai-and-code.example")
session = import_module(settings.SESSION_ENGINE).SessionStore()
session[SESSION_KEY] = str(user.pk)
session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
session[HASH_SESSION_KEY] = user.get_session_auth_hash()
session.create()
dev = Channel.objects.get(workspace__slug="chai-and-code", name="dev")
thread = (
    Message.objects.filter(channel=dev, parent=None, reply_count__gte=2, kind="message")
    .order_by("-seq")
    .first()
)
issue = (
    Issue.objects.filter(workspace__slug="chai-and-code", message__isnull=False)
    .order_by("-number")
    .first()
)
print(
    json.dumps(
        {
            "cookie": settings.SESSION_COOKIE_NAME,
            "session": session.session_key,
            "channel": f"/w/chai-and-code/c/{dev.pk}?thread={thread.seq}",
            "issue": f"/w/chai-and-code/projects/{issue.project.key}/issues/{issue.number}",
        }
    )
)
