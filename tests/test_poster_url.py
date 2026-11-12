from types import SimpleNamespace

import pytest

from plex_watcher import public_poster_url

TOKEN = "SECRETPLEXTOKEN"


def movie_with_posters(*keys):
    posters = [SimpleNamespace(key=key) for key in keys]
    return SimpleNamespace(type="movie", posters=lambda: posters)


def test_agent_poster_is_resized_for_discord():
    item = movie_with_posters("https://image.tmdb.org/t/p/original/abc.jpg")
    assert public_poster_url(item) == "https://image.tmdb.org/t/p/w500/abc.jpg"


def test_episode_uses_the_show_poster():
    show = movie_with_posters("https://image.tmdb.org/t/p/original/show.jpg")
    episode = SimpleNamespace(type="episode", show=lambda: show)
    assert public_poster_url(episode) == "https://image.tmdb.org/t/p/w500/show.jpg"


@pytest.mark.parametrize(
    "leaky_key",
    [
        f"https://10-0-0-2.abc.plex.direct:32400/library/metadata/1/thumb/2?X-Plex-Token={TOKEN}",
        f"https://image.tmdb.org/t/p/original/abc.jpg#X-Plex-Token={TOKEN}",
        f"https://user:{TOKEN}@image.tmdb.org/t/p/original/abc.jpg",
        "https://10-0-0-2.abc.plex.direct:32400/library/metadata/1/thumb/2",
        "http://image.tmdb.org/t/p/original/abc.jpg",
        "/library/metadata/1/thumb/2",
        "",
        None,
    ],
)
def test_server_or_credentialed_posters_are_never_used(leaky_key):
    assert public_poster_url(movie_with_posters(leaky_key)) is None


def test_skips_a_leaky_poster_and_uses_the_next_public_one():
    item = movie_with_posters(
        f"https://image.tmdb.org/t/p/original/abc.jpg#X-Plex-Token={TOKEN}",
        "https://image.tmdb.org/t/p/original/clean.jpg",
    )
    assert public_poster_url(item) == "https://image.tmdb.org/t/p/w500/clean.jpg"
