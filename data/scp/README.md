# Super Check Partial

`MASTER.SCP` — the active-contester callsign list. Used by the A2/B5
"near-match to a corpus-frequent call" check, which per `scoring_model.md` §4 is
the *highest*-value accuracy check because it targets busted **callsigns**, the
error class carrying the 2x point penalty.

supercheckpartial.com is egress-blocked from the cloud session; this copy came
from a GitHub repository that vendors it.

| Field | Value |
|---|---|
| Calls | 46,136 |
| Source | `mbridak/FieldDayLogger` (`fdlogger/data/MASTER.SCP`) |

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

## Freshness

This copy is undated in-file. Refresh from supercheckpartial.com before the
contest — an SCP list more than a season old misses new and reactivated calls,
which is precisely the population the soft flag is meant to distinguish.
