# coding=utf-8
import logging

from slack import WebClient
from redis.client import Redis

logger = logging.getLogger(__name__)

__all__ = ["CachedSlack", ]


class CachedSlack(object):
    ttl = {
        "profile": 60 * 60,
        "channel": 60 * 60
    }

    def __init__(
            self,
            redis: Redis,
            slack: WebClient,
            prefix: str = "SLACKCACHE"):

        self.redis = redis
        self.slack = slack
        self.prefix = prefix

    def _cache_key(self, *atoms: str) -> str:
        return ":".join([self.prefix] + list(atoms))

    def _call_slack(self, method: str, **kwargs) -> dict:
        logger.debug("Calling Slack method: %s, kwargs: %s", method, kwargs)
        response = self.slack.api_call(method, **kwargs)

        if "warning" in response:
            logger.warning("Slack method: %s raised a warning: %s",
                           method, response["warning"])

        return response

    def _get_profile(self, user_id: str) -> dict:
        """ Fetch a user profile """
        logger.debug("Fetching profile: %s", user_id)

        profile_key = self._cache_key('PROFILE', str(user_id))

        cached_profile = self.redis.hgetall(profile_key)
        if cached_profile:
            return cached_profile

        logger.info("Refreshing profile: %s", user_id)
        response = self._call_slack(
            "users.profile.get",
            json={"user": user_id})

        profile = response["profile"]
        self.redis.hmset(profile_key, profile)
        self.redis.expire(profile_key, self.ttl["profile"])

        return profile

    def avatar(self, user_id: str, size: int = 192) -> str:
        """ Fetch a user's avatar URL """
        logger.debug("Fetching avatar for user: %s", user_id)

        profile = self._get_profile(user_id)
        image_key = "image_{}".format(size)
        return profile[image_key]

    def user_name(self, user_id: str, real_name: bool = False) -> str:
        """ Fetch a user's name """
        logger.debug("Fetching name for user: %s", user_id)

        profile = self._get_profile(user_id)
        return profile["real_name" if real_name else "display_name"]

    def channel_members(self, channel_id: str) -> list:
        """ Fetch all members of a channel """
        logger.debug("Fetching channel: {}".format(channel_id))

        channel_key = self._cache_key('CHANNEL', str(channel_id))

        cached_channel = self.redis.smembers(channel_key)
        if cached_channel:
            return cached_channel

        logger.info("Refreshing channel: {}".format(channel_id))
        response = self._call_slack(
            "conversations.members",
            json={"channel": channel_id})

        channel_members = response["members"]
        self.redis.sadd(channel_key, *channel_members)
        self.redis.expire(channel_key, self.ttl["channel"])

        return channel_members
