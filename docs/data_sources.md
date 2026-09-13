# Data sources — availability, blockers, and acquisition plan

## 0. Build-environment egress reality (measured, not assumed)

Outbound HTTPS goes through a policy-enforcing gateway. Measured 2026-09-13 by
probing 24 hosts:

**Reachable**
- PyPI / files.pythonhosted.org
- npm registry
- **github.com (`git clone`) and raw.githubusercontent.com** — fully open
- GitHub REST search via MCP tools
- Anthropic-side web search (returns indexed summaries, not raw files)

**Blocked — gateway answers 403 to CONNECT**

`cqww.com` · `www.cqww.com` · `cqwpx.com` · `cqwwrtty.com` · `cq160.com` ·
`n1mmwp.hamdocs.com` · `hamdocs.com` · `www.country-files.com` ·
`supercheckpartial.com` · `www.contestcalendar.com` · `ng3k.com` · `k8nd.com` ·
`sm7iun.se` · `www.la1k.no` · `www.arrl.org` · `www.contesting.com` ·
`clublog.org` · `www.qrz.com` · `reversebeacon.net` · `archive.org` ·
`web.archive.org` · `en.wikipedia.org`

The allowlist is **PyPI, npm, GitHub**. Not a ham-radio-specific block —
Wikipedia is blocked too. `WebFetch` is subject to the same policy; there is no
alternate route and policy denials are not to be worked around.

**Consequence:** no bulk harvesting of contest data can run inside this
environment. Either the operator fetches, or the allowlist is extended to
`cqww.com`, `www.country-files.com`, `supercheckpartial.com`.

**GitHub, however, turned out to carry most of what was needed.** See below.

---

## 1. cty.dat (the spine) — SOLVED for current use

Canonical source blocked. Located current AD1C files on GitHub instead:

| File | Version | Source | Status |
|---|---|---|---|
| `data/cty/cty-VER20251218.dat` | 2025-12-18 | `thefish12357/hamradio-award-system` | **current — use for 2026** |
| `data/cty/cty-VER20251125.dat` | 2025-11-25 | `s53zo/SH6` | cross-check copy |

Both sanity-check clean:
`Suriname: 09: 12: SA: 4.00: 56.00: 3.0: PZ:` — zone 9, ITU 12, continent SA.
(cty.dat uses west-positive longitude; 56.00 = 56 W.)

Rejected: `Tlf/tlf` (VER20200405, stale), `KB1RMA/dxcc` (2013), `WSJTX/wsjtx`
(VER20250115 but a 354 KB variant, not the standard ~100 KB AD1C format).

### Still outstanding: per-contest-year files

The spec says "pin a dated cty.dat." Not sufficient. Validating a **Nov 2023**
log against a **2025/2026** cty.dat misresolves any callsign whose prefix,
entity, or zone assignment moved in between — silently corrupting the very mult
and accuracy figures the A1 validation gate exists to check.

**The PZ5CO CW 2023 validation gate needs a late-2023 cty.dat.** Two routes:
- country-files.com dated archives (blocked here — operator fetch), or
- walk the git history of a repo that vendors cty.dat and check out the commit
  nearest Nov 2023. `jr8ppg/zlog_setup` carries multiple dated versions in
  parallel directories (`v293x/` … `v297x/`) and is a good candidate.

---

## 2. CQ WW public logs archive — URL structure RECOVERED

Blocked here, but `ok1xoe/CQWWDownloader` (GPL-3.0, Java) documents the complete
structure. Harvest recipe, no guessing required:

```
index            https://cqww.com/publiclogs/
year + mode      https://cqww.com/publiclogs/{YYYY}{cw|ph|rtty}/
single log       https://cqww.com/publiclogs/{YYYY}{mode}/{callsign}.log
```

- `ph` = SSB. Filenames are the callsign, case-insensitive, optionally with a
  `[._-]suffix` before `.log`.
- The index page links each year/mode category; both levels are plain HTML,
  scraped with Jsoup in the reference implementation.

**Server behaviour — matters for the harvest:** the site issues HTTP/2 `GOAWAY`
under high concurrency. The reference tool defaults to 100 concurrent and its own
README recommends dropping to **10–20** with retries. Harvest politely; a full
year is order 8,000 files.

### Refinement to the A2b harvest method

The spec proposes harvesting `hiscall + hiszone` (zones *as received by others*)
and taking a most-frequent value. There is a strictly better signal in the same
files.

**Every submitted Cabrillo log states the sender's own zone in every QSO line**
(the `myzone` field). Self-declared, zero copy error. One pass over the archive
yields `call -> declared zone` directly, no voting.

| Tier | Source | Quality |
|---|---|---|
| 1 | `myzone` from the station's own submitted log | gold — self-declared |
| 2 | LCR-corrected zone (§3) | gold — adjudicated |
| 3 | majority vote over `hiszone` as received by others | silver — copy-error prone |

Tier 3 stays necessary for stations that never submit — which is also exactly the
population generating A2b's "absent from whitelist" soft flags. Keep it, rank it
last.

---

## 3. CQ WW public log-checking reports (LCR / UBN)

```
https://cqww.com/publiclcr/{YYYY}{cw|ph}/{callsign}.rpt
```

Confirmed live examples: `.../publiclcr/2019cw/k1ar.rpt`,
`.../publiclcr/2019cw/v26k.rpt`, `.../publiclcr/2020ph/pt5j.rpt`.
Year/mode index pages exist for at least 2015, 2018–2022.

**Scope limit — important:** published only for *world high-scoring stations in
each category*, not all entrants. Order 10² per year. **Not a bulk zone source.**
Do not plan the A2b whitelist around it.

What it is genuinely good for:
- The **benchmark** stations' real error composition — V26K's actual
  bust / NIL / exchange split rather than an assumed one. This is what converts
  the accuracy value model from estimate to arithmetic (see `scoring_model.md` §5).

The operator's **own private LCRs** for PZ5CO/PZ5DX are the highest-value
accuracy dataset that exists for this project — they name every denied QSO and
why. They are emailed to the log-submission address.

---

## 4. MASTER.SCP

`https://www.supercheckpartial.com/MASTER.SCP` — blocked. ~50k active contest
callsigns, no zones. Needed for the A2/B5 "near-match to corpus-frequent call"
check — which, per `scoring_model.md` §4, is the *highest*-value accuracy check
because it targets busted callsigns.

Not a hard dependency: the public-logs harvest (§2) produces a superset with
observation counts and zones attached.

---

## 5. Reference log corpora — **still the binding blocker**

The spec lists as collected: Zone-9 SSB 2025 (11 logs), Zone-9 CW multi-op
2023–25 (10), V26K CW 2021–25 (5), own PZ (CW 2021–25, SSB 2023/25).

**None are in this repository.** Nothing in Track A — parser, validation gate,
off-time optimiser, band plan, pace curve — can be built or validated until they
land.

```
data/logs/
  own/     pz5co-2023-cw.log, pz5dx-2025-cw.log, …
  zone9/   <call>-<year>-<mode>.log
  bench/   v26k-2021-cw.log … v26k-2025-cw.log
  lcr/     <call>-<year><mode>.rpt
```

Commit as received, unmodified. The parser adapts to them, not the reverse.

Note: with the §2 URL structure known, the V26K and Zone-9 logs are
*re-downloadable* from the public archive — they are not unique operator assets.
The genuinely irreplaceable items are the **own private LCRs** (§3).

---

## 6. Prior art located on GitHub (all cloned and read)

| Repo | Value |
|---|---|
| `s53zo/n1mm-network-protocol` | Reverse-engineered N1MM protocol reference — ports, broadcast settings, payload examples. Substitutes for the blocked manual. See `n1mm_schema_observed.md`. |
| `bjornekelund/N1MMlistener` (C#) | Real `contactinfo`/`spot`/`RadioInfo` field sets |
| `s51ds/n1mmweb` (Go) | Second field set incl. full `dynamicresults` schema |
| `chibondking/contestscore` (JS) | Third field set; resolves the `exchange1`/`exchangel` ambiguity |
| `ok1xoe/CQWWDownloader` (Java) | Public-logs URL structure + rate-limit behaviour (§2) |
| **`ftl/conval`** (Go) | **Independent machine-readable encoding of the CQ WW rules, with worked scoring examples including a South American station.** Verifies the scoring model — see `scoring_model.md`. |
| `thxo/cabrillo` (Python) | Mature dependency-free Cabrillo v3 parser — candidate A1 foundation |
| `s53zo/SH6` | Contest log analysis tool (multipliers, spots, RBN compare, band opportunities) — prior art for A3/A4/A6 |

`s53zo` is the author of both the protocol notes and SH5/SH6 — worth treating as
a high-quality source generally.

---

## 7. What this session could NOT do

- **Read cqww.com or the N1MM manual directly.** Both blocked at the gateway by
  policy. Worked around via GitHub prior art, not bypassed.
- **Search the operator's Gmail.** No mail connector is installed for this
  account (`Gmail: installState = not_installed`) and no tool available here can
  install or authorise one. Remedy: connect Gmail at
  claude.ai → Settings → Connectors, then ensure it is enabled for the session.
  This is the fastest route to the own-station LCRs and submitted logs (§3, §5).
- **Search the operator's local machine.** This is an ephemeral cloud container;
  the filesystem holds only the cloned `BFA` repo. A filesystem-wide search for
  `*n1mm*` / `*cqww*` / `*cabrillo*` returned only files written this session.
  Nothing of the operator's is mounted here.

---

## 8. Acquisition checklist, ranked by work unblocked

1. **Reference log corpora** (§5) — blocks all of Track A.
2. **Own PZ5CO/PZ5DX private LCRs** (§3) — converts the accuracy value model
   from estimate to arithmetic. Fastest route: connect Gmail (§7).
3. **Late-2023 cty.dat** (§1) — blocks the A1 validation gate. Current file done.
4. **Public LCRs for benchmark stations** (§3).
5. **CQ WW public logs archive**, 3+ recent years (§2) — builds A2b.
6. **MASTER.SCP** (§4) — convenience.
7. **Live `<contactinfo>` capture from PZ5DX** — now three specific unknowns, not
   a blocker. See `n1mm_schema_observed.md`.
8. **Enable N1MM's UDP broadcasts** — all default to OFF. Hard prerequisite for
   every Track B module. See `n1mm_schema_observed.md` §2.
9. Existing N1MM CQ WW call-history file, if current — check `Sect` mapping.

Alternative to 3/5/6: extend this environment's egress allowlist to `cqww.com`,
`www.country-files.com`, `supercheckpartial.com` and the harvest runs here.
