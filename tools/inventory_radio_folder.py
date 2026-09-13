#!/usr/bin/env python3
"""Inventory and triage a ham-radio folder for CQ WW contest material.

Cross-platform twin of inventory_radio_folder.ps1. Same classification logic.
Stdlib only.

Classifies every file by CONTENT, not extension alone, into:

    CABRILLO     contest log (START-OF-LOG). Extracts CALLSIGN, CONTEST, year
                 and QSO count - this is the triage that matters.
    LCR_UBN      CQ log-checking report. Highest value item in any such folder.
    ADIF         general logbook export.
    N1MM_DB      N1MM contest database (.s3db) - contains logged QSOs.
    CTY          AD1C country file (extracts its VER string).
    SCP          super check partial callsign list.
    CALLHISTORY  N1MM call-history file.
    OTHER        listed, not staged.

Usage
-----
    python3 tools/inventory_radio_folder.py "/path/to/Radio" --csv inv.csv
    python3 tools/inventory_radio_folder.py "/path/to/Radio" --stage /tmp/stage
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HEAD = 8192

RE_CALLSIGN = re.compile(r"^CALLSIGN:\s*(\S+)", re.I | re.M)
RE_CONTEST = re.compile(r"^CONTEST:\s*(\S+)", re.I | re.M)
RE_QSOYEAR = re.compile(r"^QSO:\s+\S+\s+\S+\s+(\d{4})-", re.I | re.M)
RE_VER = re.compile(r"VER\d{8}")
RE_CTYENT = re.compile(r"^\s*\w[\w .&'\-/]*:\s+\d{1,2}:\s+\d{1,2}:\s+[A-Z]{2}:", re.M)
RE_LCR = re.compile(r"Log Checking Report|\bUBN\b|Not in log|\bNIL\b", re.I)
RE_ADIF = re.compile(r"<EOH>|<CALL:\d+>", re.I)
RE_LCRCALL = re.compile(r"Call:\s*(\S+)", re.I)
RE_LCRYEAR = re.compile(r"(\d{4})\s+CQ\s*(?:WW|WORLD)", re.I)

STAGE_MAP = {
    "CABRILLO": "logs", "LCR_UBN": "lcr", "ADIF": "adif", "N1MM_DB": "n1mm",
    "CTY": "cty", "SCP": "scp", "CALLHISTORY": "callhistory",
}


def head_of(p: Path) -> str | None:
    try:
        with p.open("rb") as f:
            return f.read(HEAD).decode("ascii", "replace")
    except OSError:
        return None


def classify(p: Path) -> dict:
    row = {"path": str(p), "name": p.name, "ext": p.suffix.lower(),
           "size": 0, "type": "OTHER", "callsign": "", "contest": "",
           "year": "", "qsos": "", "note": ""}
    try:
        row["size"] = p.stat().st_size
    except OSError:
        row["note"] = "unstattable"
        return row

    # Documentation and source files can quote log or cty content verbatim and
    # would otherwise classify as data. Never content-sniff these.
    if row["ext"] in {".md", ".rst", ".txt.md", ".py", ".ps1", ".json", ".yaml", ".yml"}:
        row["note"] = "documentation/source - not classified"
        return row

    if row["ext"] == ".s3db":
        row["type"] = "N1MM_DB"
        row["note"] = "N1MM contest database - contains logged QSOs"
        return row

    h = head_of(p)
    if h is None:
        row["note"] = "unreadable"
        return row

    if "START-OF-LOG" in h.upper():
        row["type"] = "CABRILLO"
        m = RE_CALLSIGN.search(h)
        if m:
            row["callsign"] = m.group(1).upper()
        m = RE_CONTEST.search(h)
        if m:
            row["contest"] = m.group(1).upper()
        m = RE_QSOYEAR.search(h)
        if m:
            row["year"] = m.group(1)
        try:
            row["qsos"] = sum(
                1 for line in p.read_text("utf-8", "replace").splitlines()
                if line.upper().startswith("QSO:"))
        except OSError:
            pass
    elif row["ext"] == ".rpt" or RE_LCR.search(h):
        row["type"] = "LCR_UBN"
        m = RE_LCRCALL.search(h)
        if m:
            row["callsign"] = m.group(1).upper()
        m = RE_LCRYEAR.search(h)
        if m:
            row["year"] = m.group(1)
        row["note"] = "HIGHEST VALUE - names every denied QSO and why"
    elif RE_ADIF.search(h):
        row["type"] = "ADIF"
    elif RE_VER.search(h) or RE_CTYENT.search(h):
        row["type"] = "CTY"
        m = RE_VER.search(h)
        if m:
            row["note"] = m.group(0)
    elif row["ext"] == ".scp" or re.match(r"(?i)master.*\.scp$", p.name):
        row["type"] = "SCP"
        try:
            row["note"] = f"{len(p.read_bytes().splitlines())} lines"
        except OSError:
            pass
    elif re.search(r"^!!Order!!", h, re.M | re.I):
        row["type"] = "CALLHISTORY"
        row["note"] = "N1MM call history - check the Sect column carries the CQ zone"

    return row


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--csv", default="radio_inventory.csv")
    ap.add_argument("--stage", default=None,
                    help="copy classified contest material here, by type")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1

    rows = [classify(p) for p in sorted(root.rglob("*")) if p.is_file()]

    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["path", "name", "ext", "size", "type", "callsign",
                            "contest", "year", "qsos", "note"])
        w.writeheader()
        w.writerows(rows)
    print(f"manifest -> {args.csv}")

    print("\n=== SUMMARY ===")
    for t, n in Counter(r["type"] for r in rows).most_common():
        print(f"  {t:<12} {n}")

    cab = [r for r in rows if r["type"] == "CABRILLO"]
    if cab:
        print("\n=== CONTEST LOGS ===")
        for r in sorted(cab, key=lambda r: (r["year"], r["callsign"])):
            print(f"  {r['callsign']:<10} {r['contest']:<14} {r['year']:<6} "
                  f"{str(r['qsos']):>6} QSOs  {r['name']}")

    lcr = [r for r in rows if r["type"] == "LCR_UBN"]
    print("\n=== LOG CHECKING REPORTS (UBN) - HIGHEST VALUE ===")
    if lcr:
        for r in lcr:
            print(f"  {r['callsign']:<10} {r['year']:<6} {r['name']}")
    else:
        print("  none in this tree - check Gmail instead")

    if args.stage:
        stage = Path(args.stage)
        n = 0
        for r in rows:
            sub = STAGE_MAP.get(r["type"])
            if not sub:
                continue
            d = stage / sub
            d.mkdir(parents=True, exist_ok=True)
            tgt = d / r["name"]
            i = 1
            while tgt.exists():
                tgt = d / f"{Path(r['name']).stem}_{i}{Path(r['name']).suffix}"
                i += 1
            shutil.copy2(r["path"], tgt)
            n += 1
        print(f"\nstaged {n} file(s) -> {stage}")
        print("Copy into the BFA repo under data/ and commit BYTE-UNMODIFIED.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
