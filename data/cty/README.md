# cty.dat files

AD1C country files — the entity / CQ zone / continent resolution spine. Wrong
resolution silently corrupts multipliers, accuracy checks and band plans.

## Contents

| File | Version | Provenance | Use |
|---|---|---|---|
| `cty-VER20251218.dat` | 2025-12-18 | `thefish12357/hamradio-award-system` | **current — 2026 operation** |
| `cty-VER20251125.dat` | 2025-11-25 | `s53zo/SH6` | cross-check |

The canonical source (`www.country-files.com`) is egress-blocked from the build
environment; these were retrieved from GitHub mirrors of the genuine AD1C file.

## Missing: per-contest-year files

One file **per contest year**, selected by the log's contest date — not one
global file. A 2025 cty.dat will misresolve callsigns in a 2023 log whose prefix,
entity or zone assignment changed in between, corrupting exactly the figures the
A1 validation gate checks.

**Required for the PZ5CO CW 2023 validation gate: a late-2023 cty.dat.**

Routes: country-files.com dated archives, or walk the git history of a repo that
vendors cty.dat and check out the commit nearest Nov 2023 — `jr8ppg/zlog_setup`
carries several dated versions side by side.

Naming: `cty-VERYYYYMMDD.dat`, using AD1C's own `VER` string (grep it out of the
file).

## Sanity check

Every file here must contain:

```
Suriname:                 09:  12:  SA:    4.00:    56.00:     3.0:  PZ:
    PZ;
```

Zone 9, ITU 12, continent SA. cty.dat uses west-positive longitude, so 56.00
means 56 W.
