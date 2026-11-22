"""Recording deliveries and acting on them. Every delivery that passed its check gets a row:
finished at once when there is nothing to post, otherwise pending until a worker posts it
(queued by apps/integrations/tasks.py)."""

from django.utils import timezone

from apps.chat import messages
from apps.core.webhooks import gives_up
from apps.integrations.models import Webhook, WebhookDelivery


def finished(webhook: Webhook, event: str, status: str, detail: str, external_id: str = "") -> None:
    WebhookDelivery.objects.create(
        workspace_id=webhook.workspace_id,
        webhook=webhook,
        event=event,
        external_id=external_id,
        status=status,
        detail=detail,
        finished_at=timezone.now(),
    )


def _finish(delivery: WebhookDelivery, status: str, detail: str) -> None:
    delivery.status = status
    delivery.detail = detail[:200]
    delivery.text = ""
    delivery.finished_at = timezone.now()
    delivery.save()


def attempt(delivery: WebhookDelivery) -> bool:
    """Try to post a pending delivery once. Returns True when it should be tried again."""
    webhook = delivery.webhook
    delivery.attempts += 1
    if webhook.channel.archived:
        _finish(delivery, "ignored", "The channel is archived.")
        return False
    try:
        message, _ = messages.post(
            webhook.channel,
            None,
            delivery.text,
            # Fixed per delivery, so a retry after a post that did commit doesn't post twice.
            client_id=delivery.external_id or f"delivery-{delivery.pk}",
            kind="integration",
            sender_name="GitHub" if webhook.kind == "github" else webhook.name,
        )
    # Whatever went wrong (the database, Redis), the log says so and the delivery is retried.
    except Exception as error:
        problem = f"{type(error).__name__}: {error}"
        if gives_up(delivery.attempts):
            _finish(delivery, "failed", problem)
            return False
        delivery.detail = problem[:200]
        delivery.save(update_fields=["attempts", "detail"])
        return True
    delivery.message = message
    _finish(delivery, "posted", "")
    return False
