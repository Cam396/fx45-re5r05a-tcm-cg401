# TCM 04 · Shift index, shift-phase timers, apply ramps, and the engineering frame

**Status:** shift index CONFIRMED (code table). Phase-timer and ramp structures CONFIRMED in code; roles STRONG; A/B element naming and
the tick period CANDIDATE. Written 2026-11-19 for defs v2.

## 1. Shift index 3FB7E4 [CONFIRMED]

FUN_3BB1C sets direction 3FB7E3 (1 = up, 2 = down, 0 = none) from actual gear 3FB7F3 vs target 3FB7DF (0-based), and
**3FB7E4 = ROM 0x4B1E0[from × 5 + to]**:

| from \ to | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | – | **0** | ✗ | ✗ | ✗ |
| 2 | 4 | – | **1** | ✗ | ✗ |
| 3 | 5 | 6 | – | **2** | ✗ |
| 4 | 7 | 8 | 9 | – | **3** |
| 5 | 10 | 11 | 12 | 13 | – |

So **0-3 = 1→2, 2→3, 3→4, 4→5**; 4 = 2→1, 5 = 3→1, 6 = 3→2, 7 = 4→1, 8 = 4→2, 9 = 4→3, 10 = 5→1, 11 = 5→2, 12 = 5→3, 13 = 5→4.
No skip upshifts exist (✗ = 0xF0). This closes the "[CANDIDATE mapping]" on every per-shift table in TCM 01/03 (torque cut 0x69AC8,
shift line pressure 0x68404, learning).

## 2. Shift-phase sequencers A and B [structure CONFIRMED, roles STRONG]

Each shift runs two four-phase state machines: **A = 3FB7DA (FUN_3FCA4)** and **B = 3FB7D9 (FUN_401A8)**. Both step
0x10 → 0x20 → 0x30 → 0x40 → 0xFF (done), with a per-machine tick counter (3FB49C / 3FB49E). Phase k of shift s reads row
**s × 4 + k** of a bank of 9 × u16 rows:

| bank | used for | address |
|---|---|---|
| A normal / alternate (3FB187 b2) | sequencer A | **0x608FE** / **0x60CEE** |
| B normal / alternate | sequencer B | **0x610DE** / **0x614CE** |
| fallback (3FB2BF b1) | both | 0x492BC / 0x496AC (in the application block, not calibration) |
| no-progress mode (3FB17B b0) | A / B, columns 1-8 only | 0x618BE / 0x619BE |

- **Column 0 = shift-progress threshold.** The phase ends early when speed-ratio progress 3FB2FC passes it (upshift: above, downshift:
  below). These match the separate shift-completion table 0x65784 (2339 / 1528 / 1044 / 874 …), which is an independent check.
- **Columns 1-8 = phase duration in ticks**, chosen by turbine torque 3FB4FA (= engine torque × converter ratio) against the band edges
  **0x608EE = 100, 200, 300, 510, 1010, 2000, 2500, open**.
- Phase 1 duration + learned offset 3FB3D2. Phase 2 of an upshift + 3FB54A, floored at 0x6883E[shift] (stock 0 = no floor).

Stock example, bank A 1→2: phase 1 = 27 ticks; phase 2 = 30-55 until progress 3574; phase 3 = 32-100 until 2339; phase 4 = 40.
Downshift rows with column 0 = 65535 and 1 tick are effectively "skip this phase".

**What A/B are:** when A finishes it sets 3FB502 and 3FB506 to 0x6070E = 10000 (both elements to the "full" end), and 3FB502 is the
engaging-element pressure (TCM 03 §8). So A most likely sequences the engaging (on-coming) element and B the releasing one [CANDIDATE].
The tick period isn't measured. The shift-time targets (§3) of 15-90 ticks against real shift times suggest about 10 ms [CANDIDATE].

## 3. Apply-pressure ramp [STRONG]

```
start   3FB502 = 0x62854[shift*4 + 3FB7F8]        (FUN_41B50; 3FB7F8 = element column, 0xFF = keep)   1→2: 5670, 2→3: 3420, 3→4: 6370, 2→1: 1070, 4→2/4→3: 610 (×0.1 kPa CANDIDATE)
target  3FB504 = 3FB46E + 3FB470, floor 3FB522     (FUN_261A8)
steps   3FB3E2 = ramp table 0x629D4[shift] (alt 0x62A38): rows by turbine torque, sub-rows by speed 3FB797   (FUN_41B88)
slope   3FB3E0 = (target − start) / steps         (FUN_41C28); learning scales it (TCM 03 §8); 3FB502 += 3FB3D4 + 3FB3DE per tick
```

Ramp steps (upshifts only; fewer = firmer):

| shift | turbine torque ≤ → steps |
|---|---|
| 1→2 | 0: 125/94/62 by speed (≤25, ≤35, above) · 450: 250 · 650: 125 · 800: 105 · 1000: 90 · 1250: 80 · 1500: 70 · 2000: 62 · 2500: 57 · 3000: 65 · max: 65 (≤60 km/h) / 42 |
| 2→3 | 500: 140 · 650: 113 · 800: 95 · 1000: 86 · 2000: 77 · 3000: 75 · max: 75 (≤99 km/h) / 50 |
| 3→4 | 200: 91 · 510: 92 · 1000: 77 · 1300: 72 · 3000: 70 · max: 70 (≤162 km/h) / 47 |
| 4→5 | 500: 50 · max: 47 |

**Shift-time targets 0x6890C** (what learning converges to; {torque ≤, ticks}): 1→2 15 (25 at 1800-2300), 2→3 55-90, 3→4 50-70,
4→5 17-47. Learning compares measured shift time with these and scales the ramp (TCM 03 §8). **For a firmer feel a tuner would
lower the targets and the ramp steps together**, otherwise learning walks the ramp back.

## 4. Constant cells in the schedule tables [CONFIRMED]

The lock-up tables (0x6E99C / 0x6EF14 / 0x6F48C) and the shift pointer table 0x6D4F8 cover every mode × range × gear. Most slots point at
their **own** one-record constant line (y = 0 "never" or 255 "always"). Defs v2 counts these instead of listing them, and lists only the
real curves (168 shift lines, 89 lock-up lines). A slot can be changed in place only to another constant. A real line needs a
new curve and a repointed entry, which RomRaider can't do.

## 5. The engineering frame ("engineering mode") [CONFIRMED trigger, output only]

FUN_21184: lever code 3FB774 must read **0x8C, 0x84, 0x8C, 0x84, 0x8C, 0x84** (states 1-5, then the flag) within **500 ticks** of the
first 0x8C. Then **3FA43A = 1** (until power-off). 0x84 is the reset default, and the line-pressure code treats 0x84/0x8C as the two
not-in-gear positions, so this is a quick **P ↔ N shuffle** [CANDIDATE: which code is P]. Effect: the TCM starts sending **0x25F**
(shift-phase data + TCC pressure) and repurposes **0x25E** (input torque/40, gear state, progress). Both are on the **private
ECM↔TCM CAN**, not the OBD-port bus, so the OBDLink on the OBD port can't see them. It changes no control behaviour that I've found.
0x25E normally goes to the ECM on that bus (whether the ECM uses those bytes is unchecked), so changing its contents is a reason **not** to use it while driving.

The same data is in TCM RAM (0x3F9800-0x3FFFFF): 3FB7DA/7D9 phases, 3FB49C/49E timers, 3FB502/504/506 pressures, 3FB2FC progress.
**Read-only RAM reads over K-line get all of it without touching the private bus.**

## 6. Still open

- ~~Tick period~~ **10 ms (2026-11-19 17:49, live):** the u16 counter 3FA438 rose 201 counts in 2,004 ms (0x0B → 0xD4 low byte, 21 reads at idle in P), so 9.97 ms per count. **Correction (19:58, TCM 06 §1):** the phase timers, ramp steps, shift times 3FB67A and the 0x608xx timer tables run in the **20 ms** task T44 (schedule table 0x10C00, CONFIRMED); only the base counter 3FA438 and the engineering-mode window are 10 ms.
- A = engaging / B = releasing (a RAM log of 3FB502/506 across one shift settles it).
- 3FB46E / 3FB470 (target pressure terms) and 3FB522 (floor) sources.
- Meaning of 3FB187 b2 (alternate banks + torque-cut set), 3FB17B b0 (no-progress mode), 3FB2BF b1 (fallback banks).
- WOT 1→2 at 54 vs factory 64-68 km/h (TCM 02 §6b). The factory figure is the speed when the shift *happens*. At WOT in 1st the
  car gains ~15 km/h per second, and the phase timers above add up to roughly 0.6-1 s from decision to completion. So 54 km/h
  decision → 64-68 km/h at completion is plausible [CANDIDATE explanation; a D-range WOT log settles it].

## Files

`scripts/gen_tcm_defs.py` (v2), `scripts/tcm_v2_probe.py`, `scripts/check_defs.py` (XML bounds/overlap check), `data/dec_all.c`
FUN_3BB1C / 3FC4C / 3FCA4 / 40150 / 401A8 / 41B50 / 41B88 / 41C28 / 261A8 / 21184.
