# forsenInsane bot

Automated tracking and notifications for [Forsen](https://twitch.tv/forsen)'s minecraft speedruns.

Publishes to [X](https://forsenInsaneBot) when forsen's in game timer (IGT) is
over 10 minutes.

![forsenInsane](forsenInsane.png)

Inspired by Erik Wessman's original [forsen-bot](https://github.com/erikwessman/forsen-bot/).

## How it works

We poll from twitch instead of recieving notifications from twitch webhooks. This allows the script to be executed as a job on github actions.

- `check_live.yml` workflow runs every 15 minutes to check if forsen is live
- If live, we call `check_timer.yml` which runs on a loop for 5.5 hours
  - Verify forsen is still live + playing minecraft
  - Capture a frame from the stream (streamlink + ffmpeg)
  - OCR the IGT time (tesseract)
  - Check if the timer is between 10:00 and 14:27
  - If yes: post to X
  - If no: sleep for 60 seconds then loop again.

The bot maintains a local state `state.json` for not sending multiple notifications for the same run. Configurations for the bot live in `config.json`.

## Development

Install requirements, and setup API keys.

```
cp .env.example .env
# Fill in your credentials in .env
pip install -r requirements.txt
```

You can run the bot while mocking the post to X by using `--dryrun` flag.

```
python -m src.main --dry-run
```
