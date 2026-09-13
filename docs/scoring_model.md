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
  Each worth 1, once per band.
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

## 5. NIL is not addressable from your own log

Published CQ WW norms: busted calls ~1.5% of QSOs, NIL ~1.0% of QSOs
(confidence 6/10 — these are blog-stated aggregates, not per-category).

NIL means the other station has no record of the contact. Causes:
- he miscopied **your** call — his error, your penalty
- he never logged it (dupe-check dropped it, logging slip)
- he did not submit a log → then it *cannot be checked* and is safe

**No amount of checking your own log detects a NIL.** You copied him correctly;
the failure is on his side of the exchange. Mitigation is operating practice —
call repetition discipline, confirming before logging under marginal conditions,
not accepting a partial — not software.

### Therefore the 5.78% is not all recoverable

PZ5CO CW 2023: claimed 15,208,050, final 14,328,600, reduction 879,450 = 5.78%.
Against published norms this is somewhat worse than typical, not catastrophic.
V26K at ~2.1% is genuinely excellent.

Decomposition (unknown until the LCRs are read — **this is why item 3 on the
acquisition list matters**):
- NIL component — **not software-addressable**
- Busted-call component — **partially** addressable (near-match warnings, live)
- Busted-exchange component — addressable (A2b), but cheap per unit
- Dupe component — trivially addressable, already handled by N1MM

The spec's "worth ~500k" assumes essentially the whole gap is recoverable.
A more defensible estimate is that software recovers **the addressable fraction
of the bust component only**. Pending the LCR decomposition, plan on
**~150-250k**, not 500k. Confidence 6/10 — this number should be replaced with a
computed one as soon as the LCRs are in.

---

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
