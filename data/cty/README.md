# cty.dat files

AD1C country files — the entity / CQ zone / continent resolution spine. Wrong
resolution silently corrupts multipliers, accuracy checks and band plans.

`www.country-files.com` is egress-blocked from the cloud session, so these were
retrieved from GitHub repositories that vendor the genuine AD1C file.

## Contents

| File | VER | Format | Use |
|---|---|---|---|
| `cty-VER20251218.dat` | 2025-12-18 | standard | **current — 2026 operation** |
| `cty-VER20251125.dat` | 2025-11-25 | standard | cross-check |
| `cty-VER20231121.dat` | 2023-11-21 | standard | **CQ WW CW 2023 — the A1 validation gate** |
| `cty-VER20231103.dat` | 2023-11-03 | standard | CQ WW SSB 2023 |
| `cty-VER20231228-bigcty.dat` | 2023-12-28 | BIG CTY | 2023 season cross-check |

## Why one file per contest year

Validating a November 2023 log against a 2025 cty.dat misresolves any callsign
whose prefix, entity or zone assignment moved in between — silently corrupting
the very mult and accuracy figures the validation gate exists to check.

**Select the file by the log's contest date**, not by what is newest.

Contest dates (last full weekend of the month):

| Contest | Dates | Use |
|---|---|---|
| CQ WW SSB 2023 | 28-29 Oct 2023 | `VER20231103` (6 days after) |
| CQ WW CW 2023 | 25-26 Nov 2023 | `VER20231121` (4 days before) |

`VER20231121` is the closest available file to CQ WW CW 2023 and is what the
**PZ5CO CW 2023 / 151-zones** gate must run against.

## Standard vs BIG CTY

AD1C publishes two variants of the same format:

- **standard** (~96-101 KB, 346 entities) — what contest loggers use.
- **BIG CTY** (~340-360 KB) — same entities, many more callsign exceptions and
  prefix overrides. Arguably *more* accurate for callsign resolution.

Both parse identically. Default to standard for parity with what CQ's own log
checking is likely to use; keep a BIG CTY copy to measure whether the extra
exceptions change any entity assignment in our logs. If they do, that difference
is itself worth knowing before trusting a mult count.

## Provenance

| File | Source repo |
|---|---|
| `VER20251218` | `thefish12357/hamradio-award-system` |
| `VER20251125` | `s53zo/SH6` |
| `VER20231121` | `trlinux/trlinux` (N6TR's TR Linux contest logger) |
| `VER20231103` | `rhgndf/cty-rs` |
| `VER20231228` | `ussjoin/qso.is` |

## Validation

Every file here passes:
- 346 entity records
- zero malformed entity lines (each has >= 8 colon-separated fields)
- the Suriname record reads:

```
Suriname:                 09:  12:  SA:    4.00:    56.00:     3.0:  PZ:
    PZ;
```

Zone 9, ITU 12, continent SA. cty.dat uses west-positive longitude, so 56.00
means 56 W. Files are CRLF, as AD1C distributes them — do not normalise.
