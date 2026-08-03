"""Watches Plex for playback state changes over its websocket notification
feed and normalizes them into a plain dict presence.py can turn into a
Discord Activity payload.

Unlike polling the REST `/status/sessions` endpoint, the websocket feed
works for non-owner (shared/friend) Plex accounts too: Plex only relays
"playing" notifications for sessions the connecting account already has
visibility into, so no session-list lookup (which non-owners are forbidden
from making) is needed to know a notification is about "your" playback.
"""

import logging

from plexapi.myplex import MyPlexAccount

logger = logging.getLogger(__name__)

RELEVANT_STATES = ("playing", "paused", "stopped")


def connect_to_plex(token, server_name):
    account = MyPlexAccount(token=token)
    return account.resource(server_name).connect()


def normalize_item(item, view_offset_ms, is_paused):
    media_type = item.type
    if media_type not in ("movie", "episode"):
        return None

    normalized = {
        "title": item.title,
        "type": media_type,
        "show_name": None,
        "season": None,
        "episode": None,
        "year": item.year,
        "poster_url": item.thumbUrl,
        "duration_ms": item.duration or 0,
        "view_offset_ms": view_offset_ms or 0,
        "is_paused": is_paused,
    }

    if media_type == "episode":
        normalized["show_name"] = item.grandparentTitle
        normalized["season"] = item.parentIndex
        normalized["episode"] = item.index

    return normalized


class PlexSessionWatcher:
    """Turns a server's websocket notification feed into now-playing dicts
    delivered to `callback`. `callback` receives `None` when playback stops.
    """

    def __init__(self, server, callback):
        self._server = server
        self._callback = callback
        self._listener = None
        self._item_cache = {}
        self._last_session_key = None
        self._last_state = None

    def start(self):
        self._listener = self._server.startAlertListener(
            callback=self._handle_alert, callbackError=self._handle_error
        )

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _handle_alert(self, data):
        if data.get("type") != "playing":
            return

        notifications = data.get("PlaySessionStateNotification") or []
        if not notifications:
            return

        notification = notifications[0]
        state = notification.get("state")
        if state not in RELEVANT_STATES:
            return

        session_key = notification.get("sessionKey")
        if session_key != self._last_session_key:
            if state != "playing" and self._last_state == "playing":
                return
            self._item_cache = {}

        self._last_session_key = session_key
        self._last_state = state

        if state == "stopped":
            self._callback(None)
            return

        item = self._fetch_item(notification.get("ratingKey"))
        if item is None:
            return

        now_playing = normalize_item(
            item,
            view_offset_ms=notification.get("viewOffset", 0),
            is_paused=(state == "paused"),
        )
        if now_playing is not None:
            self._callback(now_playing)

    def _fetch_item(self, rating_key):
        if rating_key is None:
            return None
        if rating_key in self._item_cache:
            return self._item_cache[rating_key]
        try:
            item = self._server.fetchItem(int(rating_key))
        except Exception as exc:
            logger.warning("Failed to fetch metadata for ratingKey %s: %s", rating_key, exc)
            return None
        self._item_cache[rating_key] = item
        return item

    def _handle_error(self, error):
        logger.warning("Plex notification listener error: %s", error)
