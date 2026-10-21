import os
import random
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone

import urllib.parse

import requests
from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter

import config


# 1. Build every (airport, depart date, return date) combo we need to check
def build_trips():
    start = date.fromisoformat(config.EARLIEST_DEPARTURE)
    end = date.fromisoformat(config.LATEST_RETURN)
    start = max(start, date.today() + timedelta(days=1))  # skip dates that already passed

    trips = []
    depart = start
    while depart + timedelta(days=config.MIN_TRIP_DAYS) <= end:
        ret = depart + timedelta(days=config.MIN_TRIP_DAYS)
        while ret <= end:
            length = (ret - depart).days
            if config.MAX_TRIP_DAYS is None or length <= config.MAX_TRIP_DAYS:
                for origin in config.ORIGINS:
                    trips.append((origin, depart.isoformat(), ret.isoformat()))
            ret += timedelta(days=1)
        depart += timedelta(days=1)
    return trips


# 2. Search Google Flights for one round trip and return the cheapest option
def search_one(origin, depart, ret):
    flight_filter = create_filter(
        flight_data=[
            FlightData(date=depart, from_airport=origin, to_airport=config.DESTINATION),
            FlightData(date=ret, from_airport=config.DESTINATION, to_airport=origin),
        ],
        trip="round-trip",
        seat="economy",
        passengers=Passengers(adults=config.ADULTS),
    )
    tfs = flight_filter.as_b64().decode("utf-8")
    url = "https://www.google.com/travel/flights?" + urllib.parse.urlencode(
        {"tfs": tfs, "hl": "en", "tfu": "EgQIABABIgA", "curr": config.CURRENCY}
    )

    result = get_flights_from_filter(flight_filter)

    def parse_price(p):
        try:
            return int(str(p).replace("$", "").replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    priced = [(f, parse_price(f.price)) for f in result.flights]
    priced = [(f, p) for f, p in priced if p and p > 0]
    if not priced:
        return None

    best, price = min(priced, key=lambda x: x[1])
    return {
        "price": price,
        "airlines": best.name,
        "stops": best.stops,
        "url": url,
    }


def search_with_retry(origin, depart, ret):
    try:
        return search_one(origin, depart, ret)
    except Exception as first_error:
        print(f"   retrying after error: {first_error}")
        time.sleep(15)
        return search_one(origin, depart, ret)  # if this fails too, the caller handles it


# 3. Database: one row per search, so we keep the full price history
def open_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS prices (
            checked_at TEXT, origin TEXT, depart TEXT, return_date TEXT,
            price INTEGER, airlines TEXT, stops INTEGER, url TEXT)"""
    )
    return conn


def last_run_best(conn):
    row = conn.execute(
        "SELECT MIN(price) FROM prices WHERE checked_at = (SELECT MAX(checked_at) FROM prices)"
    ).fetchone()
    return row[0]


def all_time_low(conn):
    return conn.execute("SELECT MIN(price) FROM prices").fetchone()[0]


# 4. Discord alert
def send_discord(message):
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("\n(No DISCORD_WEBHOOK_URL set, printing instead)\n" + message)
        return
    # Discord messages max out at 2000 characters
    for i in range(0, len(message), 1900):
        r = requests.post(
            webhook,
            json={"content": message[i:i + 1900], "flags": 4},  # flag 4 hides link previews
            timeout=15,
        )
        r.raise_for_status()


def format_deal(d):
    stops = "nonstop" if d["stops"] == 0 else f"{d['stops']} stop" + ("s" if d["stops"] > 1 else "")
    return (f"**${d['price']}**  {d['origin']} → KTM  |  {d['depart']} to {d['return_date']}  "
            f"|  {d['airlines']} ({stops})  [Open]({d['url']})")


# 5. Main run
def main():
    test_mode = "--test" in sys.argv
    trips = build_trips()
    if not trips:
        print("Travel window has passed, nothing to check.")
        return
    if test_mode:
        trips = trips[:3]

    print(f"Checking {len(trips)} trips...")
    conn = open_db()
    prev_best = last_run_best(conn)
    prev_low = all_time_low(conn)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")

    found = []
    failures = 0
    for i, (origin, depart, ret) in enumerate(trips, 1):
        try:
            result = search_with_retry(origin, depart, ret)
        except Exception as e:
            failures += 1
            print(f"[{i}/{len(trips)}] {origin} {depart} to {ret}: FAILED ({e})")
            result = None

        if result:
            deal = {"origin": origin, "depart": depart, "return_date": ret, **result}
            found.append(deal)
            print(f"[{i}/{len(trips)}] {origin} {depart} to {ret}: ${result['price']}")
            if not test_mode:
                conn.execute(
                    "INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)",
                    (run_time, origin, depart, ret, deal["price"],
                     deal["airlines"], deal["stops"], deal["url"]),
                )
                conn.commit()

        time.sleep(random.uniform(*config.DELAY_RANGE))

    if not found:
        send_discord(f"⚠️ Flight tracker found no prices this run ({failures} searches failed). "
                     "Google may be blocking requests, try again later.")
        return

    found.sort(key=lambda d: d["price"])
    best = found[0]
    top5 = "\n".join(format_deal(d) for d in found[:5])

    if test_mode:
        send_discord(f"🧪 Test run worked! Cheapest of {len(found)} test searches:\n{top5}")
        return

    # Decide whether to alert
    reasons = []
    if prev_best is None:
        reasons.append("📍 Tracker started! Here's your starting point.")
    elif best["price"] <= prev_best - config.MIN_DROP_TO_ALERT:
        reasons.append(f"📉 Price dropped ${prev_best - best['price']} since last check (was ${prev_best}).")
        if prev_low is not None and best["price"] < prev_low:
            reasons.append("🔥 This is the LOWEST price seen so far!")
    if config.TARGET_PRICE and best["price"] <= config.TARGET_PRICE:
        reasons.append(f"🎯 Under your target of ${config.TARGET_PRICE}!")

    if reasons:
        send_discord("✈️ **Texas → Kathmandu deal alert**\n" + "\n".join(reasons) +
                     f"\n\nTop 5 right now:\n{top5}")
    else:
        print(f"No alert. Cheapest is ${best['price']} (last run ${prev_best}).")


if __name__ == "__main__":
    main()
