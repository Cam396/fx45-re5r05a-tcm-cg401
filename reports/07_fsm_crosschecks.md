# TCM 07: factory service manual cross-checks (2026-11-19 night)

Source: 2004.0 FX35/FX45 FSM, AT section (`fx45_online/fsm/at_2004.0.txt`). Each item says what the FSM states, what the ROM / logs
show, and the verdict.

## 1. Line-pressure unit: 0.1 kPa [STRONG]

FSM AT-53: D/M idle 373-422 kPa, D/M stall 1,310-1,500; R idle 392-441, R stall 1,700-1,890. Stall speed (VK45DE) 2,300-2,600 rpm (AT-350).
The ROM's maximum clamp 0x67EAE = 13720 is where the 1st-gear steady curve saturates at stall torque → **1,372 kPa at 0.1 kPa/count, inside
the FSM stall window**. The minimum 4900 (490 kPa) is ~70-120 kPa above the FSM idle spec: either absolute pressure (≈ 389 kPa gauge) or
the regulator not following that low. R's higher stall pressure is a hydraulic boost, not in the TCM tables. Details: TCM 06 §4b.

## 2. Solenoid ids 1110-111B are currents, ≈ 1/160 A per count [STRONG]

FSM AT-91 reference values: shift solenoids 0-0.05 A (off) / 0.6-0.8 A (on); line pressure 0.2-0.6 A while driving; TCC 0.2-0.4 A slip
lock-up, 0.4-0.6 A full lock-up. CONSULT lists each as "<name> (A)" plus a "<name> MON (A)" monitor value (AT-98).
Median TRANS-log values by gear (07:49 + 16:30 drives, 2026-11-19):

| state | 1110 TCC | 1111 L/P | 1112 I/C | 1113 FR/B | 1114 D/C | 1115 HLR/C | 1117 L/P (subst.) |
|---|---|---|---|---|---|---|---|
| stopped | 2 | 97 | 123 | 124 | 122 | 2 | 97 |
| 1st | 2 | 67 | 125 | 126 | 122 | 2 | 71 |
| 2nd | 2 | 90 | 123 | 124 | 93 | 116 | 96 |
| 3rd | 1 | 95 | 121 | 122 | 2 | 2 | 96 |
| 4th | 2 | 88 | 2 | 51 | 2 | 2 | 86 |
| 5th | 2 | 80 | 1 | 121 | 119 | 2 | 75 |

At 1/160 A: energised shift solenoids 120-126 → **0.75-0.79 A** (FSM 0.6-0.8), off 1-2 → 0.01 A (FSM 0-0.05), line pressure 67-97 →
**0.42-0.61 A** (FSM 0.2-0.6). A plain 0.01 A scale would put line pressure at 0.97 A and the shift solenoids at 1.2 A, both outside spec.
So the earlier "measured duty %" reading of these ids (TCM 03 §1) is replaced by **current, ≈ 6.25 mA/count** (exact factor CANDIDATE).
The pattern also agrees with the solenoid types: I/C, D/C, HLR/C are normally-high (current = element released): I/C released in 1st-3rd,
applied in 4th-5th; HLR/C released only in 2nd. Line-pressure current is lowest in 1st (most pressure) and highest stopped.
TCC (1110) stayed at 1-2 in these logs, so no lock-up event with TCC current was captured; the TCC check (0.2-0.6 A when locking) is open.

## 3. ATF pressure switches (inputs) [FSM fact, RAM location CANDIDATE]

CONSULT shows ATF PRES SW 1 (FR/B), 2 (LC/B), 3 (I/C), 5 (D/C), 6 (HLR/C), ON when that element is applied (AT-91). The "solenoid function"
DTCs use them: e.g. P1754 I/C FNCTN = gear ratio irregular AND pressure switch 3 disagrees with the gear while the pedal is pressed (not during
a shift), or switch 3 disagrees with the gear with the pedal released (AT-152). The TCM's raw digital input bytes 3FB769-3FB76B (polarity
XOR 0x4B274-0x4B276, debounced in FUN_3EB20) are the likely home of these switches together with the PNP/manual-mode switches; mapping
each bit needs a live read in P/R/N/D (read-only, easy with the PROBE page).

### 3b. Switch map from the DTC monitors (2026-11-20) [STRONG code, CONFIRMED in P live]

FUN_2CF00 (the element-function monitor driver) passes one bit of **3FB20F** with each element's solenoid command to FUN_2CBF8 /
FUN_2CD9C, and the resulting DTC mask names the switch (TCM 08 §3):

| 3FB20F bit | switch (FSM) | element | command word (u16, 0-10240) | DTC on mismatch with ratio OK |
|---|---|---|---|---|
| b1 | SW1 | FR/B | 3FB6EA (inverted test, FUN_2CD9C) | P1841 |
| b3 | SW2 | LC/B | on/off command 3FB2C4 b0 (FUN_2B79C) | P1731 (no P1842 on this car) |
| b4 | SW3 | I/C | 3FB6E8 | P1843 |
| b6 | SW5 | D/C | 3FB6EC | P1845 |
| b7 | SW6 | HLR/C | 3FB6EE | P1846 |

"Applied" = command ≤ 0x4B076 = 641 for I/C, D/C, HLR/C (normally-applied type: high current releases, FSM AT-91 I/C 0.6-0.8 A =
disengaged) and command ≥ 0x4B07C = 9615 for FR/B (normally-released type). **Live (both 11-19 SRAM dumps, P, idle):** 3FB20F = 0x82 =
SW1 FR/B + SW6 HLR/C on; commands I/C = FR/B = D/C = 10240, HLR/C = 0. That matches the code's sense for all five, and the FSM's P/N
(both brakes released for drive, FR/B + HLR/C staged). The monitors only run with 3FB9F8 ≥ 9000 (12,835-13,037 in the dumps, so
**battery mV**, STRONG). PROBE page 9 reads the word in every range and gear.

## 4. DTC detection logic (FSM wording) for the decode of P07xx/P17xx

| DTC | FSM detection condition (AT page) | what to look for in the ROM |
|---|---|---|
| P0744 TCC S/V function | lock-up commanded but slip doesn't fall; "comparing reference value with slip rotation" (AT-125) | slip-speed threshold + timer near the TCC logic |
| P0745 line-pressure solenoid | voltage drop on drive, or target vs monitor current mismatch (AT-127) | target vs MON current comparison (ids 1111 vs 1117) |
| P1754/1759/1764/1769/1774 element function | gear ratio irregular + pressure switch disagrees, pedal on/off, not during a shift (AT-152…172) | per-element switch-vs-gear table + ratio window |
| P1752/1757/1762/1767/1772 element circuit | solenoid circuit open/short (current monitor) | MON current vs command |
| P1731 1st engine braking | LC/B (on/off solenoid) function (AT-150) | switch 2 vs LC/B command |
| P1701/P1704 | TCM power supply / TCM (2004.0-only codes; confirms this car is 2004.0) | already in TCM 01 |

## 5. Still open after this pass

TCC current during a real lock-up (needs a steady highway cruise in 5th with the TRANS profile), the exact current factor, the pressure-
switch bit map (live read), and the ROM side of the §4 thresholds.
