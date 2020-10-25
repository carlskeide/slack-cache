# coding=utf-8
import logging

from slackclient import SlackClient
from redis.client import Redis

logger = logging.getLogger(__name__)

__all__ = ["CachedSlack", "SlackError"]


class SlackError(Exception):
    pass


class CachedSlack(object):
    ttl = {
        "users": 60 * 60 * 24 * 5,
        "profile": 60 * 60 * 24 * 5,
        "channel": 60 * 60 * 16,
        "presence": 60 * 20,
    }

    def __init__(
            self,
            db: Redis,
            client: SlackClient,
            prefix: str = "SLACKCACHE"):

        self.db = db
        self.client = client
        self.prefix = prefix

    def _cache_key(self, *atoms: str) -> str:
        return ":".join([self.prefix] + atoms)

    def _slack(self, method: str, **kwargs) -> dict:
        logger.debug("Calling Slack method: %s, kwargs: %s", method, kwargs)
        response = self.client.api_call(method, **kwargs)

        if response["ok"] is not True:
            logger.error("Error during slack call. response: %s", response)

            raise SlackError("error: {}".format(response.get("error")))

        else:
            if "warning" in response:
                logger.warning("Slack method: %s raised a warning: %s",
                               method, response["warning"])

            return response

    def is_present(self, user_id: str) -> bool:
        """ Check whether a given USERID is marked as present """

        logger.debug("Checking presence for: %s", user_id)

        presence_key = self._cache_key('PRESENCE')

        cached_presence = self.db.hget(presence_key, user_id)
        if cached_presence:
            return (cached_presence == "active")

        logger.debug("Refreshing presence")
        response = self._slack("users.list", presence=True)

        user_presence = {u["id"]: u.get("presence", "away")
                         for u in response["members"]}

        self.db.hmset(presence_key, user_presence)
        self.db.expire(presence_key, self.ttl["presence"])

        return (user_presence.get(user_id) == "active")

    def user_name(self, user_id: str) -> str:
        """ Get the current username for USERID """

        logger.debug("Fetching user: %s", user_id)

        users_key = self._cache_key('USERS')

        cached_user = self.db.hget(users_key, user_id)
        if cached_user:
            return (cached_user
                if not self.db.sismember(self.ignored_key, user_id) else None)

        logger.info("Refreshing userlist")
        response = self._slack("users.list")

        all_users = {u["id"]: u["name"]
                     for u in response["members"]}

        self.db.hmset(users_key, all_users)
        self.db.expire(users_key, self.ttl["users"])

        ignored_users = [u["id"] for u in response["members"]
                         if (u["deleted"] or u.get("is_bot"))]

        ignored_users.append("slackbot")  # Slackbot, is_bot == False ... Wat?

        self.db.sadd(self.ignored_key, *ignored_users)
        self.db.expire(self.ignored_key, self.ttl["users"])

        return (all_users.get(user_id)
            if user_id not in ignored_users else None)

    def profile(self, user_id: str) -> dict:
        """ Fetch a slack user profile """
        logger.debug("Fetching profile: %s", user_id)

        profile_key = self._cache_key('PROFILE', str(user_id))

        cached_profile = self.db.hgetall(profile_key)
        if cached_profile:
            return cached_profile

        logger.info("Refreshing profile: %s", user_id)
        response = self._slack("users.info", user=user_id)

        profile = response["user"]["profile"]
        profile.update({})
        self.db.hmset(profile_key, profile)
        self.db.expire(profile_key, self.ttl["profile"])

        return profile

    def avatar(self, user_id: str, size: int = 192) -> str:
        logger.debug(u"Fetching avatar for user: %s", user_id)

        profile = self.profile(user_id)
        image_key = "image_{}".format(size)

        return profile[image_key]

    def channel_members(self, channel_id: str) -> list:
        """ Fetch all memebers of a channel """
        logger.debug("Fetching channel: {}".format(channel_id))

        channel_key = self._cache_key('CHANNEL', str(channel_id))

        cached_channel = self.db.smembers(channel_key)
        if cached_channel:
            return cached_channel

        logger.info("Refreshing channel: {}".format(channel_id))
        response = self._slack("channels.info", channel=channel_id)

        channel_members = response["channel"]["members"]
        self.db.sadd(channel_key, *channel_members)
        self.db.expire(channel_key, self.ttl["channel"])

        return channel_members
