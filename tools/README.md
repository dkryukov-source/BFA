# tools

Stdlib-only Python 3.9+. No dependencies, so they run unchanged on the Windows
contest PC.

| Tool | Purpose |
|---|---|
| `harvest_cqww.py` | Download CQ WW public logs and public log-checking reports. Resumable, rate-limited. |
| `build_zone_db.py` | Build the callsign -> CQ zone ground-truth database (A2b) from harvested Cabrillo logs. |

## harvest_cqww.py

```
python3 tools/harvest_cqww.py logs --years 2021-2025 --out data/logs/archive
python3 tools/harvest_cqww.py logs --call PZ5CO --years 2019-2025
python3 tools/harvest_cqww.py lcr  --call V26K  --years 2015-2025
```

Keep `--concurrency` at the default 8. cqww.com issues HTTP/2 `GOAWAY` under
load; the reference implementation's own README recommends 10-20 and a single
year is order 8,000 files. Existing non-empty files are skipped, so an
interrupted run resumes by simply re-running.

**Blocked from the cloud session** — cqww.com is not on this environment's
egress allowlist. Run it from a machine with normal network access.

## build_zone_db.py

```
python3 tools/build_zone_db.py data/logs/archive --out data/zones.json --csv data/zones.csv
```

Three evidence tiers, best first:

- **SELF** — the zone a station declares in its *own* submitted log. Every
  Cabrillo QSO line carries the sender's own zone, so this is self-declared with
  zero copy error. Gold.
- **LCR** — zone corrected by CQ's log checking. Adjudicated. Gold. *(not yet
  implemented — needs harvested .rpt files to define the parse)*
- **HEARD** — majority vote over the zone as copied by everyone else. Silver and
  copy-error prone, but the only evidence for stations that never submit a log —
  which is exactly the population generating "absent from whitelist" soft flags.

SELF overrides HEARD. Output carries `confidence` (0-1), observation counts,
last-seen year, and flags where a station's own log is internally inconsistent
or where everyone else systematically copies something different.

### Scope discipline

The check answers **"did I copy what they sent"**, NOT "is their zone
geographically correct". CQ WW cross-references sent against received between
logs, so match the actual sent zone. Do not geo-police it.

### Known blind spot

A miscopy that lands on a *different real call sending the same zone* (copying
K5ZR/zone 4 when K5TR/zone 4 sent) fires nothing — both valid, both in the
whitelist, zone matches. Call-for-call substitution between two real stations is
only catchable post-contest via cross-log checking. This is a prioritised
re-listen prompt, not an oracle.
