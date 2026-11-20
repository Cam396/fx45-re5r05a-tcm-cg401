# TCM 03 · Solenoid outputs, line pressure, ECM↔TCM CAN, torque reduction

**ROM:** tcm_RE5R05A_20261119.bin (md5 987776c9c8e483312ad23c55c69e41e6), MPC555. Decompile: `data/dec_all.c`.
**Status:** output chain CONFIRMED (code). Torque-reduction request CONFIRMED against CAN drive data (exact table hits).
Solenoid duties by gear CONFIRMED against the 2026-11-16 TRANS log. Solenoid names CONFIRMED (2026-11-20): each slot's circuit monitor sets the FSM-named DTC for that solenoid (TCM 08 §4: slot 0 → P0740 TCC, 1 → P0745 line pressure, 2 → P1752 I/C, 3 → P1757 FR/B, 4 → P1762 D/C, 5 → P1767 HLR/C).

## 1. Output hardware (MPC555 MIOS1) [CONFIRMED]

Function 0x18xxx (dec line ~14460) writes six PWM channels every pass. Duty = drive × 10000 / 12852 (0.01 % units), with 12852 (0x3214) = 100 %.

| slot | setter | drive RAM | PWM channel (PULR) | measured duty (TPU feedback) | K-line id (measured, raw/2 = %) | role |
|---|---|---|---|---|---|---|
| 0 | 0x20354 | 3FA0A4 ← 3FB6E4 | MPWMSM16 (0x306082) | 3FA0A8 (TPU A ch4) | 1110 / 1116 | **torque-converter clutch (TCC)** [STRONG] |
| 1 | 0x2036C | 3FA0AA ← 3FB6E6 | MPWMSM3 (0x30601A) | 3FA0AE (ch3) | 1111 / 1117 | **line pressure** [STRONG] |
| 2 | 0x20384 | 3FA0B0 ← 3FB6E8 | MPWMSM0 (0x306002) | 3FA0B4 (ch0) | 1112 / 1118 | **I/C** input clutch (§4.1) |
| 3 | 0x2039C | 3FA0B6 ← 3FB6EA | MPWMSM1 (0x30600A) | 3FA0BA (ch1) | 1113 / 1119 | **FR/B** front brake |
| 4 | 0x203B4 | 3FA0BC ← 3FB6EC | MPWMSM2 (0x306012) | 3FA0C0 | 1114 / 111A | **D/C** direct clutch |
| 5 | 0x203CC | 3FA0C2 ← 3FB6EE | MPWMSM17 (0x30608A) | 3FA0C6 | 1115 / 111B | **HLR/C** high & low reverse clutch |
| on/off | 0x2033C / 0x2034C / 0x20344 | 3FB1DC bits 0 / 1 / 2 | MDASM SCR bit 3 (0x306066, 0x306076, …) | readback 3FB2C4 bits 0-2 | — | **b0 LC/B solenoid** (P1772), **b1 starter relay** (P/N, P0615), **b2 back-up lamp relay** (R) [CONFIRMED: FSM TCM pins 7 / 9, fail-safe text] |

- Ids **1110-1115** = measured duty (TPU-measured high time / period). **1116-111B** = the same with fault substitution:
  0x783 on a driver "short" flag, 0 on "open" (0x22304). Report 01's guess of "commanded and measured currents" is corrected: both are measured duty.
- The K-line value is duty >> 6 (full scale 200), so **% = raw / 2**.
- **Open/short diagnostic** 0x28656: compares commanded duty 3FB6E4+ with measured 3FB92E+ against windows 0x4B150-0x4B156.

## 2. Pressure → duty chain [CONFIRMED structure]

```
per-element pressure 3FB6C0..6CA
  → × gain/256 + offset×100        (FUN_37F14, per-solenoid {class, gain, offset} at 3FBA02 + 6k)   → 3FB708..712 / 3FB714..71E
  → zero / "full" sentinels         (0x6BE5C = 0, 0x6BE60 = 25500 → drive 0x140, or 0x168 when ATF < 55)
  → I-P characteristic curve        (FUN_3855C, curve set 0x6C834[class])                            → 3FB720..72A
  → override switch                 (FUN_26AE4: if 3FB88B b7+b4, use 3FB878+k from CAN 0x25B = active test)
  → first-order filter              (FUN_26B34, rate 0x6BE66, per-shift rates 0x6CA10)              → 3FB738..742
  → fail-safe output modes          (0x24BD0, 3FA435)                                               → 3FB6E4..6EE → PWM
```

- **3FBA02 + 6k {class byte, gain, offset}** has no static writer (copied as a block). It's the **valve-body solenoid calibration**,
  the per-unit data a TCM gets when its valve body is replaced [STRONG]. It isn't adaptive learning.
- **Fail-safe output modes** (3FA435, requested by 3FB238 bits 0/1/2 or 3FBAF8 + 3FB846): mode 4 = every solenoid off; mode 2 = slots 2 + 5 at 0x2810 (≈ 80 %);
  mode 5 = slots 3 + 4 at 0x2810. These are the mechanical limp-home gears. 3FB238 bits 4/5 kill slots 1/0, and the 3FB293 bits 0+1 "forced" state kills slots 0 + 1.
- Pressure units: the active-test byte is ×100, the sentinel is 25500, and line pressure clamps at 4900-13720. **0.1 kPa per count** fits
  (490-1,372 kPa line pressure, 2,550 kPa "full") [CANDIDATE unit].

## 3. Line pressure (slot 1) [CONFIRMED structure]

**Priority selector 0x37DB8** (first match wins; the winner's code goes to 3FB1E8, a useful live id candidate):

| condition | source | code 3FB1E8 |
|---|---|---|
| 3FB1E4 bit 7 | 0x67EA2 = **4900** (minimum) | 1 |
| 3FB1E3 bit 0 | 0x67EA4 = **13720** (maximum, failsafe) | 2 |
| 3FB1E3 bit 2 | 3FB942 (shift-related) | 8 |
| 3FB1E3 bit 3 | 3FB93C | 0x10 |
| 3FB1E2 bit 0 | 3FB9EA (tables 0x68510/0x68538) | 0x200 |
| 3FB1E3 bit 4 | 3FB944 | 0x20 |
| 3FB1E3 bit 5 | 3FB946 | 0x40 |
| 3FB1E3 bit 7 | lever floor 0x68452 = 12600 / 10810 / 7800 (lever 0x83/0x82/0x81: the manual/limit ranges) | 0x100 |
| otherwise | **base line pressure 3FB960** | 0 |

**Base line pressure 0x36E24:**
```
input  T_in = 3FB324  (id 1127)
steady: curve 0x684EC[slot](T_in)   slot = 7 failsafe / 0 lever 0x8C / 1 lever 0x84 / target gear + 2
shift:  curve 0x68404[shift index 3FB7E4](T_in)
× 3FBAE2/256 (post-event factor, steps ×307/256 every 100 ticks once shift progress passes 0x67ECA[gear])
clamp to [0x67EAC = 4900, 0x67EAE = 13720]
```
Steady curves (x = T_in, y in 0.1 kPa): 1st/2nd **0 → 3700, 500 → 4400, 1000 → 5100, 1500 → 5800, 2000 → 6510**; 3rd-5th, P, N and failsafe
**0 → 4420, 500 → 5040, 1000 → 6030, 1500 → 7710, 2000 → 8470**. The 4900 floor dominates at idle.

**Input torque T_in, 0x2A390:**
```
T_turbine 3FB4FA = engine torque 3FB310 × converter torque ratio 3FB312 / 1024      (0x2A2C4; ratio = curve 0x60474 of speed ratio 3FB2D2)
peak-hold filter 3FB364 (rate 0x60348), throttle floor 3FB36A = curve 0x604F2(throttle_b)
× ATF-temperature factor curve 0x60534(ATF) × (0x100, or 0x6036A in some states) >> 16
```
So line pressure follows **engine torque from the ECM times converter multiplication**, with a throttle-based floor and an ATF-temperature trim.

## 4. Clutch/brake element states and the gear chart

Each shift element has a state byte: slot 2 ← 3FB7E8, slot 3 ← 3FB7EE, slot 4 ← 3FB7E6, slot 5 ← 3FB7EB. At steady state they come from
target-gear tables, and during a shift from per-shift tables (0x6081A / 0x607F0 / 0x6080C / 0x607FE). Code 2 = solenoid ON and 1 = OFF; the 2026-11-16 log matches this:

| target gear | slot 2 | slot 3 | slot 4 | slot 5 | ROM steady codes (2 / 4 / 5) |
|---|---|---|---|---|---|
| P / R | ON 69 % | ON 70 % | ON 70 % | off | |
| 1st | ON | ON | ON | off | dyn / 2 / dyn |
| 2nd | ON | ON | **off** | **ON 66 %** | 2 / 1 / 2 |
| 3rd | ON | ON | off | off | 2 / 1 / 1 |
| 4th | ON ~60 % (n = 4) | ~40 % | off | off | 1 / 1 / 1 |
| 5th | **off** | ON | **ON** | off | 1 / 2 / 1 |

(The measured columns are median duty from ids 1112-1115 on the TRANS log, gear from turbine/output ratio, 4-66 samples per row.)
Slot 3's steady state is mode-dependent (0x3CF2C: speed/pedal hysteresis 0x606F6-0x60706, table 0x60784 by lever × gear).

### 4.1 Slot names [CONFIRMED 2026-11-19]

| slot | PWM | element | solenoid type | "ON" (high duty) means |
|---|---|---|---|---|
| 0 | MPWM16 | TCC (torque converter clutch) | normally low (Sonnax 63421 group) | lock-up apply |
| 1 | MPWM3 | line pressure | normally low (63421 group) | — |
| 2 | MPWM0 | **I/C** input clutch | **normally high** (63425 group, FUN_3855C type 1) | released |
| 3 | MPWM1 | **FR/B** front brake (band) | normally low (63421 group, type 0) | applied |
| 4 | MPWM2 | **D/C** direct clutch | normally high (63425 group, type 1) | released |
| 5 | MPWM17 | **HLR/C** high & low reverse clutch | normally high (63425 group, type 1) | released |
| on/off | 3FB1DC | **LC/B** low coast brake ("ON OFF SOL" in CONSULT) is one of bits 0-2 | on/off | applied (M1/M2 engine braking) |

Three independent checks agree:

1. **Factory clutch chart** (RE5R05A AT section, AT-17, `fx45_online/pdf/chart-017.png`): D-range elements are 1st HLR/C(△)+FR/B(△);
   2nd D/C(+FR/B △); 3rd HLR/C+D/C+FR/B; 4th I/C+HLR/C+D/C; 5th I/C+HLR/C+FR/B. With normally-high slots inverted, the logged
   duty table above reproduces this row for row. Example: slot 5 is "ON" (released) only in 2nd, the only forward gear without HLR/C.
2. **Solenoid part grouping:** Sonnax sells one part (63421) for line pressure, TCC and front brake, and another (63425) for direct,
   input and high-and-low-reverse clutches. That is the same split as the TCM's type flag: slot 3 type 0, slots 2/4/5 type 1.
3. **Fail-safe modes now decode as gears.** All solenoids off (mode 4) leaves I/C+D/C+HLR/C applied, which is **4th**, the
   RE5R05A's known limp gear. Mode 5 (slots 3+4 driven) applies FR/B and releases D/C, giving I/C+HLR/C+FR/B = **5th**. Mode 2 (slots 2+5 driven) releases
   I/C and HLR/C, leaving D/C = **2nd**. **The mode number is the gear.**

The CONSULT reference table (AT-75) shows 0.6-0.8 A on every shift solenoid when its element "operates". That is a display
simplification in the manual; the normally-high grouping above is what the hardware and the code use.
Pressure switches (for later): SW1 = FR/B, SW2 = LC/B, SW3 = I/C, SW5 = D/C, SW6 = HLR/C (DTCs P1841-P1846).

## 5. ECM ↔ TCM CAN [CONFIRMED]

Receive descriptors at 0x111FC (20 bytes: status*, CAN id, len, data*, flag*), transmit at 0x11350. FUN_20858(n) reads RX n; FUN_208F4(n) queues TX n.

| dir | id | TCM use | on OBD-port bus? |
|---|---|---|---|
| RX 8 | **0x23D** | b2 pedal → 3FB7A4; b3-4 LE × 25/8 → **engine rpm 3FB2E2** (matches the Nov-10 fit "×~3.1"); b5-6 → **delivered torque 3FB30A** | yes |
| RX 9 | **0x23E** | b3-4 signed LE → **engine (base) torque 3FB308**; b6 → **throttle_b 3FB884**; b0/b1/b2/b7 → 3FB886/887/896/899 | yes |
| RX 13 | 0x2D1 | b1-2 → 3FB764 (vehicle speed ×0.1, matches the CAN decode) | yes |
| RX 7 | **0x25B** | b0-5 → 3FB878-87D = **per-solenoid override** (active test), b6/b7 → 3FB982/983 (mode → 3FB88B) | no (private) |
| RX 6/12 | 0x25A / 0x25C | 3FA3AE-3B2 / 3FB9FA-9FF | no |
| RX 5/10/11/14/15/16 | 0x611 / 0x2DE / 0x29E / 0x2A5 / 0x1F9 / 0x60D | single bytes (brake, etc.) | mostly yes |
| TX 0 | **0x251** | b0 actual gear + shifting bit (3FB88C); b1 target gear + flags; b2 manual-mode gear display; **b3 lever** (P/R/N/D); b4 fault bits; b5 shift index; b6-7 ID string "RX0612" cycled | yes |
| TX 1 | **0x253** | b0 gear<<3 + 2-bit counter; b2 3FB9E4; **b3 torque-reduction request 3FB872**; b4-5 3FB2E0; b6-7 3FB2F2 | yes |
| TX 2/3 | 0x25D / 0x25E | slot 0-3 duties >> 6 / slot 4-5 duties + 6 bytes | no (private) |
| TX 4 | 0x25F | shift-phase data + TCC pressure, **only when 3FA43A = 1** | no |

**3FA43A** is set by a lever sequence: 3FB774 has to go 0x8C → 0x84 → 0x8C → 0x84 → 0x8C within 500 ticks (0x21184). It switches on an engineering frame
(0x25F) and repurposes 0x25E (input torque/40, gear state, shift progress). It's output-only, and I'm noting it here, not using it.

Torque units: 0x23E b3-4 reads +150-700 at idle, +3,379 at WOT 4,366 rpm and −120 to −770 on overrun. ~0.125 N·m/bit would put WOT at ~420 N·m (VK45DE rated 453) [CANDIDATE scale].

## 6. Torque reduction during shifts [CONFIRMED on drive data]

**0x29xxx (dec ~27350) → 3FB872 → CAN 0x253 byte 3.** Requested cut = value/256 of engine torque.

```
enabled per shift by 0x68E8E[shift] (alt 0x68E9C when 3FB187 b2), and 3FB1C3 b0, not 3FB207 b0
only inside the shift-progress window 3FB2FC (inertia phase), limits from 0x68B74/0x68CE0[shift] vs throttle & speed
value = table[shift] (0x69AC8 normal / 0x6A2BC alt): rows keyed by engine torque 3FB310 (18-byte rows: key + 16 bytes),
        columns by engine rpm 3FB2E2 (breakpoints 0x6906C[shift]: 800, 1200 … 6400 rpm)
```

**Live check (drive 2026-11-10, can_20261110_222300):**

| t (s) | shift (0x251 b0) | rpm | base torque | table value | 0x253 b3 seen | delivered torque (0x23D b5-6) |
|---|---|---|---|---|---|---|
| 129.9 | from 1st | 2,362 | 1,317 | shift 0, row 1500, col 2400 → **128** | 128 | 1,317 → **661 (0.50)** |
| 131.6 | from 2nd | 2,028 → 1,962 | 1,324 | shift 1 → **128**, then col 2000 → **102** | 128 → 102 | 1,329 → 680 |
| 157.2 | from 1st | 3,244 | 2,239 | row 2500, col 3600 → **179** | 179 | 2,241 → 1,148 and falling |

Across drive 1 + svc1: req 40 → delivered/base 0.85, 51 → 0.83, 128 → 0.55, 154 → 0.54. The ECM implements the cut and seems to stop near
50 % [CANDIDATE: ECM-side limit]. Shift 0 cuts are 20-70 % (bigger at high rpm), shift 3 (4→5) only 0-30 %. Shifts 0-3 look like the four
upshifts; 4-13 have 70 % cuts at ≤ 1000 torque and 15-30 % above, which looks like the downshift/skip set [CANDIDATE mapping].

## 7. Corrections to TCM 02

- **3FB164 bit 3 = manual mode active** (it drives the 0x251 b2 manual-gear display, 0x25068). So patterns **4/7 (3FB7B6) are the
  manual-mode patterns**, not snow/failsafe. That's why their 1→2…3→4 lines are "always up": manual mode uses its own target logic.
- The 2026-11-16 log shows **TCC duty 1 % in 1st at high pedal**. Lock-up was **not applied in 1st**, which matches the schedule (no lock-up in 1st-3rd).
  The one TCC-on sample (31 %, slip 24 %) is 4th at 46 km/h with light pedal: the partial lock-up line (≥ 44 km/h). For the bucking diagnosis this
  rules out the TCC theory for that log, and the driveline remains the lead.

## 8. Non-volatile data and adaptive shift learning [STRONG] (added 10:10)

**NV block store** (init 0x4491C → FUN_21AAC restore / FUN_21BD8 save; descriptor tables 0x46C08 restore and 0x45B50 save, entries {RAM*, source*, type, len}):

| group | RAM | stored from / default | meaning |
|---|---|---|---|
| 1-6 | 3FBA02-3FBA24 | **flash 0x6FA30-0x6FA52**, next to the ID "CG401" at 0x6FA61 | per-solenoid valve-body calibration {class, gain, offset} (§2), confirmed by location |
| 0 | 3FB986-990 | default 0x4552C | 6 words (pressure-sensor/switch related, used in 0x2A2C4 area) [CANDIDATE] |
| 9 | 3FA1E8+ ← 3FBA38/3C/40, 3FBAF8/FC, 3FBA44 … | | fault/state flags (speed-sensor fault 3FBA38 etc.) |
| **10** | **3FBA8A × 36**, 3FBAD2 × 4, **3FBADA × 4**, **3FBAE2**, 3FBAE6, 3FBAE8 … | defaults 0x4552E/0x4552C | **learned values** |

**Shift-time learning (0x2F3E8 / 0x2F4AC / 0x2F540 / 0x41CCC):**
```
cells   3FBA8A[shift 0..3][torque band 0..8]   (4 upshifts × 9 bands; band edges 0x68670 = 0,1000,…,8000 input torque)
measure 3FB67A = shift time (ticks), 3FB628/3FB49A = average input torque over the shift
target  3FB867 = table 0x6890C[shift](input torque)        1→2: 15 (25 at ~1800), 2→3: 55-90, 3→4: 50-70, 4→5: 47 ticks
law     if |measured − target| > deadband (0x6864C = 1):
            new = old × measured / (target ± deadband)      (×/256, 0 = 256 = 1.0)
        written to the band of the shift's average torque
use     3FB694 = cell for the current torque band;  3FB3D4 = 3FB3E0 × clamp(3FB694, 3FB57C, 3FB57A) / 256
```
A shift that takes longer than its target raises the factor, and a quicker one lowers it. The factor scales 3FB3E0, a per-shift control
quantity, within per-shift limits. **3FB3E0 = (target 3FB504 − start 3FB3DA) / steps 3FB3E2 is the per-tick apply-pressure ramp**, and the engaging-element pressure goes 3FB502 += 3FB3D4 + 3FB3DE each tick (0x42xxx), so **learning scales the clutch apply ramp rate**: slow shift → steeper ramp next time [STRONG]. Only the four upshifts learn. The NV shadow lives at 3FA1F4 (36 words) and following.
A "learning reset" would set these cells back to their defaults. **Don't write them.** They're documented so a log can read them, not so anything changes them.

Also found: **3FF828-3FF918** is a 7 × 40-byte **exception log** (SRR0, SRR1, DSISR, ECR, LR, …) filled by the exception handler (0x13877), not learning.

## 9. Still open (T7)

- ~~Clutch names for slots 2-5~~ done (§4.1).
- ~~On/off outputs 3FB1DC bits 0-2~~ done (2026-11-20): b0 LC/B solenoid (FUN_357B8), b1 starter relay (FUN_3DBCC: range table 0x4B299 flag 0x80, off with a P0705 or P0615 latch), b2 back-up lamp relay (FUN_39A7C: range pattern 9 = R, off with a P0705 latch), matching the FSM fail-safe text (AT "PNP switch": starter and back-up lamp relays OFF).
- The per-shift ×4 cal accessors 0x3FC4C/0x40150 read ROM (three banks: default 0x492BC, alternate 0x60CEE / 0x614CE when 3FB187 b2,
  normal 0x608FE / 0x610DE). What 3FB187 b2 means is unknown (the same bit swaps the torque-cut tables).

## Files

- Scratchpad scripts copied to `scripts/`: `canrx.py` (RX/TX descriptor dump), `tqcut.py` (torque-cut tables), `trqreq.py` / `trqreq2.py`
  (CAN check), `solgear.py` / `tcc.py` (TRANS-log duty by gear), `lp.py` (line-pressure constants and curves).
