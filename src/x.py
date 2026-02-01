"""X (Twitter) posting via tweepy."""

import os
from typing import Optional

import tweepy


class XClient:
    """Client for posting to X (Twitter)."""

    def __init__(
        self,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
    ):
        self.consumer_key = consumer_key or os.environ.get("X_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.environ.get("X_CONSUMER_SECRET")
        self.access_token = access_token or os.environ.get("X_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.environ.get(
            "X_ACCESS_TOKEN_SECRET"
        )

        if not all([
            self.consumer_key,
            self.consumer_secret,
            self.access_token,
            self.access_token_secret,
        ]):
            raise ValueError(
                "All X API credentials must be set: "
                "X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET"
            )

        # v1.1 API client (needed for media upload)
        auth = tweepy.OAuth1UserHandler(
            self.consumer_key,
            self.consumer_secret,
            self.access_token,
            self.access_token_secret,
        )
        self.api = tweepy.API(auth)

        # v2 API client (for posting tweets)
        self.client = tweepy.Client(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
        )

    def upload_media(self, file_path: str) -> str:
        """Upload media and return the media ID."""
        media = self.api.media_upload(filename=file_path)
        return media.media_id_string

    def post_tweet(
        self,
        text: str,
        media_path: Optional[str] = None,
    ) -> dict:
        """
        Post a tweet, optionally with an image.

        Returns the response from the API.
        """
        media_ids = None
        if media_path:
            media_id = self.upload_media(media_path)
            media_ids = [media_id]

        response = self.client.create_tweet(text=text, media_ids=media_ids)
        return response


def post_run_alert(
    timer_formatted: str,
    streamer: str,
    frame_path: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[dict]:
    """
    Post an alert about a speedrun timer.

    Returns the API response, or None if dry_run is True.
    """
    text = f"Current run: {timer_formatted} IGT | twitch.tv/{streamer}"

    if dry_run:
        print(f"[DRY RUN] Would post: {text}")
        if frame_path:
            print(f"[DRY RUN] With image: {frame_path}")
        return None

    client = XClient()
    return client.post_tweet(text, media_path=frame_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python x.py <timer> [frame_path] [--dry-run]")
        print("Example: python x.py 10:23 frame.jpg --dry-run")
        sys.exit(1)

    timer = sys.argv[1]
    frame_path = None
    dry_run = "--dry-run" in sys.argv

    for arg in sys.argv[2:]:
        if arg != "--dry-run":
            frame_path = arg
            break

    result = post_run_alert(timer, "forsen", frame_path, dry_run)
    if result:
        print(f"Posted tweet: {result}")
