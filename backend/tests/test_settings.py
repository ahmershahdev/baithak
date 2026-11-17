import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import env, env_list


def test_env_reads_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAITHAK_TEST_VALUE", "set")

    assert env("BAITHAK_TEST_VALUE", "default") == "set"


def test_env_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAITHAK_TEST_VALUE", raising=False)

    assert env("BAITHAK_TEST_VALUE", "default") == "default"


def test_env_without_default_requires_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAITHAK_TEST_VALUE", raising=False)

    with pytest.raises(ImproperlyConfigured, match="BAITHAK_TEST_VALUE"):
        env("BAITHAK_TEST_VALUE")


def test_env_list_splits_and_drops_blanks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAITHAK_TEST_LIST", " a.example, ,b.example ")

    assert env_list("BAITHAK_TEST_LIST") == ["a.example", "b.example"]
