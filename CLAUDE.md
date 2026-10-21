# Flight Price Tracker: Texas to Kathmandu

## What this project is

A Python bot that watches Google Flights for the cheapest round trip from Texas to Kathmandu and sends a Discord alert when prices drop. It runs on GitHub Actions twice a day, so once it is set up, nothing needs to be done by hand.

## Trip details

| Setting | Value |
|---|---|
| From | AUS (Austin), DFW (Dallas), SAT (San Antonio), IAH (Houston) |
| To | KTM (Tribhuvan International, Kathmandu) |
| Earliest departure | Dec 11, 2026 |
| Latest return | Jan 19, 2027 |
| Minimum trip length | 28 days |
| Passengers | 1 adult, economy |

Because of the 28 day minimum, the latest possible departure is Dec 22. That gives 78 date pairs across 4 airports, so **312 searches per run**.

## Files

| File | Purpose |
|---|---|
| `config.py` | Every trip and alert setting. Change trips here, not in the main code. |
| `tracker.py` | Builds all date combos, searches each one, saves results to SQLite, sends Discord alerts. |
| `requirements.txt` | `fast-flights==3.1.0` and `requests` |
| `.github/workflows/track.yml` | Runs the tracker at 13:00 and 01:00 UTC (about 7 AM and 7 PM Texas time), then commits `prices.db` back to the repo so history carries over. |
| `prices.db` | Created on the first run. One row per search. Do not delete it or the price history resets. |

## How it works

1. `build_trips()` makes every (airport, depart date, return date) combo and skips dates that already passed.
2. `search_one()` queries Google Flights through the `fast-flights` library (it scrapes Google Flights, there is no official API) and keeps the cheapest itinerary.
3. Each result is saved to the `prices` table in SQLite.
4. After the run, the cheapest price is compared to the cheapest from the previous run.
5. A Discord message is sent when:
   * it is the very first run (sets a starting point)
   * the cheapest price dropped by at least `MIN_DROP_TO_ALERT` dollars (default $20), with an extra flag if it is the lowest ever seen
   * the cheapest price is at or under `TARGET_PRICE` (off by default)
   * every search failed (warning that Google may be blocking requests)
6. Each alert lists the top 5 deals with Google Flights links.

Searches wait 3 to 7 seconds apart so Google does not block them. A full run takes roughly 30 to 40 minutes.

## Setup checklist (walk me through these one at a time)

1. **Install and verify locally**
   * Create a virtual environment and run `pip install -r requirements.txt`.
   * Run `python tracker.py --test`. This does only 3 searches and does not save anything to the database.
   * Without a webhook set, it prints the result in the terminal instead of sending to Discord. Confirm real prices show up.
2. **Discord webhook**
   * In Discord: channel settings, then Integrations, then Webhooks, then New Webhook. Copy the URL.
   * Set it as the environment variable `DISCORD_WEBHOOK_URL` and run `python tracker.py --test` again. A test message should appear in Discord.
3. **GitHub repo**
   * Create a new **public** repo (public repos get unlimited Actions minutes; a private repo would go over the 2,000 free minutes per month).
   * Push all files, keeping the `.github/workflows/` folder structure.
4. **GitHub secret**
   * Repo Settings, then Secrets and variables, then Actions. Add a secret named `DISCORD_WEBHOOK_URL`.
5. **First run**
   * Actions tab, then "Track flight prices", then "Run workflow".
   * Confirm the run finishes, a "Tracker started" message arrives in Discord, and a commit with `prices.db` shows up in the repo.

## Rules for Claude Code

* **Never** put the Discord webhook URL in any file, commit, or log. It only lives in the environment variable locally and in GitHub Secrets.
* Keep `prices.db` committed. The workflow depends on it to compare prices between runs.
* Keep all trip settings in `config.py`.
* Explain things simply, step by step. Avoid long technical explanations.

## Troubleshooting

* **No prices found or parsing errors:** Google may have changed its page. Check if there is a newer `fast-flights` version on PyPI, update `requirements.txt`, and retest with `--test`. Print the raw `fast_flights.fetch_flights_html(query)` output to see what Google returned.
* **Works locally but fails on GitHub Actions:** Google may be blocking GitHub's servers. Fallback is to run it on my laptop on a schedule instead (cron on Mac or Linux, Task Scheduler on Windows) and remove the schedule from the workflow.
* **Workflow push fails:** make sure `permissions: contents: write` is still in `track.yml` and that Actions has read and write permission under repo Settings, then Actions, then General.
* **Too many or too few alerts:** adjust `MIN_DROP_TO_ALERT` or set `TARGET_PRICE` in `config.py`.

## When the trip is booked

Disable the workflow in the Actions tab so it stops running. After Dec 22 the tracker has no dates left to check and just exits, so it is harmless either way.

## Possible improvements later

* A daily summary message even when there is no drop
* A chart of price history from `prices.db`
* Per airport alerts (for example, only DFW deals)
