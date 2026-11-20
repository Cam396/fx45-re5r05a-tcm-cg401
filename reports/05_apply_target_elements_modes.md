# TCM 05 · Apply-pressure end target, element indexing, shift modes (desk items from the TCM to-do table)

**Status:** written 2026-11-19 afternoon from the ROM alone (nothing here is VIN- or car-specific). Element indexing is **CONFIRMED**
(three tables agree with the FSM clutch chart). The pressure-target formulas are **STRONG** (code). The pressure unit is still
open, like line pressure (TCM 03): 10000 = "full" at the end of a shift.
Data: `data/ramp_target.txt` (`scripts/tcm_ramp_target.py`), `data/asm_3bfb0.txt` (`scripts/ppcmini.py`, code Ghidra never
disassembled). New tools: `scripts/ppcmini.py` (mini PowerPC disassembler, r13 offsets → RAM), `scripts/sda_access.py` (every
r13 load/store that touches a RAM byte, which catches bitfield writes Ghidra files under another name).

**Naming note:** Ghidra's `(byte)DAT_003fb17c` / `DAT_003fb17c._3_1_` is the **low byte of the word, RAM 3FB17F**. Earlier
reports' "3FB17C bit N" means 3FB17F bit N. 3FB17B is a separate byte (below).

## 1. Engaging / releasing element per shift [CONFIRMED]

Element codes: **0 = D/C, 1 = HLR/C, 2 = I/C, 3 = FR/B**, 4 / FF = none. FSM clutch chart (AT-17): 1st HLR/C+FR/B, 2nd D/C+FR/B,
3rd HLR/C+D/C+FR/B, 4th I/C+HLR/C+D/C, 5th I/C+HLR/C+FR/B.

| shift | 0x4B2E8 engaging (→ 3FB7F8 byte 0) | 0x4B406 released #1 | 0x4B414 released #2 | chart check |
|---|---|---|---|---|
| 1→2 | 0 D/C | — | — | applies D/C ✓ |
| 2→3 | 1 HLR/C | — | — | applies HLR/C ✓ |
| 3→4 | 2 I/C | — | — | applies I/C ✓ |
| 4→5 | 3 FR/B | — | — | applies FR/B ✓ |
| 2→1 | 1 HLR/C | 0 D/C | — | ✓ |
| 3→1 | FF | 0 D/C | — | release only ✓ |
| 3→2 | 3 FR/B | 1 HLR/C | — | releases HLR/C ✓ (FR/B held) |
| 4→1 | FF | 0 D/C | 2 I/C | ✓ |
| 4→2 | 3 FR/B | 1 HLR/C | 2 I/C | ✓ |
| 4→3 | 3 FR/B | 2 I/C | — | ✓ |
| 5→1 | FF | 2 I/C | — | ✓ |
| 5→2 | 0 D/C | 1 HLR/C | 2 I/C | ✓ |
| 5→3 | 0 D/C | 2 I/C | — | ✓ |
| 5→4 | 0 D/C | 3 FR/B | — | ✓ |

The initial-apply table **0x62854 [14 shifts × 4 elements, u16]** only has values in the engaging element's column:
1→2 D/C 5670, 2→3 HLR/C 3420, 3→4 I/C 6370, 2→1 HLR/C 1070, 4→2 and 4→3 FR/B 610, all others 0. So the column is the element.
(For the definition: rename the columns D/C, HLR/C, I/C, FR/B.)

3FB7F8 byte 1 = a phase-count limit for 1→2/2→3/3→4 only (0x6083E = 25 / 20 / 30); byte 2 = its counter (FUN_3C1F0).

## 2. Apply-pressure end target 3FB504 / 3FB508 [STRONG]

**Upshifts** (FUN_261A8, run every tick of the shift):

```
coefficients 0x65648 + shift×10 = {a, b, c, d, floor} (a-d /1024)
gain  3FB4C4 = PTR 0x6574C[shift] → rows {ATF temp key (3FB802 = ATF 3FB794), ptr} → {turbine torque s16, gain u16 /1024}
hold  3FB48E = max(K × T_turbine / 1024, P0 + term 0x2F244)         K: PTR 0x62610[shift], P0: PTR 0x667AC[shift], rows by speed 3FB797
      3FB412 = 3FB48E at phase start, then ramps to 0 over (3FB50C − 3FB49E + 1) ticks (FUN_427E0 / 42818)
3FB46E = a·|T_turbine|/1024 · gain/1024 + b·3FB412/1024
3FB470 = P_captured − (c·|T| + d·3FB412)/1024, captured once per phase (3FB1AF b4) from 3FB502 while sequencer A = 0x30
target 3FB504 = max(3FB46E + 3FB470, floor);  pedal released (3FB17F b2) → floor only
```

3FB470 makes the target start from the pressure the clutch already has. a sets how steeply the target rises with torque.

| upshift | a | gain (stock, flat over ATF and torque) | a × gain | floor | c |
|---|---|---|---|---|---|
| 1→2 | 1.297 | 1.0 | **1.30 × T** | 2100 | 0.830 |
| 2→3 | 0.792 | 1.5 | **1.19 × T** | 1354 | 0.526 |
| 3→4 | 1.472 | 1.5 | **2.21 × T** | 2283 | 1.000 |
| 4→5 | 0.199 | 1.5 | **0.30 × T** | 500 | 0.166 |

b = d = 0 in every shift, so the 3FB412 hold term is unused by the upshift target in stock. The ATF/torque gain grid exists
(cold < 45 raw / warm rows, torque steps 660/1600 or 1500/8000) but is flat.

**Downshifts** (FUN_2624C): 0x65670 + (shift−4)×6 = {a, b, floor}; 3FB508 = max(a·|T| + b·3FB430, floor) (pedal released → floor).
3FB430 = 0x64E40[(shift−4)×4] or the initial-apply cell of the released element (FUN_27DEC). Stock b = 0 everywhere. a/floor:
2→1 0.972/2070 · 4→2 0.170/820 · 4→3 0.229/570 · 5→2 1.244/2100 · 5→3 1.479/2750 · 5→4 0.350/1020 · 3→1, 3→2, 4→1, 5→1 = 0/0.

Speed-keyed hold gains K (0x62610) and floors P0 (0x667AC) for all 14 shifts are in `data/ramp_target.txt`.

**For a tune:** shift firmness lives in `a` (upshifts 0x65648, downshifts 0x65670), the floors, and the initial-apply table
0x62854. The learned shift-time cells (3FBA8A, TCM 03 §8) keep scaling the ramp after any change.

## 3. Phase-timer bank selection

| flag | meaning | evidence | banks |
|---|---|---|---|
| **3FB187 b2** | **continuous (same-direction) shift**: a new request in the same direction as the shift in progress (0x4BA14 [from×5+to]: 1 = down, 2 = up) | FUN_3B7C8; enable cal 0x6077D b0 = 1 (or b1 with pattern 4/7); cleared on reversal or changed target | alt 0x60CEE / 0x614CE [STRONG] |
| **3FB17B b0** | **lift-foot upshift**: armed for 1→2/2→3/3→4 above speed 0x657FC[shift] with ATF ≥ cal 0x606E9 and range enable 0x4B235[range×4+shift]; set if the pedal N samples ago (N = 0x606E7) was ≥ 0x606EA and now ≤ 0x606EB, within 0x606E8 cycles | 0x3BFB0-0x3C1A0 (not a Ghidra function) | 0x618BE / 0x619BE [STRONG]. **Disabled in stock: 0x606E9 = 255, 0x606E7/E8/EA/EB = 0** |
| 3FB2BF b1 | fallback set: cal 0x6036C b0 (= 1), no shift in progress, speed < 0x6036D (5 km/h), and 3FB2BF b0 = debounced CAN 0x2A5 byte 3 bits 0-1 = 11 | FUN_3E5CC, FUN_3EB20, mailbox 14 = 0x2A5 | 0x492BC / 0x496AC. **20:05 (TCM 06 §5):** FUN_20BC4 latches 3FB76B = 1 once mailbox 14 (0x2A5) byte 3 has bits 0-1 = 11 (never cleared until reset); FUN_3EB20 debounces it into 3FB2BF b0. No other byte of 0x2A5 is read. On this car 0x2A5 = `00 00 00 80 00 00 00 00` at 62 Hz, static, so the fallback set never runs [CONFIRMED]; sender still unknown (not found in the ECM ROM) |

## 4. Downshift start detection 0x65784 / 0x657AC / 0x657D4 [STRONG]

10 downshifts × {u16 ratio threshold, u16 tick limit}. A flag sets when the measured ratio 3FB2FC (turbine/output ×1024) passes the
threshold **or** the shift timer 3FB4A0 reaches the limit. Thresholds are the from-gear ratio ×1024 plus 1-2 %:
2339 (2nd 2318), 1528 (3rd 1506), 1044 (4th 1024), 874 (5th 854). So the flag means "the ratio has left the old gear" (inertia
phase started), and the tick limit is the fallback. With 3FB7E2 < 3FB7DF, 0x65784 drives 3FB17F b6 and 0x657AC drives 3FB187 b5.
Otherwise 0x657D4 drives 3FB187 b5. Tick limits: 50 for most; 7-8 for 3→2, 5→4 and some 4→3/5→3 cases; 25 for 4→3/5→3/5→4.

## 5. Still open (desk)

- Manual-mode request logic (pattern 4/7: up/down request handling, auto-upshift at the limiter, downshift protection).
- DTC thresholds (P07xx ratio/solenoid/pressure-switch judgments).
- 0x2A5 sender/meaning (fallback bank flag).
- Pressure unit (needs the car, together with line pressure).
