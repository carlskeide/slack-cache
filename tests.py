# coding=utf-8
import logging
from unittest.mock import Mock

import pytest
from slack import WebClient
from redis.client import Redis

from slack_cache import CachedSlack, CachedSlackError

class TestCachedSlack(object):
    def setUp(self):
        self.mock_slack = Mock(WebClient)
        self.mock_redis = Mock(Redis)

        self.cache = CachedSlack(
            slack=self.mock_slack,
            redis=mock_redis
        )

    def test__cache_key(self):
        assert self.cache._cache_key("foo") == "SLACKCACHE:foo"
        assert self.cache._cache_key("foo", "bar") == "SLACKCACHE:foo:bar"

        cache = CachedSlack(
            slack=self.mock_slack,
            redis=mock_redis,
            prefix="foobar"
        )
        assert self.cache._cache_key("foo", "bar") == "foobar:foo:bar"

    def test__call_slack(self, caplog):
        ok = {
            "ok": True,
            "data": "foobar"
        }

        warning = {
            "ok": True,
            "warning": "bad",
            "data": "foobar"
        }

        error = {
            "ok": False,
            "error": "some_error"
        }

        self.mock_slack.api_call.return_value = ok
        assert self.cache._call_slack("some_method") == ok
        self.mock_slack.api_call.assert_called_with("some_method")
        assert self.cache._call_slack("some_method", json={"foo": "bar"}) == ok
        self.mock_slack.api_call.assert_called_with("some_method", json={"foo": "bar"})

        self.mock_slack.api_call.return_value = warning
        with caplog.at_level(logging.WARNING):
            assert self.cache._call_slack("some_method") == warning
        assert 'raised a warning' in caplog.text

        self.mock_slack.api_call.return_value = error
        with pytest.raises(CachedSlackError) as exc:
            self.cache._call_slack("some_method")
        assert "some_error" in str(exc.value)

        self.mock_slack.api_call.side_effect = KeyError("API")
        with pytest.raises(KeyError):
            self.cache._call_slack("some_method")

    def test__get_profile(self):
        pass

    def test_avatar(self):
        pass

    def test_user_name(self):
        pass

    def test_channel_members(self):
        pass
