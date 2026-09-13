# Super Check Partial

`MASTER.SCP` — the active-contester callsign list. Used by the A2/B5
"near-match to a corpus-frequent call" check, which per `scoring_model.md` §4 is
the *highest*-value accuracy check because it targets busted **callsigns**, the
error class carrying the 2x point penalty.

supercheckpartial.com is egress-blocked from the cloud session; this copy came
from a GitHub repository that vendors it.

| Field | Value |
|---|---|
| Calls | 46,132 (excluding comment lines) |
| Release | **2022.06.03.00**, by Stu Phillips K6TU (stated in the file header) |
| Line endings | **CRLF** |
| Source | `mbridak/FieldDayLogger` (`fdlogger/data/MASTER.SCP`) |

Verified genuine: PZ5CO, V26K, RA3CO, PJ2T, P49Y, 8P5A, K5TR and 9Y4D are all
present, and the prefix distribution is properly global (DL 1222, VE 903,
JA 888, EA 858, SP, OK, IK, K4 ...), not US-centric.

**Strip CR before matching.** The file is CRLF, so `grep -x PZ5CO` and any
exact-match lookup silently fails against a trailing `\r`. This bit during
verification and would bite the near-match check identically.

## Trap: not every file named MASTER.SCP is MASTER.SCP

Several repositories ship a much smaller file under the same name. `ok2cqr/cqrlog`
carries one with **5,745** calls whose own header reads
`FOC, CWops, HSC and ops active on CW` — a CW-club subset, not the real list.

Using that as the near-match reference would be actively harmful: almost every
legitimate callsign would be absent from it, so the "unverified callsign" soft
flag would fire near-continuously and the operator would mute it within the first
hour. **Check the line count.** The genuine file is order 10^4-10^5 calls, not
10^3.

## Not a hard dependency

The public-logs harvest (`tools/harvest_cqww.py` + `tools/build_zone_db.py`)
produces a superset of this with observation counts and CQ zones attached.
MASTER.SCP is a convenience and a cross-check, not the foundation.

## Freshness — this copy is four years stale, and it shows

Release **2022.06.03**. Concrete demonstration of why that matters:

**`PZ5DX` is absent from this file.** The operator's own current callsign is not
in a 2022 SCP list. Every station that came on the air or changed call since
mid-2022 is likewise missing — and those are exactly the stations the
"unverified callsign" soft flag is supposed to distinguish from genuine miscopies.

Using this as-is would produce a soft-flag false-positive rate high enough to get
the check muted, which is the failure mode that matters: a muted check catches
nothing.

**Refresh from supercheckpartial.com before the contest.** Until then treat this
copy as a format reference and a rough cross-check, not as the near-match
corpus.
