from types import SimpleNamespace

from plexapi.exceptions import Unauthorized

import plex_watcher
from plex_watcher import PlexSessionWatcher

OWNER = "drew"


def media(rating_key, title):
    return SimpleNamespace(
        ratingKey=rating_key,
        type="movie",
        title=title,
        year=2020,
        duration=1000,
        posters=lambda: [],
    )


def session(session_key, username):
    return SimpleNamespace(sessionKey=session_key, usernames=[username])


class FakeServer:
    def __init__(self, sessions=None, sessions_error=None):
        self.items = {1: media(1, "Owner's film"), 2: media(2, "Another user's film")}
        self.sessions_list = sessions or []
        self.sessions_error = sessions_error
        self.sessions_calls = 0

    def fetchItem(self, rating_key):
        return self.items[rating_key]

    def sessions(self):
        self.sessions_calls += 1
        if self.sessions_error is not None:
            raise self.sessions_error
        return self.sessions_list


def playing(session_key, rating_key, state="playing"):
    return {
        "type": "playing",
        "PlaySessionStateNotification": [
            {"sessionKey": str(session_key), "ratingKey": str(rating_key), "state": state, "viewOffset": 0}
        ],
    }


def watch(server):
    shown = []
    watcher = PlexSessionWatcher(server, callback=shown.append, account_names=(OWNER,))
    return watcher, shown


def titles(shown):
    return [entry["title"] if entry else None for entry in shown]


def test_another_users_session_does_not_replace_the_presence():
    server = FakeServer(sessions=[session(10, OWNER), session(20, "friend")])
    watcher, shown = watch(server)
    watcher._handle_alert(playing(10, 1))
    watcher._handle_alert(playing(20, 2))
    assert titles(shown) == ["Owner's film"]


def test_another_users_stop_does_not_clear_the_presence():
    server = FakeServer(sessions=[session(10, OWNER), session(20, "friend")])
    watcher, shown = watch(server)
    watcher._handle_alert(playing(10, 1))
    watcher._handle_alert(playing(20, 2, state="stopped"))
    assert titles(shown) == ["Owner's film"]


def test_own_stop_clears_the_presence():
    server = FakeServer(sessions=[session(10, OWNER)])
    watcher, shown = watch(server)
    watcher._handle_alert(playing(10, 1))
    server.sessions_list = []
    watcher._handle_alert(playing(10, 1, state="stopped"))
    assert titles(shown) == ["Owner's film", None]


def test_shared_account_without_session_access_keeps_its_own_playback():
    server = FakeServer(sessions_error=Unauthorized("(401) unauthorized"))
    watcher, shown = watch(server)
    watcher._handle_alert(playing(10, 1))
    watcher._handle_alert(playing(10, 1))
    assert titles(shown) == ["Owner's film", "Owner's film"]
    assert server.sessions_calls == 1


def test_ownership_is_looked_up_once_per_session():
    server = FakeServer(sessions=[session(10, OWNER)])
    watcher, shown = watch(server)
    for _ in range(3):
        watcher._handle_alert(playing(10, 1))
    assert server.sessions_calls == 1


def test_session_lookup_failure_shows_nothing_and_retries():
    server = FakeServer(sessions_error=ConnectionError("network down"))
    watcher, shown = watch(server)
    watcher._handle_alert(playing(10, 1))
    server.sessions_error = None
    server.sessions_list = [session(10, OWNER)]
    watcher._handle_alert(playing(10, 1))
    assert titles(shown) == ["Owner's film"]


def test_connect_returns_the_server_and_the_account_names(monkeypatch):
    connected = object()
    resource = SimpleNamespace(connect=lambda: connected)

    class FakeAccount:
        def __init__(self, token):
            self.username = "drew"
            self.title = "Drew"

        def resource(self, name):
            return resource

    monkeypatch.setattr(plex_watcher, "MyPlexAccount", FakeAccount)
    assert plex_watcher.connect_to_plex("token", "server") == (connected, ("drew", "Drew"))


def test_main_wires_the_account_names_into_the_watcher(monkeypatch):
    import main

    monkeypatch.setattr(main.PlexSessionWatcher, "start", lambda self: None)
    watcher = main.start_watching(FakeServer(), ("drew",), SimpleNamespace(update=lambda entry: None))
    assert watcher._account_names == frozenset({"drew"})
