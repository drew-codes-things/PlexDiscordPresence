import logging
import time

from pypresence import Presence
from pypresence.exceptions import PyPresenceException

logger = logging.getLogger(__name__)

MAX_IMAGE_URL_LENGTH = 256
MIN_TEXT_LENGTH = 2
MAX_TEXT_LENGTH = 128
ELLIPSIS = "..."


def resolve_poster_url(poster_url):
    if poster_url and len(poster_url) > MAX_IMAGE_URL_LENGTH:
        return None, True
    return poster_url, False


def fit_discord_text(text):
    text = str(text or "")
    if len(text) > MAX_TEXT_LENGTH:
        text = text[: MAX_TEXT_LENGTH - len(ELLIPSIS)] + ELLIPSIS
    return text.ljust(MIN_TEXT_LENGTH)


def build_activity_payload(now_playing, now=None):
    poster_url, poster_dropped = resolve_poster_url(now_playing["poster_url"])

    if now_playing["type"] == "movie":
        year = now_playing.get("year")
        details = f"{now_playing['title']} ({year})" if year else now_playing["title"]
        state = "Watching"
    else:
        details = now_playing["show_name"]
        season, episode = now_playing["season"], now_playing["episode"]
        if season is not None and episode is not None:
            state = f"S{season:02d}E{episode:02d} • {now_playing['title']}"
        else:
            state = now_playing["title"]

    if now_playing["is_paused"]:
        state = f"{state} (Paused)"

    payload = {"details": fit_discord_text(details), "state": fit_discord_text(state)}

    if poster_url:
        payload["large_image"] = poster_url

    if not now_playing["is_paused"]:
        current_time = time.time() if now is None else now
        start = current_time - (now_playing["view_offset_ms"] / 1000)
        payload["start"] = int(start)
        if now_playing["duration_ms"] > 0:
            payload["end"] = int(start + now_playing["duration_ms"] / 1000)

    return payload, poster_dropped


class PlexPresenceClient:
    def __init__(self, client_id, presence=None, reconnect_interval_seconds=15.0, time_source=time.time):
        self._presence = presence if presence is not None else Presence(client_id)
        self._reconnect_interval_seconds = reconnect_interval_seconds
        self._time_source = time_source
        self._connected = False
        self._last_connect_attempt = 0.0
        self._has_active_presence = False
        self._warned_oversized_poster = False

    def update(self, now_playing):
        if now_playing is None:
            self._clear()
            return

        if not self._ensure_connected():
            return

        payload, poster_dropped = build_activity_payload(now_playing, now=self._time_source())
        if poster_dropped and not self._warned_oversized_poster:
            logger.warning(
                "Poster URL exceeds Discord's %d-character image URL limit; omitting large_image.",
                MAX_IMAGE_URL_LENGTH,
            )
            self._warned_oversized_poster = True

        try:
            self._presence.update(**payload)
            self._has_active_presence = True
        except PyPresenceException as exc:
            logger.warning("Failed to update Discord presence: %s", exc)
            self._connected = False

    def close(self):
        if not self._connected:
            return
        try:
            self._presence.close()
        except PyPresenceException:
            pass
        self._connected = False

    def _ensure_connected(self):
        if self._connected:
            return True

        now = self._time_source()
        if now - self._last_connect_attempt < self._reconnect_interval_seconds:
            return False

        self._last_connect_attempt = now
        try:
            self._presence.connect()
            self._connected = True
            logger.info("Connected to Discord IPC.")
        except PyPresenceException as exc:
            logger.warning("Could not connect to Discord (is it running?): %s", exc)

        return self._connected

    def _clear(self):
        if not self._connected or not self._has_active_presence:
            return
        try:
            self._presence.clear()
        except PyPresenceException as exc:
            logger.warning("Failed to clear Discord presence: %s", exc)
            self._connected = False
        finally:
            self._has_active_presence = False
