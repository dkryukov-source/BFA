# Agile load-shifting analysis

Sizes the battery load-shifting prize from metered half-hourly data in Octopus
Energy PDF bills. No estimates, no forecasts — every figure comes from slots you
were actually billed for.

## Requirements

Python 3 (stdlib only) and `pdftotext`:

    apt-get install poppler-utils      # or: brew install poppler

## Use

    python3 parse_octopus.py bills/*.pdf -o halfhourly.csv
    python3 analyse.py halfhourly.csv

`parse_octopus.py` reconciles each bill against its own printed totals and
prints `OK` or the mismatch. Do not trust an analysis run over bills that did
not reconcile.

Bills must be on a half-hourly tariff (Agile) — the per-day rate/consumption
tables are what gets parsed. Overlapping periods are de-duplicated by timestamp.

## Fleet parameters

Defaults are Verno Hollow: Powerwall 2 (13.5 kWh / 5 kW) plus 2x Giv-Bat5.2
behind one Giv-AC3.0 (8.36 kWh usable / 3 kW), 21.86 kWh and 8 kW combined.

    python3 analyse.py halfhourly.csv --capacity 21.86 --power 8 \
        --eta 0.88 --export-price 12.0 --charge 12-16

`--export-price` is what a kWh of solar would have earned if exported, so
charging inside the solar window is costed at the lower of that and the
prevailing Agile rate.

## What it reports

- Your volume-weighted import rate against the unweighted Agile average. Paying
  more than unweighted means your load timing is costing you money.
- Where the import actually sits by time of day.
- A perfect-foresight arbitrage bound (greedy, ranked by unit margin, chunked at
  midday so overnight windows stay interior). Tight to roughly +/-2%, so treat a
  fixed schedule within a couple of percent of it as equivalent.
- Marginal value of each extra hour of discharge permission. A discharge window
  is a permission, not an obligation: the battery stops when empty, so a wider
  window never costs anything.
- Capacity sensitivity, and how many nights capacity actually binds — the test
  for whether more storage would pay.

## Caveat

One summer bill is not a year. Solar fills the battery for free in summer and
the cheap Agile window sits at midday; in winter neither holds. Run this over
12 consecutive bills before acting on any annualised figure.
