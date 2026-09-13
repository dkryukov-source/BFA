# tools

Stdlib-only Python 3.9+. No dependencies, so they run unchanged on the Windows
contest PC.

| Tool | Purpose |
|---|---|
| `harvest_cqww.py` | Download CQ WW public logs and public log-checking reports. Resumable, rate-limited. |
| `build_zone_db.py` | Build the callsign -> CQ zone ground-truth database (A2b) from harvested Cabrillo logs. |
| `inventory_radio_folder.ps1` | Triage a Windows/OneDrive ham-radio folder: classify by content, extract log metadata, stage what matters. |
| `inventory_radio_folder.py` | Cross-platform twin of the above, same classification logic. |

## inventory_radio_folder.{ps1,py}

Point it at an opaque folder of radio material and it returns a ranked list.

```powershell
.\inventory_radio_folder.ps1 -Path "C:\Users\Multiple Monitors\OneDrive\Dima\Radio"
.\inventory_radio_folder.ps1 -Path "...\Dima\Radio" -StageTo C:\temp\stage -HydrateCloudFiles
```

```
python3 inventory_radio_folder.py "/path/to/Radio" --csv inv.csv --stage /tmp/stage
```

Classifies by **content, not extension**, into CABRILLO / LCR_UBN / ADIF /
N1MM_DB / CTY / SCP / CALLHISTORY / OTHER, and for each Cabrillo log extracts
callsign, contest, year and QSO count.

**OneDrive online-only files are skipped by default.** They are detected via
`FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`; reading one forces a download, so the
scripts count and report them rather than silently hydrating gigabytes. Pass
`-HydrateCloudFiles` / re-run to opt in.

Documentation and source files (`.md`, `.py`, `.ps1`, `.json`, `.yaml`) are
never content-sniffed — they quote log and cty content verbatim and would
otherwise misclassify as data.

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
