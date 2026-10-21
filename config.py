# All your trip settings live here. Change these and the tracker adapts.

ORIGINS = ["AUS", "DFW", "SAT", "IAH"]   # Austin, Dallas, San Antonio, Houston
DESTINATION = "KTM"                       # Kathmandu (Tribhuvan)

EARLIEST_DEPARTURE = "2026-12-11"
LATEST_RETURN = "2027-01-19"
MIN_TRIP_DAYS = 28
MAX_TRIP_DAYS = None    # set a number like 35 to cut down on searches

ADULTS = 1
CURRENCY = "USD"

# Hide itineraries where you'd have to collect bags and recheck on separate tickets
HIDE_SELF_TRANSFER = True

# Alert rules
MIN_DROP_TO_ALERT = 20  # only ping if the cheapest price drops by at least this many dollars
TARGET_PRICE = 1500     # set a number like 1100 to get pinged any time a price is at or under it

# Wait between searches (seconds) so Google doesn't block us
DELAY_RANGE = (3, 7)

DB_PATH = "prices.db"
