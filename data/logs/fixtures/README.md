# Parser fixtures

Real CQ WW Cabrillo files used to test the parser against formatting variants
seen in the wild. Both are from public GitHub repositories.

| File | Source | Tests |
|---|---|---|
| `k1ir-2017-cw.log` | `jasonhancock/go-cabrillo` | Genuine N1MM export, CQ-WW-CW 2017, single-band 40M. Column-padded QSO lines with runs of whitespace between fields. 75 QSOs. |
| `tk0c-2024-cw-synthetic.log` | `s53zo/SH6` | Synthetic but structurally real. Carries a **trailing transmitter-ID field** after the received zone — the multi-transmitter variant. 33 QSOs. |

## Variants these pin down

1. **Whitespace** — fields may be separated by one space or many. Never split on
   a fixed column.
2. **Trailing transmitter ID** — `QSO: ... K1ABC 599 05 0`. A parser that anchors
   the end of the QSO line will reject every multi-transmitter log.
3. **`X-QSO:`** lines — removed QSOs, must be ignored, not counted.

`tools/build_zone_db.py` parses both correctly: K1IR resolves to a self-declared
zone 5 over 75 QSOs, TK0C to zone 15 over 33, 109 distinct callsigns in total.

These are format fixtures only. They are **not** a substitute for the real
reference corpora listed in `extract_request.md`.
