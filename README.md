# PlexDiscordPresence

**Shows what you're currently watching on Plex as your Discord Rich Presence** - poster art plus an elapsed/remaining progress bar, similar to Spotify's native Discord integration.

This runs on the same machine as your Discord desktop client (Rich Presence is local IPC only - it cannot run on a remote Plex server). It only reflects your own account's playback; you don't need to be the Plex server's admin, just a user with your own Plex account token.

## How it works

```
plex_watcher.py --(NowPlaying | None)--> presence.py --(IPC)--> Discord client
        ^
        | plexapi websocket notifications, using your personal Plex token
   Plex server (remote, shared, not owned by you)
```

`plex_watcher.py` opens a websocket connection to Plex's notification feed and normalizes each playback state change into a plain dict (or `None` when playback stops). `presence.py` turns that into a Discord Activity payload and pushes it over IPC via `pypresence`, clearing presence when nothing is playing. `main.py` wires the two together and stays alive while the websocket listener's own background thread does the work.

This is event-driven rather than polling: it works even if you're not the Plex server's owner. Plex's REST "now playing" endpoint (`/status/sessions`) is restricted to the server owner/admin, but the websocket notification feed isn't - Plex only relays "playing" events for sessions the connecting account already has visibility into, so a shared/friend account sees its own playback without needing admin access.

## Download

Prebuilt binaries for Windows, macOS, and Linux are attached to each [GitHub Release](https://github.com/drew-codes-things/PlexDiscordPresence/releases) - no Python install required:

| Platform | File |
|---|---|
| Windows | `PlexDiscordPresence-<version>-windows-x86_64.exe` |
| macOS | `PlexDiscordPresence-<version>-macos-x86_64.zip` (unzip, then right-click → Open the first time - it's unsigned, so Gatekeeper blocks a plain double-click) |
| Linux | `.deb` (`sudo dpkg -i ...`, installs to `/usr/bin/plexdiscordpresence`) or `.AppImage` (`chmod +x`, then run directly) |

Put a `.env` file (copy `.env.example`, see Configuration reference below) next to the binary, then run it. First run walks through Plex sign-in the same as running from source.

## Running from source

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`. Leave everything blank - `PLEX_USER_TOKEN` and `PLEX_SERVER_NAME` are filled in for you on first run, and `DISCORD_CLIENT_ID` defaults to this project's own registered Discord Application if you don't set one (same model Spotify and other native integrations use - one shared app ID for everyone, so no Developer Portal step is required).

   If you'd rather your activity show under an app with your own name/icon, register one yourself instead:
   - Go to https://discord.com/developers/applications
   - Click **New Application**, name it anything (this name is what shows next to your activity)
   - On the **General Information** page, copy the **Application ID** into `.env` as `DISCORD_CLIENT_ID`
   - No bot and no OAuth2 scopes are needed.

4. Run it:

   ```bash
   python main.py
   ```

   On first run, it opens https://plex.tv/link in your browser and prints a 4-character code - enter it there to sign in. If your account has more than one Plex server, it will ask you to pick one. Both the token and the chosen server name are then saved into `.env`, so this only happens once.

## Configuration reference

| Key | Required | Default | Description |
|---|---|---|---|
| `PLEX_USER_TOKEN` | Auto-filled | - | Your personal Plex account token, obtained via the first-run sign-in flow. |
| `PLEX_SERVER_NAME` | Auto-filled | - | The Plex server to poll, chosen during first-run setup. |
| `DISCORD_CLIENT_ID` | No | This project's shared app | Set your own Discord Developer Portal Application ID if you want your activity to show under your own app name/icon (see Setup step 3). |

## Manual smoke test

1. Start the script: `python main.py`
2. Start playback on Plex from the account whose token is configured.
3. Within a couple of seconds, confirm the activity (poster, title, progress bar) shows up under your Discord profile.
4. Pause playback - confirm the state switches to `"... (Paused)"` and the progress bar disappears.
5. Stop playback - confirm the Discord activity clears.

## Running it in the background (optional)

These are just copy-pasteable starting points - the script itself stays OS-agnostic, so nothing below is required to use it.

### Linux (systemd user service)

Create `~/.config/systemd/user/plex-discord-presence.service`:

```ini
[Unit]
Description=Plex Discord Presence

[Service]
ExecStart=/path/to/PlexDiscordPresence/.venv/bin/python /path/to/PlexDiscordPresence/main.py
Restart=on-failure

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user enable --now plex-discord-presence
```

### macOS (launchd)

Create `~/Library/LaunchAgents/com.user.plex-discord-presence.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.plex-discord-presence</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/PlexDiscordPresence/.venv/bin/python</string>
        <string>/path/to/PlexDiscordPresence/main.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Then:

```bash
launchctl load ~/Library/LaunchAgents/com.user.plex-discord-presence.plist
```

### Windows (Task Scheduler)

Create a task with:
- **Trigger:** At log on
- **Action:** Start a program - `\path\to\PlexDiscordPresence\.venv\Scripts\python.exe` with argument `main.py` and "Start in" set to the project folder
- Leave **"Run whether user is logged on or not"** unchecked, since the script needs to reach the Discord client in your desktop session.

## Troubleshooting

- **Nothing shows up in Discord:** confirm the Discord desktop client is running on this machine (not the Plex server), and check the script's log output for "Could not connect to Discord".
- **Poster doesn't show:** the poster comes from the title's metadata agent (e.g. TMDB), never from your Plex server - a server image URL would expose your Plex token to anyone viewing your Discord profile. Titles with no agent poster (e.g. unmatched or personal media) show title and progress without one. Episodes use their show's poster.
- **Plex restarted or the network dropped:** the activity clears and the app reconnects by itself every 30 seconds. Poster URLs over 256 characters are also dropped automatically (logged once) since Discord rejects them.
- **`PLEX_USER_TOKEN` stopped working:** delete it from `.env` and rerun `python main.py` to redo the sign-in flow.
- **Nothing updates when you play something:** confirm playback is actually happening on the server named in `PLEX_SERVER_NAME` - only that specific server's websocket feed is being watched, not other servers on your account.

## Building the packages

Releases are built automatically by [`.github/workflows/release.yml`](.github/workflows/release.yml) when a `v*.*.*` tag is pushed, using a matrix of GitHub-hosted Windows/macOS/Linux runners (PyInstaller can't cross-compile - each platform's binary has to be built on that platform). To cut a release: bump `VERSION`, commit, then `git tag vX.Y.Z && git push --tags`.

To build locally instead:

```bash
pip install -r requirements-build.txt
pyinstaller --onefile --name PlexDiscordPresence main.py    # -> dist/PlexDiscordPresence(.exe)

# Linux only, after the PyInstaller build above:
./packaging/linux/build-deb.sh          # -> dist/plexdiscordpresence_<version>_amd64.deb
./packaging/linux/build-appimage.sh     # -> dist/PlexDiscordPresence-<version>-x86_64.AppImage

# macOS only, does the PyInstaller build itself and zips the result:
./packaging/macos/build-zip.sh

# Windows only (PowerShell), does the PyInstaller build itself:
./packaging/windows/build-exe.ps1
```

## Dependencies

- [`plexapi`](https://github.com/pkkid/python-plexapi) - Plex API client.
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) - `.env` file loading.
- [`pypresence`](https://github.com/qwertyquerty/pypresence) - Discord Rich Presence IPC client. New to this repo; actively maintained and MIT-licensed.
- [`websocket-client`](https://github.com/websocket-client/websocket-client) - used internally by `plexapi`'s notification listener. New to this repo; actively maintained and Apache-2.0-licensed.
- [`pyinstaller`](https://github.com/pyinstaller/pyinstaller) - build-time only (`requirements-build.txt`), not shipped in any release artifact. Used to produce the standalone binaries. Actively maintained.

## License

[MIT](LICENSE)
