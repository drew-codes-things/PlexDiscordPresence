"""First-run Plex sign-in: PIN login (no manual token copy/paste) followed
by Plex server selection. Persists both into the .env file."""

import webbrowser

from dotenv import set_key
from plexapi.myplex import MyPlexAccount, MyPlexPinLogin


def obtain_plex_token(pin_login=None, timeout_seconds=120):
    pin_login = pin_login if pin_login is not None else MyPlexPinLogin()
    pin_login.run(timeout=timeout_seconds)

    print(f"Go to https://plex.tv/link and enter this code: {pin_login.pin}")
    webbrowser.open("https://plex.tv/link")

    if not pin_login.waitForLogin():
        raise RuntimeError("Plex sign-in timed out or was not approved. Please try again.")

    return pin_login.token


def choose_plex_server(token, account=None, prompt=input):
    account = account if account is not None else MyPlexAccount(token=token)
    servers = [resource for resource in account.resources() if "server" in resource.provides]

    if not servers:
        raise RuntimeError("No Plex servers are available for this account.")

    if len(servers) == 1:
        return servers[0].name

    print("Multiple Plex servers found:")
    for index, server in enumerate(servers, start=1):
        print(f"  {index}. {server.name}")

    while True:
        choice = prompt(f"Select a server [1-{len(servers)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(servers):
            return servers[int(choice) - 1].name
        print("Invalid selection, try again.")


def run_first_time_setup(env_path):
    token = obtain_plex_token()
    server_name = choose_plex_server(token)
    set_key(env_path, "PLEX_USER_TOKEN", token)
    set_key(env_path, "PLEX_SERVER_NAME", server_name)
    return token, server_name
