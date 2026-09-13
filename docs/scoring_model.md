# CQ WW scoring and penalty model — and what it does to the lever ranking

cqww.com is egress-blocked from the build environment (see `data_sources.md` §0),
so the rules text could not be read directly. Two independent sources were used
instead and **they agree**:

1. Anthropic-side web search of the CQ WW rules and log-checking blog.
2. **`ftl/conval`** — a Go library that evaluates ham contest results from
   machine-readable rule definitions. Its `rules/cq-ww-cw.yaml` is an independent
   encoding of the CQ WW CW rules **with worked scoring examples**, including one
   for a South American station (PY, zone 11) — the direct analogue of PZ.

Confidence is raised accordingly and marked per item. Verify verbatim against
`https://cqww.com/rules/2026_rules_cqww.pdf` before hardcoding anything that
carries money.

## 1. Scoring (for a PZ station, South America, zone 9)

- **Points:** different continent = 3; same continent, different country = 1;
  same country = 0 (still counts for multiplier credit).
  The 2-point variant applies **only** when both stations are in North America
  and does **not** apply to PZ. W/VE from PZ = different continent = **3 points**.
- **Multipliers:** zones per band + countries per band, summed over six bands.
  Each worth 1, once per band. The country list is **DXCC entities plus the WAE
  additions plus IG9/IH9** - not DXCC alone. Read from the rules directly by the
  local session; a parser resolving only DXCC will undercount countries.
- **Score** = total QSO points x total multipliers.
- **Exchange:** RST + CQ zone.

### Independently verified by conval's worked example

`conval/rules/cq-ww-cw.yaml` encodes:

```yaml
scoring:
  qsos:
    - their_continent: [other]                      value: 3
    - their_continent: [same], their_country: [other]   value: 1
    - my_continent: [na], their_continent: [na]     value: 2
    - their_country: [same]                          value: 0
  qso_band_rule: once_per_band
  multis:
    - property: cq_zone       band_rule: once_per_band   value: 1
    - property: dxcc_entity   band_rule: once_per_band   value: 1
```

and carries a worked example for `my_continent: sa, my_country: py, cq_zone: 11`:

| Worked QSO | Points | Mults |
|---|---|---|
| K1AB (NA, K) | **3** | 2 |
| VE1ABC (NA, VE) | **3** | 1 |
| VE2ABC (NA, VE, dup entity) | **3** | 0 |
| PY1ABC (same country) | **0** | 2 |
| LU1ABC (SA, different country) | **1** | 2 |

This is the PZ case exactly: **NA contacts score 3 from South America**, the
NA-NA 2-point rule does not reach us, and **same-country QSOs score 0 but still
give zone and country multiplier credit** — a detail easy to get wrong in the
parser and worth an explicit unit test.

Confidence **9/10** (two independent sources agreeing, one with worked examples).

## 2. Operating time

Standard **Single Operator** in CQ WW has **no operating-time limit and no
minimum off-time** — the full 48 hours are available. The 24-hour limit with
60-minute minimum off-times applies to the **Classic overlay** only.

Independently confirmed by conval, which encodes `duration: 48h` globally and
applies `duration: 24h` + `breaks: 1h` **only** under
`operator_mode: single, overlay: classic`.

This validates the A3 premise: the two 07:00-09:30z blocks are *discretionary
sleep*, not a rules constraint, and the optimiser is free to place, resize, or
eliminate them. Confidence **9/10** (two independent sources).

## 3. Log-checking penalties — THE ASYMMETRY THAT MATTERS

| Error class | Treatment |
|---|---|
| Busted **callsign** | QSO removed **+ penalty of 2x the QSO point value** |
| **NIL** (not in the other station's log) | QSO removed **+ penalty of 2x the QSO point value** |
| Busted **exchange** (wrong zone received) | QSO removed, **no additional penalty** |
| **Duplicate** | removed, no penalty |
| **Unique** | listed as `U` in the LCR; **credit not denied** on uniqueness alone |

Confidence 8/10. This is the single most load-bearing fact in the whole value
model — **verify it verbatim in the rules PDF before weighting anything.**

### Unit cost of each error, for a 3-point QSO from PZ

| Error | Points lost vs. claimed |
|---|---|
| Busted call / NIL | 3 (removed) + 6 (penalty) = **9** |
| Busted zone | 3 (removed) = **3** |

**A busted callsign costs three times what a busted zone costs.**

Plus, either can additionally cost a multiplier if that QSO was the only one with
that country (busted call) or zone (busted exchange) on that band. That is a
second-order term and is band-state dependent.

---

## 4. Consequence: the A2 internal priority is inverted

The spec names **A2b (US-zone whitelist)** the highest-value sub-module. A2b
targets **busted exchanges** — the *cheapest* error class, at 1/3 the unit cost of
a busted callsign, and one that carries no penalty multiplier.

**Reprioritise inside A2: callsign accuracy above zone accuracy.**

Concretely, the checks that deserve the most engineering are the ones that catch
a wrong *call*:
- near-match against a corpus-frequent callsign (log `K5ZR`, corpus has `K5TR`
  1,400 times and `K5ZR` never)
- unresolvable-in-cty.dat
- unique-against-corpus (as a *predictor of a busted call*, see §6)

A2b is still worth building — zone busts do cost points, and it is cheap once the
corpus exists — but it should not be the module the schedule is built around.

---

## 5. MEASURED — PZ5CO CW 2023, from the private log-checking report

The estimates below are no longer estimates. The operator's private LCR gives:

| | |
|---|---|
| Claimed score | 15,208,050 |
| Final score | **14,328,600** |
| QSOs after checking | 7,746 |
| Zones | **151** |
| Countries | **499** |
| Incorrect Call (IC) | **125** |
| Incorrect Exchange (IE) | **39** |
| Not In Log (NIL) | **16** |

### The figures verify themselves

151 + 499 = **650 multipliers**. And:

```
14,328,600 / 650 = 22,044   exactly
15,208,050 / 650 = 23,397   exactly
```

650 is the **only** integer that divides both scores anywhere in 600-700. So the
multiplier count was **identical before and after log checking**:

> **PZ5CO lost zero multipliers in 2023. The entire 879,450-point reduction was
> QSO points — 1,353 of them.**

That kills a second-order worry the build spec carried (busts costing multipliers)
for this log at least, and it makes the decomposition below exact rather than
modelled.

### The penalty model is confirmed by the operator's own log

Applying §3 (bust/NIL = removed + 2x penalty = 3x cost; exchange = 1x) at 3 points
per QSO:

```
(IC 125 + NIL 16) x 9  +  IE 39 x 3  =  1,386 predicted points lost
actual                                  1,353
ratio                                   0.976
```

A 2.4% overshoot is exactly what a handful of 1-point (South American) contacts
among the removed QSOs would produce. **The penalty asymmetry in §3 is correct.**

### Where the 879,450 actually went

| Class | QSOs | Points | Score | Share of loss | Software-addressable? |
|---|---:|---:|---:|---:|---|
| **Incorrect Call** | 125 | 1,098 | **713,839** | **81.2%** | **Yes — partially, and this is the target** |
| Not In Log | 16 | 141 | 91,371 | 10.4% | **No** — the other station didn't log you |
| Incorrect Exchange | 39 | 114 | 74,239 | 8.4% | Yes (A2b) |

## 5a. Consequences — this settles the module priority

**1. A2b, the US-zone whitelist, addresses 8.4% of the loss.** The build spec
names it the "HIGHEST-VALUE MODULE". On the operator's own numbers it is the
*smallest* of the three classes, on the cheapest penalty tier. Build it — it is
nearly free once the corpus exists — but it is not what the schedule should be
built around.

**2. Callsign accuracy is 81% of the problem.** IC outnumbers IE 3.2 to 1 *and*
costs 3x more per occurrence — roughly **10x the score impact**. The checks that
deserve the engineering are the ones that catch a wrong *call*:
near-match against a corpus-frequent callsign, unresolvable-in-cty.dat, and
unique-against-corpus as a bust predictor.

**3. NIL is 10.4% and is not yours to fix.** Operating practice, not software.

### Revised recovery estimate — upward

Earlier this document estimated 150-250k, reasoning from published averages. With
the real decomposition:

| If a live near-match check reduces IC by | Recovery |
|---|---|
| 30% | ~214k |
| 50% | ~357k |
| 70% | ~500k |

**Plan on 200-400k**, concentrated entirely in callsign copy. The earlier
150-250k figure was too pessimistic because it assumed the loss was spread across
classes; it is not — it is 81% in one class, and that class is the one a live
warning can actually attack.

## 5b. Cross-year context

| Contest | Final | QSOs | IC | IE | NIL |
|---|---:|---:|---:|---:|---:|
| PZ5CO CW 2022 | 6,335,373 | 4,478 | 34 | 30 | 14 |
| **PZ5CO CW 2023** | **14,328,600** | **7,746** | **125** | **39** | **16** |
| PZ5CO SSB 2023 | 10,505,077 | 6,421 | 84 | 73 | 23 |
| PZ5DX CW 2024 | 12,596,675 | 6,906 | 74 | 37 | 33 |
| PZ5DX CW 2025 | 2,225,483 | 4,048 | 67 | 39 | 10 |
| PZ5DX SSB 2025 | 2,162,320 | 4,328 | 50 | 34 | 13 |

Two things stand out.

**IC nearly quadrupled from 2022 to 2023** (34 to 125) while QSOs only rose 73%.
The 2023 bust *rate* per QSO roughly doubled. Worth understanding — higher rate,
bigger pileups, fatigue, or a different operating posture. It is also why 2023
is the right year to target: the accuracy headroom is real and recent.

**On SSB, IE is nearly as large as IC** (73 vs 84 in 2023). Zone copy is a
materially bigger share of the problem on phone than on CW. So A2b's value is
mode-dependent: minor for the CW target, substantial for SSB.

## 5c. THE 2025 COLLAPSE — unexplained, and it invalidates the 2026 target

| Entry | Final score | QSOs | Score per QSO |
|---|---:|---:|---:|
| PZ5DX CW 2024 | 12,596,675 | 6,906 | 1,824 |
| **PZ5DX CW 2025** | **2,225,483** | **4,048** | **550** |
| **PZ5DX SSB 2025** | **2,162,320** | **4,328** | **500** |

QSOs fell 41%; score fell **82%**. Score per QSO fell by two thirds, which means
the **multiplier count collapsed** — roughly 600 down to under 200. That is a
band-coverage collapse, not a rate problem: consistent with operating one or two
bands, a major antenna failure, or a part-time entry.

**The build spec's A5 sets a 2026 target near 15.3M, extrapolated from V26K's
trend and anchored on PZ5CO 2023 (14.3M). The operator's two most recent entries
are 2.2M.** Every abort checkpoint in the spec (h24 >= 7,525,000, h36 >=
10,700,000, h42 >= 13,500,000) is derived from that target and is therefore
currently built on an unexplained discontinuity.

**This is the highest-priority open question in the project.** Until it is
answered, no 2026 target is meaningful. The answer determines whether 2026 is a
title attempt or a rebuild:

- If 2025 was a deliberate part-time or single-band entry -> ignore it, target
  from 2023/2024.
- If 2025 was an antenna or station failure -> fixing it is worth ~10M, which
  dwarfs every software lever in this document combined, and the entire build
  priority changes.

Read the CATEGORY-BAND, CATEGORY-OPERATOR and CATEGORY-POWER headers of the 2025
logs, and the per-band QSO distribution, before anything else.

## 6. Uniques are a predictor, not a penalty class

The spec calls uniques "the #1 penalty source." In CQ WW they are not a penalty
class at all — the LCR lists them as `U` and credit is not denied on uniqueness
alone. A unique worked with a station that never submitted a log simply stands.

They remain a strong **diagnostic**: CQ's own log-checking analysis found 51.3%
of uniques were busted calls; operator lore puts it higher. Keep the check —
it is the cheapest available proxy for the expensive error class — but remove the
"penalty source" framing from the value model.

Confidence 7/10.

---

## 7. Lever re-ranking

The spec ranks: (1) accuracy ~500k, (2) scheduling ~500k-1M, (3) low-band
deficit — "not a software problem."

Score is multiplicative: `points x mults`. A QSO added on a low band contributes
to *points*, and the whole multiplier total rides on it.

Sensitivity, using the spec's own ~1,400-QSO low-band deficit
(**illustrative — needs the real claimed QSO/mult split from the 2023 log to
firm up; the QSO and multiplier totals below are estimated, not read**):

| Scenario | Effect on score |
|---|---|
| +1,400 low-band QSOs at ~3 pts | ~+16% on QSO points |
| plus the new low-band zone/country mults those QSOs bring | ~+3-6% on mults |
| **combined** | **~+20%, order +2.5M on a 14.3M base** |

That is roughly **4x the accuracy lever and 2-4x the scheduling lever.**

**The largest lever in the plan is the one the plan declares out of scope.**

"Antennas aren't software" is true and irrelevant. The *capex decision* —
160 vs 80, TX vs RX array, what a given structure returns in QSOs and mults from
this specific location at this point in the solar cycle — is a quantitative
question answerable from exactly the corpus this toolkit already ingests. A
module that outputs "an 80m four-square returns ~N QSOs and ~M mults = ~X points
from PZ in a November contest" is how the spend gets justified or killed.

**Recommendation: add module A0 — low-band opportunity sizing.** Same corpus,
same parser, benchmarked against same-zone stations (PJ2T, P40, PJ4, 9Y4, 8P5),
not against V26K (zone 8, North America, different low-band geometry — see
`data_sources.md` §6).

Revised ranking:

| Rank | Lever | Est. value | Type |
|---|---|---|---|
| 1 | Low-band capability (A0 sizes it; hardware delivers it) | ~2-3M | pre-contest capex |
| 2 | Sleep / band scheduling (A3, A4) | ~0.5-1M | pre-contest, pure software |
| 3 | Log accuracy (A2, B5) | ~0.15-0.25M | software + operating practice |

Note rank 2 is the best *software-only* return in the plan and needs no
station-specific data beyond the corpus. It is the highest-value thing that can
be built immediately once the logs land.
