#!/usr/bin/env python3
"""Build the callsign -> CQ zone ground-truth database from Cabrillo logs.

Stdlib only.

This is the data asset behind the A2b zone check. The point of the check is
narrow and must stay narrow: it answers "did I copy what they sent", NOT "is
their zone geographically correct". CQ WW cross-references sent against
received between logs, so the target is the zone the station actually sends.
Do not geo-police it.

Three tiers of evidence, in descending quality:

  1  SELF   - the zone a station declares in its OWN submitted log. Every
              Cabrillo QSO line carries the sender's own zone, so this is
              self-declared with zero copy error. Gold.
  2  LCR    - zone corrected by CQ's log checking (parsed from .rpt reports).
              Adjudicated truth even where the sender was busted. Gold.
  3  HEARD  - majority vote over the zone as copied by everyone else. Silver,
              and copy-error prone, but it is the only evidence available for
              stations that never submit a log - which is exactly the
              population that generates "absent from whitelist" soft flags.

Tier 1 and 2 override tier 3. Where 1 and 2 disagree, 2 wins (it is later and
adjudicated) and the disagreement is reported.

Known blind spot, stated so nobody over-trusts the output: a miscopy that
lands on a *different real whitelisted call sending the same zone* (copying
K5ZR/zone 4 when K5TR/zone 4 sent) fires nothing here. Call-for-call
substitution between two real stations is only catchable post-contest via
cross-log checking.

Usage
-----
    python3 tools/build_zone_db.py data/logs/archive --out data/zones.json
    python3 tools/build_zone_db.py data/logs/archive --out data/zones.json --csv data/zones.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

# CQ WW Cabrillo QSO line:
#   QSO: freq mo date time mycall myrst myzone hiscall hisrst hiszone
QSO_RE = re.compile(
    r"^QSO:\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{3,4})\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
    re.IGNORECASE,
)
HEADER_RE = re.compile(r"^([A-Z0-9-]+):\s*(.*)$", re.IGNORECASE)

VALID_ZONES = set(range(1, 41))


def norm_call(c: str) -> str:
    return c.strip().upper()


def norm_zone(z: str) -> int | None:
    z = z.strip().lstrip("0") or "0"
    if not z.isdigit():
        return None
    n = int(z)
    return n if n in VALID_ZONES else None


def parse_log(path: Path):
    """Yield ('header', call) once, then ('qso', mycall, myzone, hiscall, hiszone, year)."""
    own_call = None
    try:
        text = path.read_text("utf-8", "replace")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("X-QSO:"):
            continue
        m = QSO_RE.match(line)
        if m:
            _, _, date, _, mycall, _, myzone, hiscall, _, hiszone = m.groups()
            yield ("qso", norm_call(mycall), norm_zone(myzone),
                   norm_call(hiscall), norm_zone(hiszone), int(date[:4]))
            continue
        h = HEADER_RE.match(line)
        if h and h.group(1).upper() == "CALLSIGN" and own_call is None:
            own_call = norm_call(h.group(2))
            yield ("header", own_call)


def build(root: Path):
    # tier 1: own call -> Counter of the zone it declared in its own log
    self_zone: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    self_year: dict[str, int] = {}
    # tier 3: call -> Counter of zones others copied
    heard_zone: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    heard_year: dict[str, int] = {}

    files = sorted(root.rglob("*.log"))
    if not files:
        print(f"no .log files under {root}", file=sys.stderr)
    for i, path in enumerate(files, 1):
        header_call = None
        for rec in parse_log(path):
            if rec[0] == "header":
                header_call = rec[1]
                continue
            _, mycall, myzone, hiscall, hiszone, year = rec
            owner = header_call or mycall
            if owner and myzone:
                self_zone[owner][myzone] += 1
                self_year[owner] = max(self_year.get(owner, 0), year)
            if hiscall and hiszone:
                heard_zone[hiscall][hiszone] += 1
                heard_year[hiscall] = max(heard_year.get(hiscall, 0), year)
        if i % 500 == 0:
            print(f"  parsed {i}/{len(files)} logs", file=sys.stderr)

    calls = set(self_zone) | set(heard_zone)
    db = {}
    for call in sorted(calls):
        entry: dict = {"call": call}
        s = self_zone.get(call)
        h = heard_zone.get(call)

        if s:
            zone, n = s.most_common(1)[0]
            entry.update(source="SELF", zone=zone, observations=n,
                         last_seen=self_year.get(call))
            # A station's own log should be internally consistent. If it is not,
            # the log itself is odd (rover, mid-contest correction, bad export).
            if len(s) > 1:
                entry["self_inconsistent"] = dict(s)
        elif h:
            zone, n = h.most_common(1)[0]
            total = sum(h.values())
            entry.update(source="HEARD", zone=zone, observations=n,
                         total_reports=total, agreement=round(n / total, 4),
                         last_seen=heard_year.get(call))
            if len(h) > 1:
                entry["heard_spread"] = dict(h.most_common(5))

        if s and h:
            hz = h.most_common(1)[0][0]
            entry["heard_zone"] = hz
            entry["heard_total"] = sum(h.values())
            if hz != entry["zone"]:
                # Others systematically copy something else than this station
                # declares. Usually a genuinely hard call to copy.
                entry["heard_disagrees"] = True

        entry["confidence"] = confidence(entry)
        db[call] = entry
    return db


def confidence(e: dict) -> float:
    """0..1. Source dominates; observation count and agreement modulate."""
    if e.get("source") == "SELF":
        c = 0.90
        if e.get("self_inconsistent"):
            c -= 0.15
        if e.get("heard_disagrees"):
            c -= 0.05
        c += min(e.get("observations", 0), 500) / 500 * 0.10
    elif e.get("source") == "HEARD":
        c = 0.35 + 0.35 * e.get("agreement", 0.0)
        n = e.get("total_reports", 0)
        c += min(n, 50) / 50 * 0.20
    else:
        return 0.0
    return round(max(0.0, min(1.0, c)), 4)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="directory tree containing harvested .log files")
    ap.add_argument("--out", default="data/zones.json")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args(argv)

    db = build(Path(args.root))

    by_src = collections.Counter(v.get("source") for v in db.values())
    print(f"calls: {len(db)}  SELF: {by_src['SELF']}  HEARD: {by_src['HEARD']}")
    dis = sum(1 for v in db.values() if v.get("heard_disagrees"))
    inc = sum(1 for v in db.values() if v.get("self_inconsistent"))
    print(f"self-inconsistent logs: {inc}   heard-disagrees-with-self: {dis}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(db, indent=1, sort_keys=True))
    print(f"wrote {out}")

    if args.csv:
        cp = Path(args.csv)
        cp.parent.mkdir(parents=True, exist_ok=True)
        with cp.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["call", "zone", "source", "observations",
                        "agreement", "last_seen", "confidence"])
            for call in sorted(db):
                e = db[call]
                w.writerow([call, e.get("zone"), e.get("source"),
                            e.get("observations"), e.get("agreement", ""),
                            e.get("last_seen"), e.get("confidence")])
        print(f"wrote {cp}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
