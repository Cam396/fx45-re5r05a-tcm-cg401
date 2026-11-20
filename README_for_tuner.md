# 2004.0 Infiniti FX45 TCM (RE5R05A): calibration definition v3.5, research grade

Prepared 2026-11-19 by the car's owner from a read-out of their own TCM, plus code analysis (Ghidra, PowerPC), logged drive data and
read-only live RAM reads. **Nothing in this definition has been flash-tested.** It's offered as a map to save you time, not as a
validated tune base.

## The module

| | |
|---|---|
| vehicle | 2004.0 Infiniti FX45 AWD, VK45DE, RE5R05A 5-speed (2004.0 TCM: DTCs P1701/P1704, no P0700) |
| hardware | Bosch GS19, Motorola/Freescale **MPC555** (PowerPC), 448 kB internal flash |
| software | "ERCOSEK V3.0.11 OAK (c)ETAS"; ROM id **CG401** at 0x6FA61; CAN id string "RX0612" |
| image | 0x00000-0x6FFFF, 458,752 bytes, md5 `987776c9c8e483312ad23c55c69e41e6` (read twice over K-line, verified) |
| layout | 4 signed blocks: boot BB020204, stub CBBB0202, application COBB0202, **calibration DAC14924 at 0x60000** |
| diagnostics | K-line KWP2000, physical address 0x18 (header 81 18 FC) |
| RAM | SRAM 0x3F9800-0x3FFFFF; base task counter 0x3FA438 = **10 ms** per count (live) |
| scheduler | ERCOSEK slot table 0x10C00: tasks T45 10 ms, **T44 20 ms (all shift sequencing)**, T43 50 ms, T42 100 ms |

**Checksum:** the calibration carries a **CRC-16/XMODEM at 0x6FFFC over 0x60090-0x6FFFB**. Every edit needs it recomputed. All 13
block/header CRCs in the image were recomputed and match (method in `reports/01`). RomRaider doesn't fix it.

## Formats in this package

- **`CG401_tcm_tables.csv`**: one row per item (address, name, category, layout, storage, size, axes, units, raw↔units expressions,
  confidence, source report, note). Tool-neutral, meant for building your own definition in Osiris, EcuTek, EcuFlash, TunerPro, etc.
- **`CG401_tcm.xdf`**: TunerPro XDF (big-endian, base offset 0, same 553 tables as the XML). [xdfkit](https://github.com/nyetlabs/xdfkit) converts XDF to a WinOLS map pack (KP).
- `CG401_tcm_romraider.xml`: RomRaider definition (each table description carries `[confidence, source] note`).
- `CG401_tcm.md`: everything readable, with stock values. `CG401_tcm.json`: machine-readable, with raw values and segment records.

**UpRev / EcuTek:** neither imports third-party definitions; both add a controller from a dump made with their own tool (EcuTek: ProECU
Utility Mode → "Dump Details for EcuTek" / Help → Submit New ROM; UpRev: dump with their software and send it). This package is meant as
reference for their engineers: the CSV, the reports and the checksum notes save the mapping work.

## What's in the definition (422 items, 553 RomRaider tables, all inside 0x60090-0x6FFFB, none overlapping; 85 CONFIRMED, 337 STRONG, 0 CANDIDATE)

| area | items | confidence |
|---|---|---|
| Gear ratios | 1 | CONFIRMED (matches logged turbine/output ratios) |
| Shift lines: every pattern × range × gear (168 real curves) | 168 + 7 scalars/maps | D normal CONFIRMED: 15/16 factory shift speeds (FSM AT-62) inside the factory window; **WOT 1→2 lands at 66 km/h on the car (factory 64-68)**. Other patterns STRONG |
| Lock-up lines: full and slip, every mode × range × gear (89 real curves) | 90 | **full lock-up on/off naming CONFIRMED**: D 5th on 71 / off 58 km/h at closed throttle and 196 / 142 at half pedal, all inside FSM AT-63 (66-74 / 53-61, 191-199 / 136-144); slip pair STRONG |
| Line pressure: clamps, steady and per-shift base curves, converter ratio, throttle floor, ATF factor | 16 | STRONG; **unit 0.1 kPa STRONG** (max 1372 kPa = FSM D stall 1310-1500, AT-53; idle minimum ~100 kPa above FSM, open) |
| Shift quality: phase timers (4 banks × 14 shifts × 4 phases × 8 torque bands + progress thresholds; **1 tick = 20 ms, CONFIRMED**), apply-ramp steps, torque-cut extra ramp, initial apply pressure by element, upshift/downshift apply end-target coefficients, downshift start detection, shift-time targets | 116 | structure CONFIRMED in code; **A = engaging-element apply command on upshifts, CONFIRMED live** (reports/06); element columns D/C, HLR/C, I/C, FR/B CONFIRMED vs FSM |
| Torque reduction during shifts (14 shifts × torque × rpm) | 14 | upshifts 1-2 CONFIRMED on CAN logs; rest STRONG |
| Mode enables: continuous-shift, lift-foot (disabled in stock), fallback phase-timer banks | 3 | STRONG |
| ATF temperature sensor curves 1 and 2 (voltage → the ATF-temp unit every temp threshold uses) | 2 | CONFIRMED (live RAM: 3FB77B 47 → 3FB794 132 = curve); FSM points: 0 °C ≈ 88, 20 °C ≈ 100, 80 °C ≈ 151 raw (sensor 1) |

**Shift index (CONFIRMED, table 0x4B1E0):** 0 = 1→2, 1 = 2→3, 2 = 3→4, 3 = 4→5, 4 = 2→1, 5 = 3→1, 6 = 3→2, 7 = 4→1, 8 = 4→2, 9 = 4→3, 10 = 5→1, 11 = 5→2,
12 = 5→3, 13 = 5→4.

Segment curves are stored as `{x0, y0, slope}` records with y = y0 + slope·(x − x0)/16 between breakpoints. Three formats (u8, u16, and u8-x/u16-y)
are described in `CG401_tcm.md` and the generator. The definition exposes them as raw records, so editing a line means editing
breakpoints and slopes, not a grid.

**Solenoids (CONFIRMED):** MPWM16 TCC, MPWM3 line pressure, MPWM0 I/C, MPWM1 FR/B, MPWM2 D/C, MPWM17 HLR/C, plus an on/off LC/B.

## How a shift runs (live, reports/06)

On an upshift the engaging element's command (RAM 0x3FB502) starts at the initial-apply table value, climbs by the ramp step 0x3FB3D4
every 20 ms (task T44; ramp = (target − start) / steps, steps from the apply-ramp tables; the adaptive cell would scale it, but the stock clamp holds it at 256), then jumps to full
(10000) when the measured ratio says the shift is done. Coast downshifts use the second sequencer (0x3FB506) the same way. The
adaptive cell for the shift/torque band being executed shows up in 0x3FB694, which is a handy way to tag shifts in a RAM log.

## Not mapped / not confirmed

- **Manual mode** (reports/09): lever switches arrive on CAN 0x2DE byte 0 (0x02 D gate, 0x01 manual gate, 0x04 up, 0x08 down); the slot-4 shift lines double as the manual tap permission lines (over-rev / lugging guards); cal 0x60337 b0 = start manual mode at the current gear.
- **DTCs** (reports/08): code table 0x47BDC, status bits, P0744 (12 s of slip ≥ speed/2 + 40 with lock-up commanded), P17xx vs P184x split by the in-gear ratio windows 0x4B0BA; pressure-switch word 3FB20F; every other monitor's gate, counter and ROM limit (08 §4: solenoid circuit checks 2 s, speed sensors 0.8 s, P1730 interlock 1.9 s, P1731 at ≥ 1,200 rpm, P1825 disabled in ROM).
- **Not in the definition:** the DTC limits as editable tables (they are listed in 08 §4 only). CAN 0x2A5: only byte 3 bits 0-1 are read (both set selects the
  fallback timer banks below 5 km/h); on this car the byte is 0x80, so that set is never used. Its sender is unknown (needs a pressure reference).
- ~~Phase-timer tick length~~: **20 ms** (CONFIRMED v3.2: the shift code runs in the 20 ms task of the schedule table, matching the live ramp rate).
- **Never write:** the adaptive-learning cells (0x3FBA8A: 4 upshifts × 9 torque bands, 256 = default) and the per-unit valve-body
  solenoid calibration, both in non-volatile storage. The valve-body data is mirrored in flash at 0x6FA30-0x6FA52, next to the ROM id.
  **In stock the cells are ignored:** the clamp table 0x668AC pins the cell to 256 (min = max = 256) before it scales the apply ramp, so
  shift-time adaptation is effectively off (CONFIRMED in code and live). On this car the light-throttle cells have drifted to 0-237 with no effect.
  So in stock, changing shift firmness through the ramp steps is **not** undone by learning. If you widen the clamp, learning will pull
  shift times toward the targets in 0x6890C, so set those to match.

## Files

- `tcm_RE5R05A_20261119.bin` (+ `.md5`, `.sha256`): the stock image the definition was built from (0x00000-0x6FFFF). It holds no VIN or
  immobilizer data.
- `CG401_tcm_tables.csv`, `CG401_tcm.xdf`, `CG401_tcm_romraider.xml`, `CG401_tcm.md`, `CG401_tcm.json`: the definition (see "Formats").
- `reports/01-09`: how each item was found (06 = live RAM: tick, A/B roles, learned cells, WOT 1→2; 07 = factory-manual cross-checks: pressure unit, solenoid currents, pressure switches; 08 = DTCs; 09 = manual mode).
- `img/`: D-range shift lines with the factory AT-62 shift-speed windows drawn on (`shift_lines.png`; the full-pedal 1→2 bar sits right of the line because the line is the decision point and the factory figure is shift completion, 66 km/h measured on the car), live upshift sequencer trace, phase timers and shift-time targets in ms, task schedule (report 06).
- `tools/cg401_cal_crc.py`: checks or rewrites the calibration CRC (`python3 cg401_cal_crc.py image.bin [--fix]`, keeps a .bak). `tools/gen_tcm_defs.py` + `tools/check_defs.py` regenerate every format from the image and verify no table overlaps or leaves the calibration block (`gen_tcm_defs.py image.bin outdir`, `check_defs.py outdir/CG401_tcm_romraider.xml image.bin`).

## Changes

- **v3.5 (2026-11-20):** + `img/` figures and `tools/` (checksum fixer, generator, checker). + ATF temperature sensor curves 0x60375 / 0x603F7 (TCM 08 §5; report 01 had them as solenoid curves). Full lock-up on/off naming CONFIRMED against FSM AT-63 (90 lock-up items → CONFIRMED). Solenoid names for all six linear slots and the three on/off outputs (LC/B solenoid, starter relay, back-up lamp relay) CONFIRMED from the DTC writers (TCM 03, 08 §4). Every DTC monitor threshold listed (08 §4); P1710 = open-circuit check. 422 items, 0 CANDIDATE.
- **v3.4 (2026-11-20, report 08 §4 added 04:30):** reports 08 (DTC table, P0744, P17xx/P184x logic, in-gear ratio windows, all monitor thresholds) and 09 (manual mode: CAN 0x2DE switches, gear request, slot-4 lines = tap permission); pressure-switch map 3FB20F (07 §3b); slot-4 shift-line notes updated. Same 420 items.
- **v3.3 (2026-11-19 night):** line-pressure unit 0.1 kPa now STRONG from the factory line-pressure test (TCM 07); solenoid ids are currents ≈ 6.25 mA/count; report 07 added.
- **v3.2 (2026-11-19 20:00):** every shift-quality tick = 20 ms CONFIRMED (scheduler table 0x10C00); + torque-cut extra apply ramp table
  0x65628 (stock gain 0, off); 3FB46E/470 described in reports/06 §2. 420 items.
- **v3.1 (2026-11-19 late):** + adaptive cell clamp tables (0x668AC → 0x66882…) and learning deadband 0x6864C: stock clamp min = max = 256,
  so shift-time learning has no effect (TCM 06 §3). 419 items.
- **v3 (2026-11-19 evening):** A/B sequencer roles CONFIRMED live; 10 ms base tick; WOT 1→2 cross-check vs factory; CSV table list;
  report 06; TunerPro XDF. Same 414 items as v2.1.
- v2.1 (2026-11-19 14:00): apply end-target coefficients, downshift start detection, initial-apply columns named by element, mode enables.
- v2 (2026-11-19 12:00): 401 items, every shift and lock-up line, phase timers, apply ramps, shift-time targets.
- v1 (2026-11-19 09:55): 63 items.
