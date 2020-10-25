# coding=utf-8
import logging
from unittest import TestCase
from unittest.mock import Mock

import pytest
from slack import WebClient
from slack.errors import SlackApiError
from redis.client import Redis

from slack_cache import CachedSlack

# https://api.slack.com/methods/users.profile.get
SLACK_PROFILE =  {
    "ok": True,
    "profile": {
        "avatar_hash": "ge3b51ca72de",
        "status_text": "Print is dead",
        "status_emoji": ":books:",
        "status_expiration": 0,
        "real_name": "Egon Spengler",
        "display_name": "spengler",
        "real_name_normalized": "Egon Spengler",
        "display_name_normalized": "spengler",
        "email": "spengler@ghostbusters.example.com",
        "image_original": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "image_24": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "image_32": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "image_48": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "image_72": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "image_192": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "image_512": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
        "team": "T012AB3C4"
    }
}

# https://api.slack.com/methods/conversations.members
SLACK_CONVERSATION_MEMBERS ={
    "ok": True,
    "members": [
        "U023BECGF",
        "U061F7AUR",
        "W012A3CDE"
    ],
    "response_metadata": {
        "next_cursor": "e3VzZXJfaWQ6IFcxMjM0NTY3fQ=="
    }
}


class TestCachedSlack(TestCase):
    def setUp(self):
        self.mock_slack = Mock(WebClient)
        self.mock_redis = Mock(Redis)

        self.cache = CachedSlack(
            slack=self.mock_slack,
            redis=self.mock_redis
        )

    # TODO: migrate from TestCase
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test__cache_key(self):
        assert self.cache._cache_key("foo") == "SLACKCACHE:foo"
        assert self.cache._cache_key("foo", "bar") == "SLACKCACHE:foo:bar"

        cache = CachedSlack(
            slack=self.mock_slack,
            redis=self.mock_redis,
            prefix="foobar"
        )
        assert cache._cache_key("foo", "bar") == "foobar:foo:bar"

    def test__call_slack(self):
        ok = {
            "ok": True,
            "data": "foobar"
        }

        warning = {
            "ok": True,
            "warning": "bad",
            "data": "foobar"
        }

        self.mock_slack.api_call.return_value = ok
        assert self.cache._call_slack("some_method") == ok
        self.mock_slack.api_call.assert_called_with("some_method")
        assert self.cache._call_slack("some_method", json={"foo": "bar"}) == ok
        self.mock_slack.api_call.assert_called_with("some_method", json={"foo": "bar"})

        self.mock_slack.api_call.return_value = warning
        with self._caplog.at_level(logging.WARNING):
            assert self.cache._call_slack("some_method") == warning
        assert 'raised a warning' in self._caplog.text

        self.mock_slack.api_call.side_effect = SlackApiError("foo", response={"ok": False, "error": "foo"})
        with pytest.raises(SlackApiError):
            self.cache._call_slack("some_method")

    def test__get_profile(self):
        cache_key = "SLACKCACHE:PROFILE:some_user"
        self.mock_redis.hgetall.return_value = {"foo": "bar"}

        assert self.cache._get_profile("some_user") == {"foo": "bar"}
        self.mock_redis.hgetall.assert_called_with(cache_key)
        self.mock_slack.api_call.assert_not_called()

        self.mock_redis.hgetall.return_value = {}
        self.mock_slack.api_call.return_value = SLACK_PROFILE
        assert self.cache._get_profile("some_user") == SLACK_PROFILE["profile"]
        self.mock_slack.api_call.assert_called_with(
            "users.profile.get", json={"user": "some_user"})
        self.mock_redis.hmset.assert_called_with(cache_key, SLACK_PROFILE["profile"])
        self.mock_redis.expire.assert_called_with(cache_key, 3600)

    def test_avatar(self):
        mock_profile = SLACK_PROFILE["profile"]
        self.cache._get_profile = Mock(return_value=mock_profile)

        assert self.cache.avatar("some_user") == mock_profile["image_192"]
        self.cache._get_profile.assert_called_with("some_user")
        assert self.cache.avatar("some_user", 32) == mock_profile["image_32"]

        with pytest.raises(KeyError):
            self.cache.avatar("some_user", 8)

    def test_user_name(self):
        mock_profile = SLACK_PROFILE["profile"]
        self.cache._get_profile = Mock(return_value=mock_profile)

        assert self.cache.user_name("some_user") == mock_profile["display_name"]
        assert self.cache.user_name("some_user", real_name=True) == mock_profile["real_name"]
        self.cache._get_profile.assert_called_with("some_user")

    def test_channel_members(self):
        cache_key = "SLACKCACHE:CHANNEL:some_channel"
        self.mock_redis.smembers.return_value = ["foo", "bar"]

        assert self.cache.channel_members("some_channel") == ["foo", "bar"]
        self.mock_redis.smembers.assert_called_with(cache_key)
        self.mock_slack.api_call.assert_not_called()

        self.mock_redis.smembers.return_value = []
        self.mock_slack.api_call.return_value = SLACK_CONVERSATION_MEMBERS
        assert self.cache.channel_members("some_channel") == SLACK_CONVERSATION_MEMBERS["members"]
        self.mock_slack.api_call.assert_called_with(
            "conversations.members", json={"channel": "some_channel"})
        self.mock_redis.sadd.assert_called_with(cache_key, *SLACK_CONVERSATION_MEMBERS["members"])
        self.mock_redis.expire.assert_called_with(cache_key, 3600)
