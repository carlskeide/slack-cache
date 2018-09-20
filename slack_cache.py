# coding=utf-8
import logging

import slackclient

logger = logging.getLogger(__name__)

__all__ = ["CachedAPI"]


class CachedAPI(object):
    def __init__(self, db, token, prefix="SLACK"):
        self.db = db

        self.ttl = {
            "users": 60 * 60 * 24 * 5,
            "profile": 60 * 60 * 24 * 5,
            "channel": 60 * 60 * 16,
            "presence": 60 * 20,
        }

        self.prefix = prefix
        self.client = slackclient.SlackClient(token)

    def cache_key(self, *atoms):
        return ":".join([self.prefix] + atoms)

    def slack(self, *args, **kwargs):
        logger.debug(u"Slack API call, args: {}, kwargs: {}".format(
                  args, kwargs))

        response = self.client.api_call(*args, **kwargs)
        if response["ok"] is not True:
            logger.error(
                u"Error during slack call. response: {}".format(response))

            raise Exception("Slack API return an error.")

        return response

    def is_present(self, user_id):
        logger.debug(u"Checking presence for: {}".format(user_id))

        presence_key = self.cache_key('PRESENCE')

        cached_presence = self.db.hget(presence_key, user_id)
        if cached_presence:
            return (cached_presence == "active")

        logger.debug(u"Refreshing presence")
        response = self.slack("users.list", presence=True)

        user_presence = {u["id"]: u.get("presence", "away")
                         for u in response["members"]}

        self.db.hmset(presence_key, user_presence)
        self.db.expire(presence_key, self.ttl["presence"])

        return (user_presence.get(user_id) == "active")

    def user(self, user_id):
        logger.debug(u"Fetching user: {}".format(user_id))

        users_key = self.cache_key('USERS')

        cached_user = self.db.hget(users_key, user_id)
        if cached_user:
            return (cached_user
                if not self.db.sismember(self.ignored_key, user_id) else None)

        logger.info(u"Refreshing userlist")
        response = self.slack("users.list")

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

    def profile(self, user_id):
        logger.debug(u"Fetching profile: {}".format(user_id))

        profile_key = self.cache_key('PROFILE', str(user_id))

        cached_profile = self.db.hgetall(profile_key)
        if cached_profile:
            return cached_profile

        logger.info(u"Refreshing profile: {}".format(user_id))
        response = self.slack("users.info", user=user_id)

        profile = response["user"]["profile"]
        profile.update({})
        self.db.hmset(profile_key, profile)
        self.db.expire(profile_key, self.ttl["profile"])

        return profile

    def channel_members(self, channel_id):
        logger.debug(u"Fetching channel: {}".format(channel_id))

        channel_key = self.cache_key('CHANNEL', str(channel_id))

        cached_channel = self.db.smembers(channel_key)
        if cached_channel:
            return cached_channel

        logger.info(u"Refreshing channel: {}".format(channel_id))
        response = self.slack("channels.info", channel=channel_id)

        channel_members = response["channel"]["members"]
        self.db.sadd(channel_key, *channel_members)
        self.db.expire(channel_key, self.ttl["channel"])

        return channel_members
