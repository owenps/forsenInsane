"""Twitch API integration for checking stream status."""

import os
import requests
from typing import Optional


class TwitchClient:
    """Client for interacting with the Twitch API."""

    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    STREAMS_URL = "https://api.twitch.tv/helix/streams"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.client_id = client_id or os.environ.get("TWITCH_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("TWITCH_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET must be set"
            )

        self._access_token: Optional[str] = None

    def _get_access_token(self) -> str:
        """Get OAuth access token using client credentials flow."""
        if self._access_token:
            return self._access_token

        response = requests.post(
            self.TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        return self._access_token

    def get_stream(self, username: str) -> Optional[dict]:
        """
        Get stream info for a user.

        Returns None if the user is offline, otherwise returns stream data dict.
        """
        token = self._get_access_token()
        response = requests.get(
            self.STREAMS_URL,
            params={"user_login": username},
            headers={
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
        )
        response.raise_for_status()

        data = response.json().get("data", [])
        if not data:
            return None
        return data[0]

    def is_live_with_game(self, username: str, game_name: str) -> tuple[bool, Optional[dict]]:
        """
        Check if a user is live and playing a specific game.

        Returns (is_match, stream_data).
        """
        stream = self.get_stream(username)
        if not stream:
            return False, None

        current_game = stream.get("game_name", "").lower()
        if game_name.lower() in current_game:
            return True, stream

        return False, stream


def check_minecraft_stream(streamer: str) -> tuple[bool, Optional[dict]]:
    """
    Check if streamer is live and playing Minecraft.

    Returns (is_minecraft, stream_data).
    """
    client = TwitchClient()
    return client.is_live_with_game(streamer, "Minecraft")


if __name__ == "__main__":
    import sys

    streamer = sys.argv[1] if len(sys.argv) > 1 else "forsen"
    is_minecraft, stream = check_minecraft_stream(streamer)

    if stream:
        print(f"Stream: {stream.get('title')}")
        print(f"Game: {stream.get('game_name')}")
        print(f"Is Minecraft: {is_minecraft}")
    else:
        print(f"{streamer} is offline")
