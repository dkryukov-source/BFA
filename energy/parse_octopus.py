#!/usr/bin/env python3
"""Extract half-hourly consumption and Agile unit rates from Octopus Energy PDF bills.

Usage:
    python3 parse_octopus.py bills/*.pdf -o data/halfhourly.csv

Each bill is reconciled against its own stated totals; a mismatch above the
tolerance is reported rather than silently accepted.
"""
import argparse, csv, re, shutil, subprocess, sys
from collections import OrderedDict

MONTHS = {m: i for i, m in enumerate(
    "January February March April May June July August September October November December".split(), 1)}

# "14th July 2026" — the per-day page header
DAY_RE = re.compile(r'^(\d{1,2})(?:st|nd|rd|th)\s+([A-Z][a-z]+)\s+(\d{4})$')
# "00:00 - 00:30  21.03  0.41  8.622" — spacing around the dash varies; rates can be negative
ROW_RE = re.compile(r'^(\d{2}):(\d{2})\s*-\s*\d{2}:\d{2}\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)$')
# Bill-level totals used for reconciliation
TOTAL_RE = re.compile(r'Total consumption\s+([\d.]+)\s*kWh\s*@\s*([\d.]+)p/kWh')
EXPORT_RE = re.compile(r'Energy Exported\s+([\d.]+)\s*kWh\s*@\s*([\d.]+)p/kWh')
STANDING_RE = re.compile(r'Standing Charge\s+(\d+)\s*days\s*@\s*([\d.]+)p/day')


def pdf_to_text(path):
    if not shutil.which("pdftotext"):
        sys.exit("pdftotext not found. Install poppler-utils.")
    # -raw keeps each table row on one line; -layout scrambles the narrow columns.
    out = subprocess.run(["pdftotext", "-raw", path, "-"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def parse_bill(path):
    """Return (rows, stated) where rows is [(iso_timestamp, rate_p, kwh, cost_p)]."""
    rows, current = [], None
    stated = {"path": path}
    for line in pdf_to_text(path).split("\n"):
        line = line.strip()
        m = DAY_RE.match(line)
        if m and m.group(2) in MONTHS:
            current = f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
            continue
        m = ROW_RE.match(line)
        if m and current:
            hh, mm, rate, kwh, cost = m.groups()
            rows.append((f"{current}T{hh}:{mm}", float(rate), float(kwh), float(cost)))
            continue
        for key, rx in (("import", TOTAL_RE), ("export", EXPORT_RE), ("standing", STANDING_RE)):
            m = rx.search(line)
            if m and key not in stated:
                stated[key] = tuple(float(g) for g in m.groups())
    return rows, stated


def reconcile(rows, stated, tol=0.005):
    """Compare parsed rows against the bill's own printed totals."""
    kwh = sum(r[2] for r in rows)
    cost = sum(r[3] for r in rows)
    problems = []
    if "import" in stated:
        want_kwh, want_rate = stated["import"]
        if want_kwh and abs(kwh - want_kwh) / want_kwh > tol:
            problems.append(f"consumption {kwh:.2f} kWh vs bill {want_kwh:.2f} kWh")
        want_cost = want_kwh * want_rate
        if want_cost and abs(cost - want_cost) / want_cost > tol:
            problems.append(f"energy cost {cost/100:.2f} vs bill {want_cost/100:.2f} GBP")
    else:
        problems.append("no 'Total consumption' line found")
    return kwh, cost, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("-o", "--out", default="halfhourly.csv")
    args = ap.parse_args()

    merged, exports = OrderedDict(), []
    for path in args.pdfs:
        rows, stated = parse_bill(path)
        if not rows:
            print(f"  !! {path}: no half-hourly rows found — is this an Agile bill?")
            continue
        kwh, cost, problems = reconcile(rows, stated)
        days = len({r[0][:10] for r in rows})
        flag = "OK " if not problems else "!! "
        print(f"{flag}{path}: {len(rows)} slots / {days} days / {kwh:.1f} kWh / "
              f"{cost/kwh:.2f}p avg")
        for p in problems:
            print(f"     mismatch: {p}")
        if "export" in stated:
            exports.append(stated["export"])
        for r in rows:
            merged[r[0]] = r  # later bills win on overlapping periods

    if not merged:
        sys.exit("nothing parsed")
    out = sorted(merged.values())
    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp", "rate_p_per_kwh", "consumption_kwh", "cost_p"])
        w.writerows(out)

    kwh = sum(r[2] for r in out)
    cost = sum(r[3] for r in out)
    days = len({r[0][:10] for r in out})
    print(f"\nwrote {args.out}: {len(out)} slots, {days} days, {out[0][0][:10]} -> {out[-1][0][:10]}")
    print(f"  {kwh:.1f} kWh imported, GBP {cost/100:.2f} ex-VAT, {cost/kwh:.2f}p weighted average")
    if exports:
        print(f"  export tariff seen: " +
              ", ".join(f"{k:.1f} kWh @ {r:.2f}p" for k, r in exports))


if __name__ == "__main__":
    main()
