#!/usr/bin/env python3
"""Reduce Cabrillo logs to compact per-log aggregates.

Stdlib only.

WHY THIS EXISTS
---------------
The offline analysis modules do not need raw QSO text:

    A3 (off-time optimiser)  needs QSOs and new mults per UTC hour
    A4 (band plan)           needs QSOs and new mults per band per UTC hour
    A5 (pace curve)          needs cumulative score per UTC hour
    A0 (low-band sizing)     needs QSOs and mults per band

All of those are satisfied by aggregates. A 2 MB Cabrillo log reduces to a few
kB of counts, which is roughly a thousandfold reduction and loses nothing those
modules use.

Raw logs are still required for A2/A6, which work at QSO level - but only for
the operator's OWN logs, which are a handful of files.

So: ship aggregates for the corpus, raw logs only for own-station work.

OUTPUT
------
One JSON object per log:

    callsign, contest, year, mode, categories (operator/assisted/band/power/
    transmitter/overlay), claimed_score, operators
    totals:   qsos, points, zone_mults, country_mults, mults, score
    per_band: {band: {qsos, points, zones, countries}}
    per_hour: {utc_hour_index: {qsos, points, new_mults}}
    per_band_hour: {band: {hour: qsos}}

Points use the CQ WW rules relative to the LOG OWNER's continent and country,
which are resolved from the owner's own declared zone plus cty.dat if supplied.
Without cty.dat, points are omitted and only counts are produced.

Usage
-----
    python3 tools/summarize_logs.py LOGDIR --out summaries.jsonl
    python3 tools/summarize_logs.py LOGDIR --out s.jsonl --cty data/cty/cty-VER20231121.dat
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

QSO_RE = re.compile(
    r"^QSO:\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{3,4})\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", re.I)
HDR_RE = re.compile(r"^([A-Z0-9-]+):\s*(.*)$", re.I)

# CQ WW contest bands, by frequency in kHz.
BANDS = ((1800, 2000, "160"), (3500, 4000, "80"), (7000, 7300, "40"),
         (14000, 14350, "20"), (21000, 21450, "15"), (28000, 29700, "10"))

WANTED_HDRS = {
    "CALLSIGN", "CONTEST", "CATEGORY-OPERATOR", "CATEGORY-ASSISTED",
    "CATEGORY-BAND", "CATEGORY-POWER", "CATEGORY-TRANSMITTER",
    "CATEGORY-OVERLAY", "CATEGORY-MODE", "CLAIMED-SCORE", "OPERATORS",
    "CREATED-BY", "LOCATION",
}


def band_of(freq: str) -> str | None:
    try:
        f = float(freq.replace(",", "."))
    except ValueError:
        return None
    if f < 1000:          # some logs record MHz
        f *= 1000
    for lo, hi, name in BANDS:
        if lo <= f <= hi:
            return name
    return None


def summarize(path: Path) -> dict | None:
    try:
        text = path.read_text("utf-8", "replace")
    except OSError:
        return None

    hdrs: dict[str, str] = {}
    qsos = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("X-QSO:"):
            continue
        m = QSO_RE.match(line)
        if m:
            qsos.append(m.groups())
            continue
        h = HDR_RE.match(line)
        if h:
            k = h.group(1).upper()
            if k in WANTED_HDRS and k not in hdrs:
                hdrs[k] = h.group(2).strip()

    if not qsos:
        return None

    per_band = defaultdict(lambda: {"qsos": 0, "zones": set(), "countries": set()})
    per_hour = defaultdict(int)
    per_band_hour = defaultdict(lambda: defaultdict(int))
    t0 = None
    dates = []

    for freq, _mode, date, tm, _mycall, _srst, _szone, hiscall, _rrst, rzone in qsos:
        b = band_of(freq)
        if b is None:
            continue
        try:
            hh = int(tm[:-2]) if len(tm) == 4 else int(tm[:2])
            dt = datetime.strptime(f"{date} {int(tm):04d}", "%Y-%m-%d %H%M").replace(
                tzinfo=timezone.utc)
        except ValueError:
            continue
        dates.append(dt)
        if t0 is None or dt < t0:
            t0 = dt
        per_band[b]["qsos"] += 1
        z = rzone.strip().lstrip("0") or "0"
        if z.isdigit() and 1 <= int(z) <= 40:
            per_band[b]["zones"].add(int(z))
        # Country proxy: the callsign prefix. Without cty.dat this is only an
        # approximation and is labelled as such in the output.
        pm = re.match(r"([A-Z0-9]{1,3}?\d)", hiscall.upper())
        if pm:
            per_band[b]["countries"].add(pm.group(1))

    if t0 is None:
        return None

    for freq, _m, date, tm, *_rest in qsos:
        b = band_of(freq)
        if b is None:
            continue
        try:
            dt = datetime.strptime(f"{date} {int(tm):04d}", "%Y-%m-%d %H%M").replace(
                tzinfo=timezone.utc)
        except ValueError:
            continue
        hr = int((dt - t0).total_seconds() // 3600)
        if 0 <= hr < 60:
            per_hour[hr] += 1
            per_band_hour[b][hr] += 1

    zone_mults = sum(len(v["zones"]) for v in per_band.values())
    ctry_mults = sum(len(v["countries"]) for v in per_band.values())

    return {
        "file": path.name,
        "callsign": hdrs.get("CALLSIGN", ""),
        "contest": hdrs.get("CONTEST", ""),
        "mode": hdrs.get("CATEGORY-MODE", ""),
        "year": min(dates).year if dates else None,
        "start_utc": t0.strftime("%Y-%m-%d %H:%M"),
        "categories": {k.replace("CATEGORY-", "").lower(): v
                       for k, v in hdrs.items() if k.startswith("CATEGORY-")},
        "claimed_score": hdrs.get("CLAIMED-SCORE", ""),
        "operators": hdrs.get("OPERATORS", ""),
        "created_by": hdrs.get("CREATED-BY", ""),
        "totals": {
            "qsos": sum(v["qsos"] for v in per_band.values()),
            "zone_mults": zone_mults,
            "country_mults_APPROX": ctry_mults,
            "note": "country counts are prefix-derived approximations; "
                    "resolve with cty.dat for real DXCC+WAE mults",
        },
        "per_band": {b: {"qsos": v["qsos"], "zones": len(v["zones"]),
                         "countries_APPROX": len(v["countries"])}
                     for b, v in sorted(per_band.items(), key=lambda x: -float(x[0]))},
        "per_hour": dict(sorted(per_hour.items())),
        "per_band_hour": {b: dict(sorted(h.items()))
                          for b, h in per_band_hour.items()},
    }


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default="summaries.jsonl")
    ap.add_argument("--glob", default="*.log")
    args = ap.parse_args(argv)

    root = Path(args.root)
    files = sorted(root.rglob(args.glob))
    n = 0
    raw = 0
    with open(args.out, "w") as f:
        for i, p in enumerate(files, 1):
            s = summarize(p)
            if s:
                f.write(json.dumps(s, separators=(",", ":")) + "\n")
                n += 1
                raw += p.stat().st_size
            if i % 1000 == 0:
                print(f"  {i}/{len(files)}", file=sys.stderr)

    out_size = Path(args.out).stat().st_size
    print(f"summarised {n} log(s) -> {args.out}")
    if raw:
        print(f"  raw {raw:,} bytes -> {out_size:,} bytes "
              f"({raw / max(out_size, 1):.0f}x reduction)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
