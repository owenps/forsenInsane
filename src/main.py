"""Main entry point for the forsenInsane bot."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .capture import capture_stream_frame
from .ocr import format_timer, read_timer_from_frame
from .twitch import check_minecraft_stream
from .x import post_run_alert

# Paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "config.json"
STATE_PATH = REPO_ROOT / "state.json"


def load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_state() -> dict:
    """Load state from state.json."""
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state: dict) -> None:
    """Save state to state.json."""
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def should_skip_for_same_run(state: dict, config: dict) -> bool:
    """
    Check if we should skip because we're in the same run.

    Returns True if last tweet was within max_threshold time (same run still active).
    """
    last_tweet = state.get("last_tweet_time")
    if not last_tweet:
        return False

    last_time = datetime.fromisoformat(last_tweet.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    elapsed = (now - last_time).total_seconds()

    max_threshold = config.get("max_threshold_seconds", 867)
    return elapsed < max_threshold


def check_live(config: dict, state: dict) -> bool:
    """
    Tier 1: Check if streamer is live with Minecraft.

    Returns True if Tier 2 should be triggered.
    """
    if not config.get("enabled", True):
        print("Bot is disabled in config")
        return False

    streamer = config.get("streamer", "forsen")
    is_minecraft, stream = check_minecraft_stream(streamer)

    if not stream:
        print(f"{streamer} is offline")
        return False

    game = stream.get("game_name", "unknown")
    if not is_minecraft:
        print(f"{streamer} is live but playing {game}, not Minecraft")
        return False

    print(f"{streamer} is live and playing Minecraft!")

    if should_skip_for_same_run(state, config):
        print("Recently tweeted, same run still active - skipping")
        return False

    return True


def check_timer_loop(
    config: dict,
    state: dict,
    dry_run: bool = False,
    single_check: bool = False,
) -> Optional[int]:
    """
    Tier 2: Polling loop to check the timer.

    Returns the timer value in seconds if threshold was reached and tweet posted,
    None otherwise.
    """
    streamer = config.get("streamer", "forsen")
    min_threshold = config.get("min_threshold_seconds", 600)
    max_threshold = config.get("max_threshold_seconds", 867)

    # Exit before GitHub's 6-hour limit so Tier 1 can re-trigger
    MAX_RUNTIME = 5.5 * 3600  # 5.5 hours
    start_time = time.time()

    iteration = 0
    while True:
        # Check for approaching job timeout
        elapsed = time.time() - start_time
        if elapsed > MAX_RUNTIME:
            print(f"Approaching job timeout ({elapsed/3600:.1f}h), exiting for re-trigger")
            return None
        iteration += 1
        print(f"\n--- Check #{iteration} ---")

        # Verify still live with Minecraft
        is_minecraft, stream = check_minecraft_stream(streamer)
        if not stream:
            print("Stream ended, exiting loop")
            return None
        if not is_minecraft:
            print(f"Game changed to {stream.get('game_name')}, exiting loop")
            return None

        # Capture frame
        print("Capturing frame...")
        frame_path = capture_stream_frame(streamer)
        if not frame_path:
            print("Failed to capture frame, will retry")
            if single_check:
                return None
            time.sleep(60)
            continue

        # OCR the timer
        print("Reading timer...")
        timer_seconds = read_timer_from_frame(frame_path)
        if timer_seconds is None:
            print("Failed to read timer, will retry")
            if single_check:
                return None
            time.sleep(60)
            continue

        timer_str = format_timer(timer_seconds)
        print(f"Timer: {timer_str} ({timer_seconds}s)")

        # Check thresholds
        if timer_seconds > max_threshold:
            print(f"Timer past max threshold ({format_timer(max_threshold)}), run failed")
            return None

        if timer_seconds >= min_threshold:
            print(f"Timer reached threshold! Posting to X...")
            post_run_alert(timer_str, streamer, frame_path, dry_run)

            # Update state
            if not dry_run:
                state["last_tweet_time"] = datetime.now(timezone.utc).isoformat()
                save_state(state)
                print("State updated")

            return timer_seconds

        print(f"Timer below threshold ({format_timer(min_threshold)})")

        if single_check:
            return None

        print("Sleeping 60s...")
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="forsenInsane Minecraft speedrun tracker")
    parser.add_argument(
        "--mode",
        choices=["check-live", "check-timer", "full"],
        default="full",
        help="Operation mode: check-live (Tier 1), check-timer (Tier 2), or full",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually post to X or update state",
    )
    parser.add_argument(
        "--single-check",
        action="store_true",
        help="Only run one iteration of the timer check loop",
    )
    args = parser.parse_args()

    config = load_config()
    state = load_state()

    if args.mode == "check-live":
        should_trigger = check_live(config, state)
        sys.exit(0 if should_trigger else 1)

    elif args.mode == "check-timer":
        result = check_timer_loop(config, state, args.dry_run, args.single_check)
        sys.exit(0 if result else 1)

    else:  # full mode
        if not check_live(config, state):
            sys.exit(0)
        result = check_timer_loop(config, state, args.dry_run, args.single_check)
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
