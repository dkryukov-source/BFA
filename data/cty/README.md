# cty.dat files

AD1C country files. `cty.dat` is the entity/zone/continent resolution spine —
wrong resolution silently corrupts multipliers, accuracy checks and band plans.

## Current contents

| File | Version | Provenance | Status |
|---|---|---|---|
| `cty-VER20200405.dat` | VER20200405 | github.com/Tlf/tlf `share/cty.dat` | **STALE placeholder** |

The canonical source (`www.country-files.com`) is egress-blocked from the build
environment. This file was retrieved from a GitHub mirror as a format-valid
stand-in so parser work can start. **It must not be used for any scored result.**

## Required

One file **per contest year**, selected by the log's contest date — not one
global file. A 2026 cty.dat will misresolve callsigns in a 2023 log whose
prefix, entity or zone assignment changed in between, corrupting exactly the
figures the A1 validation gate checks.

Naming: `cty-YYYYMMDD.dat`, using AD1C's own `VER` string.

Needed at minimum:
- current (2026 operation)
- late-2023 (the PZ5CO CW 2023 validation gate)
- one per reference-log contest year

Fetch from https://www.country-files.com/cty/ (current) and the dated archives
on the same site.

## Sanity check

Any file in this directory must contain:

```
Suriname:                 09:  12:  SA:    4.00:    56.00:     3.0:  PZ:
    PZ;
```

Zone 9, ITU 12, continent SA. (cty.dat uses west-positive longitude, so 56.00
means 56 W.)
