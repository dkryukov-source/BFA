#!/usr/bin/env python3
"""Harvest CQ WW public logs and public log-checking reports.

Stdlib only - runs on Windows, macOS or Linux with a bare Python 3.9+.

URL structure (from ok1xoe/CQWWDownloader, GPL-3.0, and confirmed live examples):

    index        https://cqww.com/publiclogs/
    year+mode    https://cqww.com/publiclogs/{YYYY}{cw|ph|rtty}/
    one log      https://cqww.com/publiclogs/{YYYY}{mode}/{callsign}.log
    one report   https://cqww.com/publiclcr/{YYYY}{cw|ph}/{callsign}.rpt

'ph' means SSB.

Politeness: cqww.com issues HTTP/2 GOAWAY under load. The reference
implementation defaults to 100 concurrent and its own README recommends
dropping to 10-20. Default here is 8 with a small inter-request delay.
Do not raise it casually - a year is order 8,000 files.

Resumable: an existing non-empty target file is skipped unless --overwrite.

Examples
--------
    # everything, both modes, 2021-2025
    python3 tools/harvest_cqww.py logs --years 2021-2025 --out data/logs/archive

    # one station across all years, both modes
    python3 tools/harvest_cqww.py logs --call PZ5CO --years 2019-2025

    # public log-checking reports for the benchmark stations
    python3 tools/harvest_cqww.py lcr --call V26K --years 2015-2024
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import html.parser
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_LOGS = "https://cqww.com/publiclogs"
BASE_LCR = "https://cqww.com/publiclcr"
UA = "bfa-contest-toolkit/0.1 (+research; contact via repo owner)"

# cqww uses 'ph' in URLs for SSB. RTTY exists for logs only.
MODE_SUFFIX = {"cw": "cw", "ssb": "ph", "ph": "ph", "rtty": "rtty"}

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


class LinkParser(html.parser.HTMLParser):
    """Collect href values from an index page."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def fetch(url: str, retries: int = 4, timeout: int = 60) -> bytes:
    """GET with exponential backoff. Raises on final failure."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 404 is a real answer, not a transient failure - do not retry.
            if e.code == 404:
                raise
            last = e
        except Exception as e:  # noqa: BLE001 - network layer is broad by nature
            last = e
        if attempt < retries:
            time.sleep((2 ** attempt) + random.uniform(0, 0.4))
    raise RuntimeError(f"GET failed after {retries + 1} attempts: {url}: {last}")


def list_directory(url: str, suffix: str) -> list[str]:
    """Return filenames ending in `suffix` linked from an index page."""
    body = fetch(url).decode("utf-8", "replace")
    p = LinkParser()
    p.feed(body)
    names: list[str] = []
    seen: set[str] = set()
    for h in p.hrefs:
        h = h.split("?")[0].split("#")[0]
        name = h.rstrip("/").split("/")[-1]
        if name.lower().endswith(suffix) and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def parse_years(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def download_one(url: str, dest: Path, overwrite: bool, delay: float,
                 counters: dict, lock: threading.Lock) -> None:
    if dest.exists() and dest.stat().st_size > 0 and not overwrite:
        with lock:
            counters["skipped"] += 1
        return
    try:
        data = fetch(url)
    except urllib.error.HTTPError as e:
        with lock:
            counters["missing" if e.code == 404 else "failed"] += 1
        if e.code != 404:
            log(f"  ERR {e.code} {url}")
        return
    except Exception as e:  # noqa: BLE001
        with lock:
            counters["failed"] += 1
        log(f"  ERR {url}: {e}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    with lock:
        counters["ok"] += 1
        counters["bytes"] += len(data)
    if delay:
        time.sleep(delay)


def harvest_category(base: str, year: int, mode_suffix: str, ext: str,
                     out_root: Path, args, only_call: str | None) -> dict:
    cat = f"{year}{mode_suffix}"
    cat_url = f"{base}/{cat}/"
    out_dir = out_root / cat
    counters = {"ok": 0, "skipped": 0, "failed": 0, "missing": 0, "bytes": 0,
                "index_failed": 0, "absent": 0}
    lock = threading.Lock()

    if only_call:
        names = [f"{only_call.lower()}{ext}"]
    else:
        try:
            names = list_directory(cat_url, ext)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # A category that does not exist is a real answer, not a
                # failure: publiclcr has no 2025 yet, and rtty is logs-only.
                log(f"[{cat}] no such category")
                counters["absent"] = 1
                return counters
            # Any other HTTP status means we could not enumerate a category
            # that probably DOES exist. Silently returning zeros here made a
            # skipped year indistinguishable from a complete one.
            log(f"  ERR [{cat}] index HTTP {e.code} - CATEGORY SKIPPED")
            counters["index_failed"] = 1
            return counters
        except Exception as e:  # noqa: BLE001
            log(f"  ERR [{cat}] index failed: {e} - CATEGORY SKIPPED")
            counters["index_failed"] = 1
            return counters
        if not names:
            log(f"  ERR [{cat}] index listed no {ext} files - CATEGORY SKIPPED")
            counters["index_failed"] = 1
            return counters

    log(f"[{cat}] {len(names)} file(s) -> {out_dir}")
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [
            ex.submit(download_one, cat_url + n, out_dir / n,
                      args.overwrite, args.delay, counters, lock)
            for n in names
        ]
        for _ in cf.as_completed(futs):
            pass

    log(f"[{cat}] ok={counters['ok']} skipped={counters['skipped']} "
        f"missing={counters['missing']} failed={counters['failed']} "
        f"bytes={counters['bytes']}")
    return counters


def write_manifest(out_root: Path) -> None:
    """Record every harvested file with size and sha256 for integrity/resume."""
    entries = []
    for p in sorted(out_root.rglob("*")):
        if p.is_file() and p.suffix in (".log", ".rpt"):
            data = p.read_bytes()
            entries.append({
                "path": str(p.relative_to(out_root)).replace("\\", "/"),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
    man = out_root / "manifest.json"
    man.write_text(json.dumps(
        {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "count": len(entries), "files": entries}, indent=2))
    log(f"manifest: {len(entries)} files -> {man}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["logs", "lcr"],
                    help="'logs' = public Cabrillo logs; 'lcr' = public log-checking reports")
    ap.add_argument("--years", default="2021-2025",
                    help="e.g. 2023 or 2021-2025 or 2019,2021-2023")
    ap.add_argument("--modes", default="cw,ssb",
                    help="comma list of cw,ssb,rtty (rtty is logs-only)")
    ap.add_argument("--call", default=None,
                    help="single callsign (skips the index listing)")
    ap.add_argument("--out", default=None, help="output root directory")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="parallel downloads (default 8; the site sends GOAWAY when pushed)")
    ap.add_argument("--delay", type=float, default=0.05,
                    help="seconds to pause after each successful download")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-download files that already exist")
    ap.add_argument("--no-manifest", action="store_true")
    args = ap.parse_args(argv)

    if args.concurrency > 20:
        log("WARNING: concurrency above 20 triggers HTTP/2 GOAWAY on cqww.com. "
            "The reference implementation's own README recommends 10-20.")

    base = BASE_LOGS if args.what == "logs" else BASE_LCR
    ext = ".log" if args.what == "logs" else ".rpt"
    out_root = Path(args.out) if args.out else Path("data") / (
        "logs/archive" if args.what == "logs" else "lcr")

    modes = []
    for m in args.modes.split(","):
        m = m.strip().lower()
        if not m:
            continue
        if m not in MODE_SUFFIX:
            ap.error(f"unknown mode {m!r}")
        if args.what == "lcr" and MODE_SUFFIX[m] == "rtty":
            log("note: rtty has no public LCR category - skipping")
            continue
        modes.append(MODE_SUFFIX[m])
    modes = sorted(set(modes))

    total = {"ok": 0, "skipped": 0, "failed": 0, "missing": 0, "bytes": 0,
             "index_failed": 0, "absent": 0}
    for year in parse_years(args.years):
        for ms in modes:
            c = harvest_category(base, year, ms, ext, out_root, args, args.call)
            for k in total:
                total[k] += c[k]

    log(f"\nTOTAL ok={total['ok']} skipped={total['skipped']} "
        f"missing={total['missing']} failed={total['failed']} "
        f"bytes={total['bytes']}")
    if total["absent"]:
        log(f"      {total['absent']} category/categories did not exist (normal)")
    if total["index_failed"]:
        log(f"\n*** {total['index_failed']} CATEGORY/CATEGORIES WERE SKIPPED "
            f"because their index could not be listed. The data for those "
            f"year/mode combinations is INCOMPLETE. Re-run them. ***")

    if not args.no_manifest and out_root.exists():
        write_manifest(out_root)

    # A skipped category is a failure: a silent zero here previously made an
    # incomplete harvest look like a clean one.
    return 1 if (total["failed"] or total["index_failed"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
