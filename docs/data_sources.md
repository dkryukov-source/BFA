# Data sources — availability, blockers, and acquisition plan

## Build-environment egress reality

This environment routes outbound HTTPS through a policy-enforcing proxy.
Verified state as of 2026-09-13:

**Reachable**
- PyPI / files.pythonhosted.org (direct)
- npm registry
- github.com (`git clone` over HTTPS) and raw.githubusercontent.com
- Anthropic-side web search (returns summaries, not raw files)

**Blocked — gateway answers 403 to CONNECT**
- `cqww.com` — rules, public logs, public log-checking reports
- `www.country-files.com` — AD1C cty.dat, the canonical source
- `www.supercheckpartial.com` — MASTER.SCP
- `n1mmwp.hamdocs.com` — N1MM documentation
- `web.archive.org`, `r.jina.ai` — no proxy route either

Consequence: **no bulk harvesting of contest data can happen inside this
environment.** Every bulk dataset has to be fetched by the operator and committed,
or the egress allowlist has to be extended.

---

## 1. cty.dat (the spine)

Canonical source blocked. Obtained a genuine AD1C-format file from a GitHub
mirror instead:

| File | Version | Source | Verdict |
|------|---------|--------|---------|
| `data/cty/cty-VER20200405.dat` | VER20200405 (2020-04-05) | github.com/Tlf/tlf `share/cty.dat` | **STALE — placeholder only** |
| (rejected) | Feb 2013 | github.com/KB1RMA/dxcc | too old |

Sanity-checked: `Suriname: 09: 12: SA: 4.00: 56.00: 3.0: PZ:` — zone 9,
continent SA, as expected. 346 entities.

### Design point not in the original spec: pin cty.dat *per contest year*

The spec says "pin a dated cty.dat." That is not sufficient. Validating a
**November 2023** log against a **2026** cty.dat will misresolve any callsign
whose prefix, entity, or zone assignment changed in between — silently corrupting
exactly the mult and accuracy figures the validation gate depends on.

Correct approach: one cty.dat per contest year in `data/cty/`, selected by the
log's contest date. The CI gate for PZ5CO CW 2023 must run against a
**late-2023** cty.dat, not the newest one.

### Action required
Fetch from https://www.country-files.com/cty/ and commit:
- current file (for 2026 operation)
- the archived file closest to each reference log's contest date (country-files.com
  keeps dated archives) — at minimum CW 2023 for the validation gate

---

## 2. CQ WW public logs archive — the zone ground-truth corpus

`https://cqww.com/publiclogs/` — all submitted Cabrillo logs, by year and mode.
Blocked here. This is the bulk source for A2b.

### Refinement to the A2b harvest method

The spec proposes harvesting `hiscall + hiszone` (received zones) and taking a
most-frequent value. There is a strictly better source in the same files.

**Every submitted Cabrillo log states the sender's own zone in every QSO line**
(the `myzone` field). That is self-declared, zero copy error. One pass over the
archive yields `call -> own declared zone` directly for every station that
submitted a log, with no voting required.

Ground-truth ranking for the whitelist:

| Tier | Source | Quality |
|------|--------|---------|
| 1 | `myzone` from the station's own submitted log | gold — self-declared |
| 2 | LCR-corrected zone (see §3) | gold — adjudicated |
| 3 | Majority vote over `hiszone` as received by others | silver — copy-error prone |

Tier 3 remains necessary for stations that never submit logs (casual entrants) —
which is also exactly the population that generates the A2b "absent from
whitelist" soft flags. Keep it, but rank it below tiers 1 and 2.

---

## 3. CQ WW public log-checking reports (LCR/UBN)

`https://cqww.com/publiclcr/<year><mode>/<call>.rpt` — e.g.
`https://cqww.com/publiclcr/2019cw/v26k.rpt`. Blocked here.

**Important scope limit:** these are published only for *world high-scoring
stations in each category*, not for all entrants. This is a small targeted set
(order 10^2 per year), **not** a bulk zone source. Do not plan the A2b whitelist
around it.

What it is genuinely good for:
- The **benchmark** stations' real error composition — V26K's actual bust vs NIL
  vs exchange split, rather than an assumed one. This directly calibrates how much
  of PZ5CO's 5.78% is software-addressable.
- Zone corrections (tier 2 above) for the calls appearing in those reports.

Operator's own private LCRs for PZ5CO/PZ5DX are emailed to the submitting address
and are the highest-value accuracy dataset available — they say exactly which
QSOs were denied and why.

---

## 4. MASTER.SCP (super check partial)

`https://www.supercheckpartial.com/MASTER.SCP` — blocked. Needed for the A2 /
B5 "near-match to a corpus-frequent call" check. Roughly 50k active contest
callsigns, no zone data. Operator to fetch and commit.

Note: the public-logs harvest (§2) produces a superset of this with observation
counts and zones attached, so MASTER.SCP is a convenience, not a dependency.

---

## 5. Reference log corpora — **the actual blocker**

The spec lists these as "collected":

- Zone-9 SSB 2025 — 11 logs
- Zone-9 CW multi-op 2023–25 — 10 logs
- V26K CW 2021–25 — 5 logs
- Own PZ — CW 2021/22/23/24/25, SSB 2023/25

**None of them are in this repository.** The repo currently contains only a
static web page. Nothing in Track A — parser, validation gate, off-time
optimizer, band plan, pace curve — can be built or validated until these land.

Proposed layout:

```
data/logs/
  own/        pz5co-2023-cw.log, pz5dx-2025-cw.log, ...
  zone9/      <call>-<year>-<mode>.log
  bench/      v26k-2021-cw.log ... v26k-2025-cw.log
  lcr/        <call>-<year><mode>.rpt
```

Commit as-received, unmodified. The parser adapts to them, not the reverse.

---

## 6. Benchmark-station selection — challenge to the spec

The spec benchmarks the low-band QSO deficit against **V26K (Antigua)**.
V26K is **zone 8, North America**. Its low-band path geometry to both North
America and Europe differs materially from Suriname's. An unknown but non-zero
share of the stated ~1,400-QSO low-band gap is geography, not station capability
— i.e. structurally unattainable from PZ.

Recommendation: split the benchmark role.
- **Pace / accuracy benchmark (A5):** V26K is fine — it is a well-run
  comparable-category operation.
- **Low-band attainability benchmark:** use same-zone big guns —
  PJ2T, P40/P49, PJ4, 9Y4, 8P5. Zone 9, comparable paths, honest target.

---

## Acquisition checklist (operator)

Ranked by what unblocks the most work.

1. **Reference log corpora** (§5) — blocks all of Track A.
2. **cty.dat, current + 2023-dated** (§1) — blocks the A1 validation gate.
3. **Own PZ5CO/PZ5DX private LCRs** (§3) — calibrates the accuracy value model.
4. **Public LCRs for the benchmark stations** (§3) — same.
5. **CQ WW public logs archive**, at least 3 recent years (§2) — builds A2b.
6. **MASTER.SCP** (§4) — convenience.
7. **Live `<contactinfo>` capture from PZ5DX** — see `n1mm_schema_observed.md`.
   No longer a blocker; now a confirmation step.
8. **Existing N1MM CQ WW call-history file**, if current — check its `Sect`
   mapping and data freshness before trusting it.

Alternative to 2/5/6: extend this environment's egress allowlist to
`cqww.com`, `www.country-files.com`, `www.supercheckpartial.com`. That would let
the harvest run here instead of on the operator's machine.
