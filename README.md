# NoTimeToRinse Party Room Bot

Custom Telegram group moderation bot for @NoTimeToRinsePartyBot.

## What it does
- Welcomes new members with Party Room branding
- `/rules` shows the three house rules
- Reply to a member's message with `/warn reason`, `/warnings`, `/clearwarns`, `/mute 60`, `/unmute`, or `/ban`
- Three warnings automatically mute the member for 24 hours and reset the count
- Six messages within ten seconds automatically mute for ten minutes
- Only group admins can run moderation commands; bot will not punish group admins

## Local test
1. Install Python 3.11+.
2. `pip install -r requirements.txt`
3. Set `TELEGRAM_BOT_TOKEN` in your terminal environment (never post or commit it).
4. `python bot.py`

## Hosting on Railway (GitHub deployment)
1. Create a **private** GitHub repository and upload `bot.py`, `requirements.txt`, `Procfile`, `.gitignore`, and `README.md` (do not upload tokens).
2. Create a Railway project from the GitHub repository.
3. In the service settings set the **start command** to `python bot.py`. No public domain or HTTP port is required; this is a polling worker.
4. In service Variables, set `TELEGRAM_BOT_TOKEN` to the token from BotFather. Never share it in chat.
5. Deploy and inspect the service logs for `NoTimeToRinse Party Bot started`.
6. Keep exactly one running instance. Multiple pollers using the same token conflict.
7. To **persist warnings across redeploys**, attach a Railway persistent volume mounted at `/data`, and set `DB_PATH=/data/party_room.sqlite3`. Without a volume, warning counts can reset on redeploy. Volume availability and pricing depend on Railway's current plan.

## Telegram setup
- Add @NoTimeToRinsePartyBot as group administrator.
- Enable **Delete Messages** and **Ban Users / Restrict Members** permissions.
- Disable privacy mode in BotFather (`/setprivacy`) and re-add the bot if needed.
- Send `/rules` in the group to verify it responds.
- Reply to a test user's message with `/warn test` and then `/warnings`.
- Avoid testing automatic flood protection with real community members.

## Settings (optional environment variables)
- `WARN_LIMIT` default `3`
- `WARN_MUTE_HOURS` default `24`
- `FLOOD_COUNT` default `6`
- `FLOOD_WINDOW_SECONDS` default `10`
- `FLOOD_MUTE_MINUTES` default `10`
- `DB_PATH` default `party_room.sqlite3`

## Notes
- The flood counter is in memory; it resets when the process restarts. Warnings are in SQLite.
- This is a basic starter moderation bot, not a complete anti-scam classifier or web dashboard.
- Only a single process should run the bot. Hosting requires a provider account and may have costs.
- Telegram's permissions and group default settings affect what an unmuted user can send.
