import logging
from urllib.parse import urlsplit

from plexapi.myplex import MyPlexAccount

logger = logging.getLogger(__name__)

RELEVANT_STATES = ("playing", "paused", "stopped")


def connect_to_plex(token, server_name):
    account = MyPlexAccount(token=token)
    return account.resource(server_name).connect()


TMDB_ORIGINAL_SIZE = "/t/p/original/"
TMDB_PRESENCE_SIZE = "/t/p/w500/"


def public_poster_url(item):
    source = item.show() if item.type == "episode" else item
    for poster in source.posters():
        parts = urlsplit(poster.key or "")
        if parts.scheme == "https" and not parts.query:
            return poster.key.replace(TMDB_ORIGINAL_SIZE, TMDB_PRESENCE_SIZE, 1)
    return None


def normalize_item(item, view_offset_ms, is_paused, poster_url=None):
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
        "poster_url": poster_url,
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

    def __init__(self, server, callback):
        self._server = server
        self._callback = callback
        self._listener = None
        self._item_cache = {}
        self._poster_cache = {}
        self._last_session_key = None
        self._last_state = None

    def start(self):
        self._listener = self._server.startAlertListener(
            callback=self._handle_alert, callbackError=self._handle_error
        )

    def is_running(self):
        return self._listener is not None and self._listener.is_alive()

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
            poster_url=self._poster_for(item),
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

    def _poster_for(self, item):
        if item.ratingKey not in self._poster_cache:
            try:
                self._poster_cache[item.ratingKey] = public_poster_url(item)
            except Exception as exc:
                logger.warning("Failed to look up a poster for '%s': %s", item.title, exc)
                return None
        return self._poster_cache[item.ratingKey]

    def _handle_error(self, error):
        logger.warning("Plex notification listener error: %s", error)
