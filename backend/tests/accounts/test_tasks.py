from smtplib import SMTPException
from typing import Any

import pytest
from celery import Task

from apps.accounts import tasks

# Eager mode raises celery's Retry instead of running the retry, so these check the settings a
# worker uses to retry.
EMAIL_TASKS = [
    tasks.send_verification_email,
    tasks.send_password_reset_email,
    tasks.send_account_exists_email,
]


@pytest.mark.parametrize("task", EMAIL_TASKS)
def test_email_tasks_retry_with_backoff_when_sending_fails(task: Task[Any, Any]) -> None:
    # celery-types does not declare the autoretry options, hence getattr.
    assert getattr(task, "autoretry_for") == (SMTPException, OSError)  # noqa: B009
    assert getattr(task, "retry_backoff") is True  # noqa: B009
    assert task.max_retries == 5
