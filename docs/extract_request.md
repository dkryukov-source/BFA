# Extract request — for the session with local machine + Gmail access

**For:** the Remote Control session running on DK's PC (currently
"Claude agents post-swap round", which is blocked asking where Contest Master
runs and whether the extract is one-time).
**From:** the Contest Master cloud session, repo `dkryukov-source/BFA`,
branch `claude/contest-master-cq-ww-kux1rl`.

---

## The two blocking questions, answered

**Q1 — Where does Contest Master run?** Both, split:

- **Offline analysis (Track A)** — Cabrillo parser, accuracy checker, off-time
  optimiser, band plan, pace curve — runs in the **cloud session**, this repo,
  this branch.
- **Live in-contest display (Track B)** runs **local on the Windows PC beside
  N1MM**, because N1MM's UDP broadcasts default to `127.0.0.1`.

So: **deliver all extracted data into this repo on this branch.** That is the
handoff point.

**Q2 — One-time extract or ongoing sync?** **One-time.** The corpus is static
historical data; new logs appear only annually. No sync job. Re-run by hand
after CQ WW SSB (late Oct) and CW (late Nov) 2026.

## Why this is delegated rather than done here

This cloud container's egress policy allows **PyPI, npm and GitHub only**.
`cqww.com`, `www.country-files.com` and `supercheckpartial.com` all return 403 at
the gateway (measured across 24 hosts — see `data_sources.md` §0). A session on
DK's own machine has his network and his Gmail and can reach all of it.

---

## Step 0 — inventory the local Radio folder FIRST

The operator's OneDrive-backed radio folder (path held locally, deliberately
not recorded in this public repository).

It holds a lot of material of unknown composition (~389
files seen referenced elsewhere). **Triage it before anything else** — it may
already contain items 1, 2, 5, 6 and 7d, which would make most of the network
harvest unnecessary.

Two equivalent scripts are committed; use whichever suits:

```powershell
.\tools\inventory_radio_folder.ps1 -Path "<the Radio folder>"
```

```
python3 tools/inventory_radio_folder.py "<the Radio folder>" --csv inv.csv
```

They classify every file **by content, not extension** into CABRILLO / LCR_UBN /
ADIF / N1MM_DB / CTY / SCP / CALLHISTORY, and for each Cabrillo log extract the
callsign, contest, year and QSO count. That turns an opaque folder into a ranked
list in one pass.

Then stage what matters:

```powershell
.\tools\inventory_radio_folder.ps1 -Path "<the Radio folder>" -StageTo C:\temp\bfa-stage -HydrateCloudFiles
```

**OneDrive caveat — read this before running with `-HydrateCloudFiles`.** Files
in OneDrive may be online-only placeholders. The scripts detect them via the
`FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` attribute and **skip them by default**
rather than silently pulling gigabytes down. Reading one forces a download.
`-HydrateCloudFiles` opts in; the summary tells you how many are affected first.

What to look for, in priority order:
1. **`.rpt` files or anything matching "Log Checking Report" / "UBN"** — item 1
   below, the single most valuable thing in this project.
2. **Cabrillo logs for PZ5CO / PZ5DX / RA3CO** — item 2.
3. **`.s3db` N1MM databases** — these contain the logged QSOs directly and can
   substitute for a missing Cabrillo export.
4. **An N1MM call-history file** — item 7d.

---

## Manifest, ranked by value

### 1. Own UBN / log-checking reports — highest value, irreplaceable, Gmail only

Search Gmail for: `CQ WW` · `log checking report` · `UBN` · sender containing
`cqww` · subject `Log Checking Report`. Callsigns **PZ5DX, PZ5CO, RA3CO**, all
years.

These name every denied QSO and why. Nothing else in this project is as valuable
per byte — they convert the accuracy value model from estimate to arithmetic
(see `scoring_model.md` §5).

→ `data/lcr/<call>-<year><cw|ph>.rpt`

### 2. Own submitted Cabrillo logs

Gmail (submission confirmations usually echo the log) or the PC's N1MM export
folders. Wanted: **CW 2021, 2022, 2023, 2024, 2025** and **SSB 2023, 2025**.

→ `data/logs/own/<call>-<year>-<cw|ssb>.log`

### 3. Public logs — re-downloadable, not unique

**The harvester is already written and tested. Do not write another.**

```
python3 tools/harvest_cqww.py logs --years 2021-2025 --out data/logs/archive
```

Keep `--concurrency` at the default **8**. cqww.com issues HTTP/2 `GOAWAY` when
pushed; a year is ~8,000 files. The tool is resumable — re-running skips files
already present.

Faster priority subset: **V26K** 2021-2025 CW, plus the Zone 9 stations
(PJ2T, P40/P49, PJ4, 9Y4, 8P5, 8R, FY, YV, HK, PZ).

### 4. Public log-checking reports for benchmark stations

```
python3 tools/harvest_cqww.py lcr --call V26K --years 2015-2025
```

Scope limit: cqww publishes these only for **world high scorers**, so most calls
404. That is expected, not an error.

### 5. cty.dat — late-2023 version

From country-files.com dated archives. Needed because the A1 validation gate
reproduces PZ5CO CW 2023 and must hit **exactly 151 zones**; a 2025 cty.dat
misresolves 2023 callsigns and silently corrupts the check. Current files
(`VER20251218`, `VER20251125`) are already committed.

→ `data/cty/cty-VERYYYYMMDD.dat`, using AD1C's own `VER` string.

### 6. MASTER.SCP

→ `data/scp/MASTER.SCP`

### 7. N1MM items — only obtainable from the real PZ5DX install

a. **Enable the UDP broadcasts. They all default to `False`:**
   `IsBroadcastContact`, `IsBroadcastSpots`, `IsBroadcastScoreUDP`,
   `IsBroadcastExternalLookup`, `IsBroadcastRadio`.
   **Nothing in Track B receives a single byte until these are on.**

b. Capture **raw datagram bytes** (not a parsed view) for: one logged CQ WW QSO,
   one edit, one delete, one typed-but-unlogged callsign.

c. Three specific unknowns to answer from that capture:
   1. **Which field carries the received CQ zone in CQ WW** — `<zone>`,
      `<rcvnr>` or `<exchange1>`. This gates the live accuracy assist.
   2. `rxfreq` / `txfreq` scaling in `<contactinfo>`.
   3. Whether `<timestamp>` is UTC.

d. Check whether N1MM's pre-assembled CQ WW call-history file exists and is
   current — verify the received zone sits in the **`Sect`** column.

→ append raw dumps to `docs/n1mm_schema_observed.md`

---

## Delivery rules

Commit to `dkryukov-source/BFA`, branch `claude/contest-master-cq-ww-kux1rl`,
under `data/`.

**Commit logs and reports byte-unmodified, as received.** Do not reformat,
re-encode, normalise line endings, or "clean" Cabrillo files. The parser adapts
to the data, never the reverse.

Read `docs/data_sources.md` first — it carries the full URL structures, the
rate-limit behaviour and the reasoning. `tools/harvest_cqww.py` and
`tools/build_zone_db.py` are committed and tested.

If Gmail turns out not to be reachable from your side either, say so rather than
spending time on it.


---

# Round 2 — asks after the local Step 0 report

Step 0 is done: 13,426 files scanned, 45 distinct CQ WW files staged. The
following are the things that report raised and did not settle.

## R1. PZ5CO CW 2023 — two files, same QSO count (8,037). Which was submitted?

This is the **validation-gate log**, so picking the wrong one invalidates the
gate. Decisive test, in order:

1. `diff` them. If they differ only in header fields, go to 2.
2. Compare each file's `CLAIMED-SCORE:` header against the published claimed
   score **15,208,050**. The match is the submitted log.
3. If both match or neither does, prefer the one whose `CREATED-BY:` is the
   N1MM version in use that season, and record the ambiguity in the manifest.

Report both headers verbatim either way.

## R2. PZ5DX CW 2024 — two files differing by one QSO

The extra line is:

```
QSO: 1822 CW 2024-11-24 0057 PZ5DX 599 9 V26K 599 08
```

Same question: which was submitted? Compare `CLAIMED-SCORE:` against the
published PZ5DX 2024 claimed score.

Two incidental notes, both already handled by our parser but worth recording:
- **`599 9`** — the sent zone is a single digit here, not `09`. Cabrillo zone
  padding is inconsistent in the wild. `build_zone_db.py` strips leading zeros,
  so both forms normalise to 9.
- `1822` kHz is **160m**, and it is a V26K QSO — i.e. the one differing QSO is a
  topband contact with the benchmark station.

## R3. Category headers for the benchmark logs — needed before any comparison

For **every** reference log staged, report these headers verbatim:

```
CALLSIGN  CONTEST  CATEGORY-OPERATOR  CATEGORY-ASSISTED  CATEGORY-BAND
CATEGORY-POWER  CATEGORY-TRANSMITTER  CATEGORY-OVERLAY  CLAIMED-SCORE  OPERATORS
```

**Why this is now the highest-value thing in the staged set.** The QSO counts you
reported change the picture:

| Station | CW 2023 QSOs |
|---|---|
| V26K | 9,217 |
| **PZ5CO** | **8,037** |
| P40L (Aruba, **zone 9**) | 7,727 |

P40L is the correct same-zone benchmark, and it logged **310 fewer QSOs than
PZ5CO**. If P40L is a comparable category, the premise that PZ is
structurally short of its zone peers is wrong, and the low-band investment case
has to be rebuilt on a different basis. If P40L is low power or single band, the
comparison is void. **Without the category headers the numbers are unusable** —
do not let anyone draw a conclusion from the raw counts alone.

## R4. V26K 2024 and 2025 — needed for the pace projection

You have 2019, 2021, 2022, 2023 (8,226 / 8,414 / 9,105 / 9,217). The A5 pace
target extrapolates the V26K trend to 2026; a projection anchored on data
ending in 2023 and crossing the solar maximum is weak. **2024 and 2025 are the
two most load-bearing years and both are missing.** Harvest them first:

```
python3 tools/harvest_cqww.py logs --call V26K --years 2024-2025 --modes cw
```

## R5. N1MM / B0 — you do not need the real station

The report says N1MM is not installed and treats B0 as blocked until a station
is available. It is not blocked. **Any Windows machine will answer all three
open questions**, because they are about the wire format, not about this
station's configuration:

1. Install N1MM Logger+.
2. Create a new contest, type **CQWW**, mode CW. Enter any callsign.
3. Enable the broadcasts (all default off) — `IsBroadcastContact`,
   `IsBroadcastSpots`, `IsBroadcastScoreUDP`, `IsBroadcastExternalLookup`,
   `IsBroadcastRadio`. Destination `127.0.0.1`, ports **12060** and **12050**.
4. Log one QSO with a plausible exchange, e.g. `K1ABC 599 05`.
5. Capture raw datagrams on both ports. Then edit that QSO, delete it, and type
   a callsign without logging.

That answers: which field carries the received zone in CQ WW, `rxfreq`/`txfreq`
scaling, and whether `timestamp` is UTC. The only thing genuinely requiring the
PZ5DX machine is confirming its own port configuration, which is a one-line
check later.

The old `RCC_CallHistory.txt` and `Master DAT\ARRLDXCW_2025-003.txt` you found
are **not** CQ WW call-history files — the exchange differs. Keep them as format
references only.

## R6. Private repo — agreed, and here is the split

Contest data should not go in the public `BFA` repo. Logs carry callsigns,
timestamps and locations, and the Step 0 manifest demonstrated the adjacent risk
directly by listing passport and booking scans.

Proposed split:

- **`BFA` (public)** — `tools/`, `docs/`, `data/cty/`, `data/scp/`,
  `data/logs/fixtures/`. Code and public reference data only.
- **new private repo** — all own logs, all UBN/LCR reports, the harvested
  public-log archive, and any derived database keyed to real callsigns.

The tools take the data root as an argument, so nothing needs to change in them:
point `--out` / the positional root at a checkout of the private repo.

DK needs to name the private repo. Until then keep the intake local, as you have.

## R7. Manifest gaps to fill

Still outstanding from the original manifest: own UBNs (Gmail — in progress),
own 2025 CW and SSB logs (Gmail — in progress), V26K 2024/2025 (R4), Zone 9
multi-op CW 2023-25 and SSB 2025 (harvest), current MASTER.SCP (the committed
copy is Release 2022.06.03 and does not contain PZ5DX).
