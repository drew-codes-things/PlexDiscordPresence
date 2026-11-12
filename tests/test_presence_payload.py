from presence import build_activity_payload

DISCORD_TEXT_MIN = 2
DISCORD_TEXT_MAX = 128


def episode(title, show_name="V", duration_ms=1_000_000):
    return {
        "title": title,
        "type": "episode",
        "show_name": show_name,
        "season": 1,
        "episode": 2,
        "year": None,
        "poster_url": None,
        "duration_ms": duration_ms,
        "view_offset_ms": 0,
        "is_paused": False,
    }


def test_text_fields_fit_discords_length_rules():
    payload, _ = build_activity_payload(episode("x" * 140), now=1000)
    assert DISCORD_TEXT_MIN <= len(payload["details"]) <= DISCORD_TEXT_MAX
    assert DISCORD_TEXT_MIN <= len(payload["state"]) <= DISCORD_TEXT_MAX


def test_zero_duration_has_no_end_time():
    payload, _ = build_activity_payload(episode("Pilot", duration_ms=0), now=1000)
    assert payload["start"] == 1000
    assert "end" not in payload


def test_normal_episode_is_unchanged():
    payload, _ = build_activity_payload(episode("Pilot", show_name="Show"), now=1000)
    assert payload == {"details": "Show", "state": "S01E02 • Pilot", "start": 1000, "end": 2000}
