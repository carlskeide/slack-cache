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

    def test__cache_key(self):
        assert self.cache._cache_key("foo") == "SLACKCACHE:foo"
        assert self.cache._cache_key("foo", "bar") == "SLACKCACHE:foo:bar"

        cache = CachedSlack(
            slack=self.mock_slack,
            redis=self.mock_redis,
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

        self.mock_slack.api_call.return_value = ok
        assert self.cache._call_slack("some_method") == ok
        self.mock_slack.api_call.assert_called_with("some_method")
        assert self.cache._call_slack("some_method", json={"foo": "bar"}) == ok
        self.mock_slack.api_call.assert_called_with("some_method", json={"foo": "bar"})

        self.mock_slack.api_call.return_value = warning
        with caplog.at_level(logging.WARNING):
            assert self.cache._call_slack("some_method") == warning
        assert 'raised a warning' in caplog.text

        self.mock_slack.api_call.side_effect = SlackApiError("foo")
        with pytest.raises(SlackApiError):
            self.cache._call_slack("some_method")

    def test__get_profile(self):
        pass

    def test_avatar(self):
        mock_profile = SLACK_PROFILE["profile"]
        self.cache._get_profile = Mock(
            spec=CachedSlack._get_profile,
            return_value=mock_profile
        )

        assert self.cache.avatar("some_user") == mock_profile["image_192"]
        assert self.cache.avatar("some_user", 32) == mock_profile["image_32"]
        self.cache._get_profile.assert_called_with("some_user")

        with pytest.raises(KeyError):
            self.cache.avatar("some_user", 8)

    def test_user_name(self):
        mock_profile = SLACK_PROFILE["profile"]
        self.cache._get_profile = Mock(
            spec=CachedSlack._get_profile,
            return_value=mock_profile
        )

        assert self.cache.user_name("some_user") == mock_profile["display_name"]
        assert self.cache.user_name("some_user", real_name=True) == mock_profile["real_name"]
        self.mock_slack._get_profile.assert_called_with("some_user")

    def test_channel_members(self):
        pass
