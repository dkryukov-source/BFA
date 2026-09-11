#!/usr/bin/env python3
"""Size the load-shifting prize from half-hourly Octopus Agile import data.

Usage:
    python3 analyse.py halfhourly.csv                    # default fleet
    python3 analyse.py halfhourly.csv --capacity 21.86 --power 8

Every figure is derived from metered half-hours. The optimiser has perfect
foresight of prices, so it is an upper bound no real controller can beat.
"""
import argparse, csv
from collections import defaultdict

def load(path):
    rows = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            ts = r["timestamp"]
            h = int(ts[11:13]) + (0.5 if ts[14:16] == "30" else 0.0)
            rows.append((ts, h, float(r["rate_p_per_kwh"]), float(r["consumption_kwh"])))
    return sorted(rows)

def in_window(h, lo, hi):
    return (lo <= h < hi) if lo < hi else (h >= lo or h < hi)

def charge_cost(rate, h, solar, export_p):
    """Marginal p/kWh to put energy into the battery in this slot.
    Inside the solar window the cheaper of importing or diverting export wins."""
    return min(rate, export_p) if (solar and in_window(h, *solar)) else rate

# --- perfect-foresight arbitrage -------------------------------------------
def optimise(rows, cap, power, eta, solar=None, export_p=12.0,
             chunk_at=12.0, min_margin_p=0.05):
    """Greedy successive-best-pair arbitrage, chunked at `chunk_at` so that
    overnight windows stay interior. Discharge can only displace metered import."""
    chunks, cur = [], []
    for r in rows:
        if cur and r[1] == chunk_at:
            chunks.append(cur); cur = []
        cur.append(r)
    if cur: chunks.append(cur)

    slot_cap = power * 0.5
    total_saving = total_shifted = 0.0
    for ch in chunks:
        n = len(ch)
        price = [c[2] for c in ch]; load = [c[3] for c in ch]
        cprice = [charge_cost(c[2], c[1], solar, export_p) for c in ch]
        chg = [0.0] * n; dis = [0.0] * n
        def soc_at(k):                      # stored energy entering slot k
            s = 0.0
            for i in range(k):
                s += eta * chg[i] - dis[i]
            return s
        while True:
            soc = [soc_at(k) for k in range(n + 1)]
            best = None
            for i in range(n):
                room_i = slot_cap - chg[i]
                if room_i <= 1e-9: continue
                headroom = cap - soc[i + 1]
                for j in range(i + 1, n):
                    if headroom <= 1e-9: break
                    room_j = min(slot_cap - dis[j], load[j] - dis[j])
                    if room_j > 1e-9:
                        gain = price[j] - price[i] / eta
                        if gain > 1e-6:
                            amt = min(room_j, room_i * eta, headroom)
                            # rank by margin per kWh, not total gain: a fat
                            # low-margin transfer otherwise blocks better pairs
                            if amt > 1e-9 and (best is None or gain > best[0]):
                                best = (gain, i, j, amt)
                    headroom = min(headroom, cap - soc[j + 1])
            if best is None or best[0] < min_margin_p: break
            _, i, j, amt = best
            dis[j] += amt; chg[i] += amt / eta
        total_saving += sum(price[k]*dis[k] - cprice[k]*chg[k] for k in range(n)) / 100
        total_shifted += sum(dis)
    return total_saving, total_shifted

# --- fixed clock schedule ---------------------------------------------------
def schedule(rows, cap, power, eta, charge, discharge, solar_p=None):
    """Charge during `charge`, discharge to meet load during `discharge`.
    solar_p costs charging as forgone export; None charges from grid at Agile."""
    soc = saving = delivered = 0.0
    slot_cap = power * 0.5
    for _, h, rate, kwh in rows:
        if in_window(h, *charge):
            add = min(slot_cap, (cap - soc) / eta)
            soc += add * eta
            saving -= (rate if solar_p is None else min(rate, solar_p)) * add
        elif in_window(h, *discharge):
            out = min(kwh, soc, slot_cap)
            soc -= out; delivered += out
            saving += rate * out
    return saving / 100, delivered

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--capacity", type=float, default=21.86, help="usable kWh (default: PW2 13.5 + GivEnergy 8.36)")
    ap.add_argument("--power", type=float, default=8.0, help="combined kW (default: PW2 5 + Giv 3)")
    ap.add_argument("--eta", type=float, default=0.88, help="round-trip efficiency")
    ap.add_argument("--export-price", type=float, default=12.0, help="p/kWh forgone when charging from solar")
    ap.add_argument("--charge", default="12-16", help="solar charge window, e.g. 12-16")
    args = ap.parse_args()

    rows = load(args.csv)
    days = len({r[0][:10] for r in rows})
    kwh = sum(r[3] for r in rows); cost = sum(r[2] * r[3] for r in rows) / 100
    yr = 365 / days
    cw = tuple(float(x) for x in args.charge.split("-"))

    print(f"=== {days} days, {len(rows)} half-hours, {rows[0][0][:10]} -> {rows[-1][0][:10]} ===")
    print(f"imported {kwh:.1f} kWh for GBP {cost:.2f} ex-VAT")
    print(f"  your weighted average   {cost*100/kwh:6.2f} p/kWh")
    print(f"  unweighted Agile average{sum(r[2] for r in rows)/len(rows):6.2f} p/kWh   "
          f"<- a flat, unmanaged load would pay this")
    neg = [r for r in rows if r[2] < 0]
    if neg:
        print(f"  {len(neg)} negative-price slots (min {min(r[2] for r in neg):.2f}p); "
              f"you imported {sum(r[3] for r in neg):.2f} kWh in them")

    print(f"\n--- where the import sits ---")
    for lo, hi in [(0, 7), (7, 16), (16, 21), (21, 24)]:
        w = [r for r in rows if in_window(r[1], lo, hi)]
        k = sum(r[3] for r in w); c = sum(r[2] * r[3] for r in w)
        print(f"  {lo:02.0f}:00-{hi:02.0f}:00  {k:8.1f} kWh ({100*k/kwh:4.1f}%)  "
              f"GBP {c/100:8.2f}  avg {c/k if k else 0:5.2f}p")

    print(f"\n--- fleet: {args.capacity:.2f} kWh usable, {args.power:.1f} kW, "
          f"eta {args.eta:.2f}, charge {args.charge} ---")
    perfect, shifted = optimise(rows, args.capacity, args.power, args.eta,
                                solar=cw, export_p=args.export_price)
    print(f"  perfect-foresight optimiser  GBP {perfect:7.2f}  "
          f"({perfect*yr:5.0f}/yr)  {shifted:.0f} kWh shifted   <- upper bound")

    print(f"\n--- marginal value of the discharge permission window ---")
    prev = 0.0
    for hi in [19, 21, 23, 1, 3, 5, 7, 8, 9, 10]:
        s, d = schedule(rows, args.capacity, args.power, args.eta, cw, (16, hi), args.export_price)
        print(f"  16:00-{hi:02d}:00   GBP {s:7.2f}  ({s*yr:5.0f}/yr)  "
              f"{d/days:5.2f} kWh/day delivered   marginal {s-prev:+6.2f}")
        prev = s

    best, _ = schedule(rows, args.capacity, args.power, args.eta, cw, (16, 8), args.export_price)
    print(f"\n  fixed schedule captures {100*best/perfect:.1f}% of the perfect optimiser "
          f"-> automation is worth GBP {(perfect-best)*yr:.0f}/yr")

    print(f"\n--- capacity sensitivity (charge {args.charge}, discharge 16:00-08:00) ---")
    prev = None
    for cap in [8.36, 13.5, 21.86, 30, 40, 55]:
        s, d = schedule(rows, cap, args.power, args.eta, cw, (16, 8), args.export_price)
        extra = "" if prev is None else f"   +{(s-prev[1])*yr:5.0f}/yr per +{cap-prev[0]:.1f} kWh"
        print(f"  {cap:5.1f} kWh usable   GBP {s:7.2f}  ({s*yr:5.0f}/yr){extra}")
        prev = (cap, s)

    print(f"\n--- how often capacity actually binds (16:00->08:00 window) ---")
    from datetime import date, timedelta
    byday = defaultdict(float)
    for ts, h, _, k in rows:
        if 8 <= h < 16:
            continue                      # daytime: outside the discharge window
        d = date.fromisoformat(ts[:10])
        night = d if h >= 16 else d - timedelta(days=1)
        byday[night.isoformat()] += k
    first, last = min(byday), max(byday)
    nightly = sorted(v for kx, v in byday.items() if first < kx < last)  # drop partial ends
    n = len(nightly)
    if n:
        print(f"  nightly window load: median {nightly[n//2]:.1f} kWh, "
              f"p25 {nightly[n//4]:.1f}, p75 {nightly[3*n//4]:.1f}, max {nightly[-1]:.1f}")
        over = sum(1 for v in nightly if v > args.capacity)
        print(f"  nights where window load exceeds {args.capacity:.2f} kWh usable: {over}/{n} "
              f"({100*over/n:.0f}%)  <- capacity binds only here")

if __name__ == "__main__":
    main()
