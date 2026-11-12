import logging
import os
import sys
import time

from dotenv import load_dotenv

from plex_watcher import PlexSessionWatcher, connect_to_plex
from presence import PlexPresenceClient
from first_run import run_first_time_setup


def _resolve_base_dir():
    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        candidate = os.path.dirname(appimage_path)
    elif getattr(sys, "frozen", False):
        candidate = os.path.dirname(sys.executable)
    else:
        candidate = os.path.dirname(os.path.abspath(__file__))

    if os.access(candidate, os.W_OK):
        return candidate

    config_dir = os.path.expanduser("~/.config/plexdiscordpresence")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


BASE_DIR = _resolve_base_dir()
ENV_PATH = os.path.join(BASE_DIR, ".env")

DEFAULT_DISCORD_CLIENT_ID = "1533953665763901572"
RECONNECT_DELAY_SECONDS = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def start_watching(server, names, presence_client):
    watcher = PlexSessionWatcher(server, callback=presence_client.update, account_names=names)
    watcher.start()
    return watcher


def main():
    load_dotenv(ENV_PATH)

    token = os.getenv("PLEX_USER_TOKEN")
    server_name = os.getenv("PLEX_SERVER_NAME")
    if not token or not server_name:
        token, server_name = run_first_time_setup(ENV_PATH)

    client_id = os.getenv("DISCORD_CLIENT_ID") or DEFAULT_DISCORD_CLIENT_ID

    server, names = connect_to_plex(token, server_name)
    presence_client = PlexPresenceClient(client_id)
    watcher = start_watching(server, names, presence_client)

    logger.info("Plex Discord presence started. Listening for playback events.")

    try:
        while True:
            time.sleep(1)
            if not watcher.is_running():
                watcher = reconnect(token, server_name, presence_client, watcher)
    except KeyboardInterrupt:
        logger.info("Shutting down.")
    finally:
        watcher.stop()
        presence_client.close()


def reconnect(token, server_name, presence_client, old_watcher):
    old_watcher.stop()
    presence_client.update(None)
    while True:
        logger.warning("Lost the Plex connection; retrying in %ds.", RECONNECT_DELAY_SECONDS)
        time.sleep(RECONNECT_DELAY_SECONDS)
        try:
            server, names = connect_to_plex(token, server_name)
        except Exception as exc:
            logger.warning("Reconnect failed: %s", exc)
            continue
        logger.info("Reconnected to Plex.")
        return start_watching(server, names, presence_client)


if __name__ == "__main__":
    main()
