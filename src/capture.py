import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def get_stream_url(channel: str, quality: str = "best") -> Optional[str]:
    """
    Get the direct stream URL using streamlink.

    Returns None if stream is not available.
    """
    try:
        result = subprocess.run(
            ["streamlink", f"twitch.tv/{channel}", quality, "--stream-url"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def capture_frame(stream_url: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Capture a single frame from the stream using ffmpeg.

    Returns path to the captured frame, or None on failure.
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".jpg")

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",  # Overwrite output
                "-i",
                stream_url,
                "-vframes",
                "1",
                "-q:v",
                "2",
                output_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        if Path(output_path).exists():
            return output_path
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def capture_stream_frame(
    channel: str, output_path: Optional[str] = None
) -> Optional[str]:
    """
    Capture a single frame from a Twitch channel's stream.

    Returns path to the captured frame, or None if stream unavailable.
    """
    stream_url = get_stream_url(channel)
    if not stream_url:
        return None

    return capture_frame(stream_url, output_path)


if __name__ == "__main__":
    import sys

    channel = sys.argv[1] if len(sys.argv) > 1 else "forsen"
    output = sys.argv[2] if len(sys.argv) > 2 else "frame.jpg"

    print(f"Capturing frame from {channel}...")
    result = capture_stream_frame(channel, output)

    if result:
        print(f"Frame saved to: {result}")
    else:
        print("Failed to capture frame (stream may be offline)")
