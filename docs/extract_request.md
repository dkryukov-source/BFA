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
