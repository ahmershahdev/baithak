from typing import Any

import pytest
from channels_redis.core import RedisChannelLayer  # type: ignore[import-untyped]
from django.core.exceptions import ImproperlyConfigured

from config.settings import base
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


def test_redis_reads_outlast_the_channel_layers_blocking_wait() -> None:
    config: Any = base.CHANNEL_LAYERS["default"]["CONFIG"]
    host = config["hosts"][0]

    assert host["socket_timeout"] > RedisChannelLayer.brpop_timeout


def test_the_channel_layer_pool_outgrows_redis_pys_default() -> None:
    config: Any = base.CHANNEL_LAYERS["default"]["CONFIG"]

    # redis-py 8 defaults to 100 and raises when they are all in use.
    assert config["hosts"][0]["max_connections"] >= 1000
