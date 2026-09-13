# N1MM Logger+ UDP schema — observed

Status: **VERIFIED against four independent sources. Live PZ5DX capture still
wanted for three specific items listed at the end, but B0 is no longer a blocker.**

The official N1MM documentation (n1mmwp.hamdocs.com) is unreachable from the
build environment — see `data_sources.md`. This document is reconstructed from
independent implementations that parse real N1MM datagrams, plus a
reverse-engineered protocol reference.

| Ref | Source | Language | Repo |
|-----|--------|----------|------|
| **PROTO** | s53zo/n1mm-network-protocol — protocol notes, docs, Python PoC | Python/MD | https://github.com/s53zo/n1mm-network-protocol |
| **CS** | bjornekelund/N1MMlistener | C# | https://github.com/bjornekelund/N1MMlistener |
| **GO** | s51ds/n1mmweb `udp/xml.go` | Go | https://github.com/s51ds/n1mmweb |
| **JS** | chibondking/contestscore `src/parsers/contact.js` | JS | https://github.com/chibondking/contestscore |

PROTO is by S53ZO, also the author of the SH5/SH6 contest log analysis tools.
It is explicitly *not* official N1MM documentation, but it is the most systematic
reference available and it agrees with the three parser implementations.

---

## 1. Port matrix — the spec got this partly wrong

| Port | Proto | Dir | Carries |
|---:|---|---|---|
| **12060** | UDP | out | `RadioInfo`, `AppInfo`, `contactinfo`, `contactreplace`, `contactdelete`, `lookupinfo`, `spot` |
| **12050** | UDP | out | **score XML (`dynamicresults`) — SEPARATE PORT** |
| 12070 | TCP+UDP | both | multi-user station sync + discovery (`DATA__…__DATA` frames) |
| 12040 | UDP | out | rotor commands |
| 13064 | UDP | in/out | radio / spectrum / control XML |
| 12080 | UDP | in | CW / serial / control bridge |

**The score packet is on 12050, not 12060.** The build spec assumed the score
aggregate arrived alongside contacts. It does not. **The live tool needs two
listening sockets.** Ports are user-settable; confirm both in the running config.

## 2. ⚠ Every broadcast defaults to OFF — config prerequisite

From PROTO's settings table, all of these default to `False`:

| Setting | Default | Gates |
|---|---|---|
| `IsBroadcastContact` | `False` | `contactinfo` / `contactreplace` / `contactdelete` |
| `IsBroadcastSpots` | `False` | `spot` — **B3 depends on this** |
| `IsBroadcastScoreUDP` | `False` | score XML — **B1 fallback depends on this** |
| `IsBroadcastExternalLookup` | `False` | `lookupinfo` — **pre-log warning depends on this** |
| `IsBroadcastRadio` | `False` | `RadioInfo` — **B4 depends on this** |
| `IsBroadcastAppInfo` | `False` | `AppInfo` |

**None of the live tooling receives a single byte until these are enabled in
N1MM.** This was not in the build spec and is a hard prerequisite — it belongs
in the pre-contest checklist, not discovered on contest morning.

### Destination defaults to loopback

`DestinationIPs` defaults to `127.0.0.1`, `DestinationPort` to `12060`.
So by default the tool must run **on the N1MM machine**. To offload the display
to a second box or a tablet, add its IP to `DestinationIPs` — the list accepts
multiple destinations and per-stream `ip:port` overrides
(`BroadcastContactAddr`, `BroadcastSpotsAddr`, `BroadcastScoreAddr`, …).
Score UDP defaults to `127.0.0.1:12050` via its own setting.

This is a useful degree of freedom the spec assumed away.

---

## 3. `<contactinfo>` / `<contactreplace>` / `<lookupinfo>` — field list

All three carry the same field set. CS and GO agree on:

```
app              contestname      contestnr        timestamp
mycall           band             rxfreq           txfreq
operator         mode             call             countryprefix
wpxprefix        stationprefix    continent        snt
sntnr            rcv              rcvnr            gridsquare
exchange1        section          comment          qth
name             power            misctext         zone
prec             ck               ismultiplier1    ismultiplier2
ismultiplier3    points           radionr          RoverLocation
RadioInterfaced  NetworkedCompNr  IsOriginal       NetBiosName
IsRunQSO         StationName      ID
```

GO-only: `IsClaimedQso` · CS-only: `Run1Run2`, `ContactType`
(version drift across N1MM releases — treat both sets as optional.)

### Gates — ANSWERED

- **`call` present** — yes, all refs.
- **`zone` present** — yes, all refs. Received CQ zone is broadcast per QSO.
  → **B5 (live accuracy assist) is viable.**
- **`points` present** — yes. Per-QSO point value.
- **`ismultiplier1/2/3`** — yes. Mult flags per QSO.
- **`IsRunQSO`, `radionr`, `continent`, `countryprefix`** — yes.

### ✅ FIELD-NAME CONFLICT — RESOLVED

GO renders two tags with a lowercase **L**: `exchangel`, `ismultiplierl`.
CS and JS use digit **one**: `exchange1`, `ismultiplier1`.

JS carries the explanation in a source comment: the **N1MM documentation itself
renders `exchange1` as `exchangel`** — a font/OCR artifact in the published docs.
GO was transcribed from those docs and inherited the bug; CS and JS were written
against real packets.

**Conclusion: the wire format is `exchange1` / `ismultiplier1` (digit one).**
Confidence 8/10.

**Mitigation regardless — accept both spellings.** JS does exactly this
(`c.exchange1 || c.exchangel`), arrived at independently. Parse tag names
case-insensitively and alias both forms. The ambiguity then cannot bite, and the
live capture becomes confirmation rather than a dependency.

---

## 4. Observed payload shapes (PROTO examples — abridged, illustrative)

```xml
<contactinfo>
  <app>N1MM</app>
  <contestname>CQWPXCW</contestname>
  <timestamp>2026-06-02 12:00:00</timestamp>
  <mycall>N0CALL</mycall>
  <call>K1ABC</call>
  <band>14.00</band>
  <mode>CW</mode>
  <snt>599</snt>
  <rcv>599</rcv>
  <StationName>N1MMA</StationName>
</contactinfo>
```

### ⚠ `band` is a decimal string in MHz — `14.00`

The locale risk the spec flagged is **real**: a comma-decimal Windows locale can
render this `14,00`. Normalise both separators before band mapping. Never parse
`band` as a number without replacing `,` with `.` first.

### ⚠ Frequency scaling differs between streams — concrete trap

| Stream | Field | Observed | Units |
|---|---|---|---|
| `spot` | `frequency` | `14074` | **kHz** |
| multi-user `DATA` frame | freq | `1407400` | **10 Hz** (kHz x100) |
| `contactinfo` | `rxfreq` / `txfreq` | — | **UNCONFIRMED** |

Do not assume one scaling across streams. `rxfreq`/`txfreq` scaling remains a
capture item.

### `timestamp` format

`2026-06-02 12:00:00` — space-separated, **no timezone marker**. Presumed UTC;
confirm in capture. Everything internal stays UTC per the spec's discipline rule.

---

## 5. `<contactdelete>`

```
app   timestamp   call   contestnr   StationName   ID
```

No band, no mode, no frequency. **The live QSO store must be keyed on `ID`**, not
on a composite (call, band, mode) match, or deletes and replaces cannot be applied
correctly. Same for `contactreplace`. Getting this wrong is how live counts drift.

## 6. `<spot>`

```
app  StationName  dxcall  frequency  spottercall  timestamp
action  mode  comment  status  statuslist
```

→ **B3 viable** without a telnet client. `action` = add/delete. `status` /
`statuslist` carry mult/dupe flags — exact encoding still to be confirmed.
`frequency` in **kHz** (see above).

## 7. `<dynamicresults>` — score packet (port 12050)

Full schema per GO:

- `contest`, `call`, `ops`, `score`, `timestamp`, `club`
- `class` attributes: `power`, `assisted`, `transmitter`, `ops`, `bands`, `mode`,
  `overlay`
- `qth`: `dxcccountry`, `cqzone`, `iaruzone`, `arrlsection`, `stprvoth`, `grid6`
- `breakdown`: repeated `<qso band= mode=>` and `<point band= mode=>`

PROTO's minimal example shows only `contest/call/ops/score/timestamp` — the
breakdown block appears to be emitted conditionally. **Do not require it**; fall
back to per-QSO accumulation when absent.

→ B1 gets per-band QSO and point totals for free when present, plus a cheap
cross-check against locally accumulated numbers.

## 8. `<RadioInfo>` — B4 input

```
app  StationName  RadioNr  Freq  TXFreq  Mode  OpCall  IsRunning  FocusEntry
  EntryWindowHwnd: Antenna Rotors FocusRadioNr IsStereo IsSplit
                   ActiveRadioNr IsTransmitting FunctionKeyCaption RadioName
```

→ B4 reads what both radios are actually on directly. `IsRunning` gives run/S&P
state per radio without inferring it from QSO traffic.

## 9. `<lookupinfo>` — pre-log warning channel

Same field set as `contactinfo`, broadcast when N1MM performs a callsign lookup —
**before the QSO is committed**. Gated by `IsBroadcastExternalLookup` (default
off).

If the exchange fields are populated when it fires, B5 warns **before** the
operator presses Enter. That is a correction rather than an edit, and is
materially better than the post-log design in the build spec. Worth designing for.

---

## Remaining capture items (PZ5DX, station-specific)

Reduced from "mandatory before building" to three specific unknowns:

1. **Which field carries the received zone in CQ WW specifically.** `zone` exists,
   but which field a given contest populates is contest-definition dependent — it
   could land in `zone`, `rcvnr`, or `exchange1`. **This is the one remaining real
   risk to B5.** Log one CQ WW QSO and look.
2. **`rxfreq` / `txfreq` scaling** in `contactinfo` (kHz? 10 Hz? Hz?).
3. **`timestamp` timezone** — confirm UTC.

Also worth capturing while there: `status`/`statuslist` encoding on a `spot`, and
whether `lookupinfo` populates the exchange.

Procedure: enable the broadcasts (§2), point `DestinationIPs` at the capture box,
dump **raw datagram bytes** — not a parsed view — for one logged QSO, one edit,
one delete, one typed-but-unlogged call. Append the raw dumps here.
