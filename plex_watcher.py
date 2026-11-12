import logging
from urllib.parse import urlsplit

from plexapi.exceptions import Unauthorized
from plexapi.myplex import MyPlexAccount

logger = logging.getLogger(__name__)

RELEVANT_STATES = ("playing", "paused", "stopped")


def connect_to_plex(token, server_name):
    account = MyPlexAccount(token=token)
    server = account.resource(server_name).connect()
    return server, account_names(account)


def account_names(account):
    return tuple(name for name in (account.username, account.title) if name)


TMDB_ORIGINAL_SIZE = "/t/p/original/"
TMDB_PRESENCE_SIZE = "/t/p/w500/"
PLEX_SERVER_HOST_SUFFIX = ".plex.direct"


def is_public_image_url(url):
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    return (
        parts.scheme == "https"
        and bool(host)
        and not host.endswith(PLEX_SERVER_HOST_SUFFIX)
        and not parts.query
        and not parts.fragment
        and parts.username is None
        and parts.password is None
    )


def public_poster_url(item):
    source = item.show() if item.type == "episode" else item
    for poster in source.posters():
        if is_public_image_url(poster.key):
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

    def __init__(self, server, callback, account_names=()):
        self._server = server
        self._callback = callback
        self._account_names = frozenset(account_names)
        self._listener = None
        self._item_cache = {}
        self._poster_cache = {}
        self._session_ownership = {}
        self._sessions_visible = True
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

        for notification in data.get("PlaySessionStateNotification") or []:
            self._handle_notification(notification)

    def _handle_notification(self, notification):
        state = notification.get("state")
        if state not in RELEVANT_STATES:
            return

        session_key = notification.get("sessionKey")
        if not self._is_own_session(session_key):
            return

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

    def _is_own_session(self, session_key):
        if not self._sessions_visible:
            return True
        if session_key in self._session_ownership:
            return self._session_ownership[session_key]
        try:
            sessions = self._server.sessions()
        except Unauthorized:
            logger.info("This account cannot list server sessions; Plex only sends it its own playback.")
            self._sessions_visible = False
            return True
        except Exception as exc:
            logger.warning("Could not check who owns Plex session %s: %s", session_key, exc)
            return False
        match = next((entry for entry in sessions if str(entry.sessionKey) == str(session_key)), None)
        if match is None:
            return False
        is_own = not self._account_names.isdisjoint(match.usernames)
        self._session_ownership[session_key] = is_own
        return is_own

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
