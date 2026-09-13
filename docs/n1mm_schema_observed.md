# N1MM Logger+ UDP schema — observed field sets

Status: **PARTIALLY VERIFIED — not yet confirmed against a live PZ5DX capture.**

Source of this document: two independent third-party implementations that parse
real N1MM UDP datagrams, read directly from source (the official N1MM docs at
n1mmwp.hamdocs.com are unreachable from the build environment — egress-blocked).

| Ref | Implementation | Language | Repo |
|-----|----------------|----------|------|
| GO  | s51ds/n1mmweb `udp/xml.go` | Go | https://github.com/s51ds/n1mmweb |
| CS  | bjornekelund/N1MMlistener `Program.cs` | C# | https://github.com/bjornekelund/N1MMlistener |

Default contact broadcast port: **12060** (user-settable; confirm in the running
PZ5DX config — do not assume).

---

## Datagram types observed

`lookupinfo`, `contactinfo`, `contactreplace`, `contactdelete`,
`AppInfo`, `RadioInfo`, `spot`, `dynamicresults`, `Spectrum`,
`radio_setfrequency`, `N1MMRotor`.

---

## `<contactinfo>` / `<contactreplace>` — field list

Both refs agree on the following (identical in `contactinfo`, `contactreplace`,
and `lookupinfo`):

```
app              contestname      contestnr        timestamp
mycall           band             rxfreq           txfreq
operator         mode             call             countryprefix
wpxprefix        stationprefix    continent        snt
sntnr            rcv              rcvnr            gridsquare
section          comment          qth              name
power            misctext         zone             prec
ck               points           radionr          RoverLocation
RadioInterfaced  NetworkedCompNr  IsOriginal       NetBiosName
IsRunQSO         StationName      ID
```

GO-only: `IsClaimedQso`
CS-only: `Run1Run2`, `ContactType`
(version drift between N1MM releases — treat both as optional.)

### Gates for the toolkit — ANSWERED

- **`call` present** — yes, both refs.
- **`zone` present** — yes, both refs. *Received CQ zone is broadcast per QSO.*
  → **B5 (live accuracy assist) is viable.** This was the day-one go/no-go.
- **`points` present** — yes, both refs (per-QSO point value).
- **Mult flags present** — yes, three of them (see conflict below).
- **`IsRunQSO`, `radionr`, `continent`, `countryprefix`** — yes, all present.

### ⚠ FIELD-NAME CONFLICT — do not hardcode either spelling

The two refs disagree on two tag names, digit-one vs lowercase-L:

| CS (C#)          | GO (Go)          |
|------------------|------------------|
| `exchange1`      | `exchangel`      |
| `ismultiplier1`  | `ismultiplierl`  |

(`ismultiplier2` / `ismultiplier3` agree in both.)

This is a classic `1`/`l` transcription ambiguity and cannot be resolved from
secondary sources. **Mitigation: parse tag names case-insensitively and accept
both spellings as aliases.** This removes the failure mode permanently and makes
the live capture a confirmation step rather than a blocker.

### Still unverified — needs the live capture

- `band` formatting: may be a locale-delimited string (`"3,5"` vs `"3.5"`).
  Parse defensively.
- `rxfreq` / `txfreq` scaling (10-Hz units suspected, unconfirmed).
- `timestamp` format and whether it is UTC.
- Whether `zone` is populated for CQ WW specifically, or whether the received
  zone lands in `rcvnr` / `exchange1` for this contest's exchange definition.
  **This is the remaining real risk to B5** — the field exists, but which field
  CQ WW populates is contest-definition dependent.

---

## `<contactdelete>` — field list

```
app   timestamp   call   contestnr   StationName   ID
```

**Design consequence:** delete carries no band/mode/frequency. The live QSO store
**must be keyed on `ID`**, not on a composite (call, band, mode) match, or
deletes cannot be applied correctly. Same applies to `contactreplace`.

---

## `<spot>` — field list

```
app   StationName   dxcall   frequency   spottercall
timestamp   action   mode   comment   status   statuslist
```

→ **B3 (live mult inventory, assisted only) is viable** without a telnet client.
`status` / `statuslist` carry the mult/dupe flags. `action` distinguishes
add/delete. Semantics of `status` vs `statuslist` still to be confirmed by capture.

---

## `<dynamicresults>` — the score packet

Richer than expected. Carries:

- `contest`, `call`, `ops`, `score`, `timestamp`
- `class` with attributes: `power`, `assisted`, `transmitter`, `ops`, `bands`,
  `mode`, `overlay`
- `qth`: `dxcccountry`, `cqzone`, `iaruzone`, `arrlsection`, `stprvoth`, `grid6`
- `breakdown`: repeated `<qso band= mode=>` and `<point band= mode=>` elements

→ **B1 gets a per-band QSO and point breakdown for free**, not just an aggregate
score. Good fallback if per-QSO accumulation drifts, and a cheap cross-check.

---

## `<RadioInfo>` — useful for B4

```
app  StationName  RadioNr  Freq  TXFreq  Mode  OpCall  IsRunning  FocusEntry
  EntryWindowHwnd: Antenna Rotors FocusRadioNr IsStereo IsSplit
                   ActiveRadioNr IsTransmitting FunctionKeyCaption RadioName
```

→ B4 (band-plan nudge) can read what both radios are actually on without
inferring it from QSO traffic. `IsRunning` gives run/S&P state per radio.

---

## `<lookupinfo>` — possible pre-log warning channel

`lookupinfo` carries the **same field set as `contactinfo`** and is broadcast
when N1MM performs a callsign lookup — i.e. *before* the QSO is committed.

If the exchange fields are populated at that point, B5 could warn **before** the
operator presses Enter rather than after. That is strictly better than the
post-log design in the spec: a pre-log warning is a correction, a post-log
warning is an edit.

**To confirm in the capture:** what triggers `lookupinfo`, and whether `zone` /
`exchange1` are populated when it fires.

---

## Capture checklist for PZ5DX (station-specific, must be done on the real install)

1. Confirm the broadcast port in Config > Configure Ports > Broadcast Data.
2. Log one CQ WW QSO with a known non-trivial exchange. Dump the raw datagram
   bytes verbatim — not a parsed view.
3. Record: which field holds the received zone; `band` string format; `rxfreq`
   scaling; `timestamp` format and timezone; exact spelling of `exchange1` /
   `ismultiplier1`.
4. Edit that QSO, then delete it — capture `contactreplace` and `contactdelete`.
5. Type a callsign without logging — capture `lookupinfo` and check whether the
   exchange fields are populated.
6. Append the raw dumps to this file under a "Live capture" section.
