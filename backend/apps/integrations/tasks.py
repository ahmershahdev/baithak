from datetime import timedelta
from typing import Any

from celery import Task, shared_task
from django.utils import timezone

from apps.core.webhooks import KEEP_DAYS, retry_delay
from apps.integrations import deliveries
from apps.integrations.models import WebhookDelivery


@shared_task(bind=True, max_retries=None)
def deliver(self: Task[Any, Any], delivery_id: int) -> None:
    # Only pending ones: a duplicate task for a finished delivery does nothing.
    delivery = (
        WebhookDelivery.objects.select_related("webhook__channel")
        .filter(pk=delivery_id, status="pending")
        .first()
    )
    if delivery is not None and deliveries.attempt(delivery):
        raise self.retry(countdown=retry_delay(delivery.attempts))


@shared_task
def prune_deliveries() -> None:
    cutoff = timezone.now() - timedelta(days=KEEP_DAYS)
    WebhookDelivery.objects.filter(finished_at__lt=cutoff).delete()
