import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError


@pytest.mark.django_db
def test_email_is_unique() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(username="amna", email="amna@example.com", password="x")

    with pytest.raises(IntegrityError):
        user_model.objects.create_user(username="bilal", email="amna@example.com", password="x")
