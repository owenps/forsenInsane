# forsenInsane bot

X bot account for tracking [Forsen](https://twitch.tv/forsen)'s minecraft speedruns.

Publishes to [X](https://forsenInsaneBot) when forsen's in game timer (IGT) is
over the threshold (currently 10 mins).

![forsenInsane](forsenInsane.png)

Inspired by Erik Wessman's original [forsen-bot](https://github.com/erikwessman/forsen-bot/)

## How it works

- GitHub action `check_live.yml` runs every 15 minutes to check if forsen is live.
- If so, we call `check_timer.yml` which runs on a loop for 5.5 hours.
  - Verify forsen is still live + playing minecraft.
  - Capture a frame from the stream (streamlink + ffmpeg)
  - OCR the IGT time (Tesseract)
  - Check if the timer is between 10:00 and 14:27.
  - If yes: post to X
  - If no: sleep for 60 seconds then loop again.
