# TCM 08: DTC table, status bits, and the P0744 monitor (2026-11-19 night)

**Status:** table, bit map, the §4 monitor conditions and the §5 ATF-temp chain CONFIRMED (ROM data + the readers FUN_23364 / FUN_277B8). P0744 monitor CONFIRMED in code; units of
two of its inputs CANDIDATE.

## 1. The table

- **Codes:** ROM 0x47BDC, 37 u16 entries (D000 = U1000).
- **Descriptors:** pointer table 0x47F64 → one 0x18-byte record per code, {u32 RAM status word, u8 type = 1, u8 bit mask, …}.
- **Read-out:** FUN_23364 walks all 37 (FUN_43834 tests the bit) and returns the set codes as 2-byte pairs. That's the K-line DTC
  read.
- **Clear:** FUN at dec_all.c line 26358 zeroes the five status words.

| idx | DTC | status bit | idx | DTC | status bit |
|---|---|---|---|---|---|
| 0 | U1000 (D000) CAN | 3FBA48 b7 | 19 | P1759 FR/B function | 3FBA48 b3 |
| 1 | P0720 vehicle speed sensor A/T (revolution sensor) | 3FBA44 b1 | 20 | P1762 D/C solenoid | 3FBA44 b6 |
| 2 | P0725 engine speed signal | 3FBA4C b6 | 21 | P1764 D/C function | 3FBA44 b5 |
| 3 | **P0744 TCC function** | **3FBA4C b0** | 22 | P1767 HLR/C solenoid | 3FBA48 b0 |
| 4-8 | P1701-P1704 TCM, P1709 (not in the FSM) | (no RAM bit; TCM self-test path) | 23 | P1769 HLR/C function | 3FBA44 b7 |
| 9 | P1716 turbine sensor | 3FBA44 b3+b4 | 24 | P1772 LC/B solenoid (on/off) | 3FBA48 b6 |
| 10 | P1721 vehicle speed sensor MTR | 3FBA44 b2 | 25 | P1774 LC/B function | 3FBA48 b5 |
| 11 | P1815 manual-mode switch | 3FBA4C b7 | 26 | P0615 start signal | 3FBA4C b3 |
| 12 | P1710 fluid temp sensor | 3FBA4C b4 | 27 | P1705 throttle position | 3FBA4C b5 |
| 13 | P0705 PNP switch | 3FBA44 b0 | 28 | P1730 interlock | 3FBB00 b0 |
| 14 | P0740 TCC solenoid | 3FBA4C b1 | 29 | P1731 1st engine braking | 3FBB00 b1 |
| 15 | P0745 line-pressure solenoid | 3FBA4C b2 | 30 | P1812 (not in the 2004 FSM) | 3FBB00 b2 |
| 16 | P1752 I/C solenoid | 3FBA48 b2 | 31-35 | P1841, P1842, P1843, P1845, P1846 (pressure switches 1, 2, 3, 5, 6) | 3FBB00 b3-b7 |
| 17 | P1754 I/C function | 3FBA48 b1 | 36 | P1825 (not in the 2004 FSM) | 3FBB04 b0 |
| 18 | P1757 FR/B solenoid | 3FBA48 b4 | | | |

Names follow the 2004 FSM AT DTC index. The P17xx element codes pair circuit/function (I/C, FR/B, D/C, HLR/C, LC/B) as in report 07 §4.
Bits are on the low byte of each 32-bit word (Ghidra's `DAT_003fba4c._3_1_`).

**Set alongside P0744 (§2), probably for the others too (not checked):** 3FBA40 b0 (a "malfunction present" summary) and 3FB293 b3
(fail-safe request; 3FB293 b0/b1 feed the forced shift-line path of TCM 04).

## 2. P0744 TCC function: two monitors, FUN_2BA30 and FUN_2BB14 (T44, 20 ms)

FSM AT-125: "lock-up commanded but slip doesn't fall; compares a reference value with the slip rotation".

**A, lock-up states (TCC state 3FB821 = 2 or 5):** count while **all** of these hold:
- 3FB5FE > ROM 0x4B0CE = 15,200 (an input or turbine speed word; unit CANDIDATE)
- no fault or override bits (3FB292 b0/b1, 3FB293 b2)
- 3FB2F8 ≥ 0
- **slip word 3FB2F6 (id 1108) ≥ vehicle speed (3FB796, km/h) / 2 + 40**

Fault when the counter reaches ROM **0x4B0D0 = 600 ticks (12 s at 20 ms)**. Any break in the conditions resets the count.

**B, slip-control states (3FB821 = 1 or 4):** reference = 3FB825 + ROM 0x4B0D6 (= +65). Same speed gate (0x4B0D2 = 15,200) and fault
gates. It counts while slip 3FB2F8 ≥ the reference, and faults at **0x4B0D4 = 600 ticks**.

**Reading it:** P0744 needs about **12 s of continuous excess slip** with lock-up commanded. That's why a slipping converter clutch can
shudder for a long time before the light comes on.

## 3. Element function vs pressure switch: P17xx / P184x (FUN_2CF00 → 2CBF8 / 2CD9C → 2C880)

Per element, a counter runs while the command says "applied" (≤ 641) but the switch reads off, or the command says "released"
(≥ 9615) but the switch reads on. FR/B uses the opposite sense. Each mismatch kind has its own counter, and the limit is RAM 3FB654
(debounce). Then FUN_2C880 decides which code it is:

- **below ROM 0x4B0B6 = 10 km/h** (3FB797): the element **function** code (P1754 / P1759 / P1764 / P1769 / P1774 via 3FB842/843);
- **above 10 km/h**, if the turbine/output ratio 3FB2FC (×1000) sits inside the current gear's window, the gear is fine, so it's the
  **switch** code (P1841-P1846, 3FBB00), as the FSM says ("actual gear ratio is normal and the switch is irregular"). Otherwise it's the
  element function code;
- the switch code also needs 3FB15C b4 = 0, 3FB865 = 0 and a per-gear enable byte = 0 (else: function code). In fail-safe (3FB293 b0) it is always the function code.

**In-gear ratio windows (ROM 0x4B0BA, {lo, hi} u16 per gear):** 1st 3.543-3.707, 2nd 2.237-2.400, 3rd 1.425-1.589, 4th 0.942-1.106,
5th 0.772-0.936. The logged ratios (1st 3.59, 2nd 2.30, TCM 06 §4) fall inside them, which confirms the ×1000 scale.

## 4. The other monitors (dispatcher FUN_2D260, 20 ms task; ticks = 20 ms unless noted)

All gates and limits are ROM bytes/words in the 0x4B0xx block (read from the 2026-11-19 dump). Speeds are km/h (3FB796 A/T VSS,
3FB797 processed speed, 3FB798 meter VSS), engine rpm 3FB2E2 is rpm (CAN 0x23D, TCM 03). "Immediate" = no counter. FSM checks are
against AT-108…AT-170 (2004.0).

| DTC | function | sets when | limit | FSM check |
|---|---|---|---|---|
| P0720 VSS A/T | FUN_2A730 | **before the A/T sensor has ever read ≥ 5 km/h** (0x4B084, latched in 3FB1B7 b0): meter speed ≥ 20 km/h (0x4B085). After it has: a drop-out counter (3FB28E b5) passes 0x4B08C = 51 | 0x4B14C = **40 ticks (0.8 s)** | matches "irregular signal … before the vehicle starts moving" |
| P1721 VSS MTR | FUN_2A730 | mirror image: meter never ≥ 5 km/h (0x4B08F) while A/T speed ≥ 20 (0x4B090); drop-out limit 0x4B097 = 20 | 0x4B14E = 40 ticks | ✓ |
| | | both set fail-safe 3FB293 b0/b1 (3FB797 then uses the other sensor, TCM 02); recovery when both speeds sit in 5-20 km/h | | |
| P1705 TP (CAN) | FUN_2AA7C | CAN throttle byte 3FB884 fails its complement check (3FB896 = ~884), ECM fail flag 3FB1CB b7, or 3FB15C b5 with throttle 0. Second path: 3FB15C b4 **and** b5 together (CANDIDATE: closed + full-throttle bits) | 0x4B0A8 = **100 ticks (2 s)**; second path 0x4B0B1 = 100 | "proper accelerator pedal signals (CAN) from ECM" ✓ |
| | | runs only ≥ 0x4B133 = 5 km/h or in fail-safe | | |
| P1772 LC/B solenoid | FUN_2AC00 | on/off solenoid: command 3FB1DC b0 ≠ output readback 3FB2C4 b0, either direction, **> 3 / ≥ 4 consecutive** | 4 ticks | ✓ ("improper voltage drop") |
| P0740, P0745, P1752, P1757, P1762, P1767 | FUN_2AD00 | per linear solenoid, command vs current monitor (command 3FB6E4 TCC, 6E6 line pressure, 6E8 I/C, 6EA FR/B, 6EC D/C, 6EE HLR/C; monitors 3FB92E…938, 0-10240): **command < 7692 (0x4B150) but monitor > 10256 (0x4B152)**, or **command ≥ 2564 (0x4B154) but monitor ≤ 641 (0x4B156)**. Each kind has its own counter (latches 3FB233 / 3FB22F) | 0x4B047 = **100 ticks (2 s)** | "comparing target value with monitor value" ✓ |
| | | battery 3FB9F8 < 9000 mV clears all counters; TCC/line-pressure are skipped while any of a set of other faults is set (3FB228 b1, 3FBA38/3C bits, 3FB842 b1) | | |
| P0744 | FUN_2BA30 / 2BB14 | §2 | 600 ticks | ✓ |
| P1710 ATF temp | FUN_2BC18 | 3FB792 < 0x4B136 = 53 or 3FB793 < 0x4B137 = 53 (3FB792/793 = 255 − sensor voltage, so this is a **high-voltage / open-circuit check** on sensor 1 / 2: voltage raw > 202 ≈ 3.96 V, §5) while ≥ 10 km/h (0x4B135). Sets 3FB28E b2/b3, which make the TCM use a substitute temp | immediate | "excessively low or high voltage" ✓ |
| P0725 engine speed | FUN_2BCE8 | rpm 3FB2E2 < **305 rpm** (cal 0x606E4) while > 10 km/h (0x4B09A). Clears itself when rpm returns | immediate | ✓ |
| P1716 turbine sensor | FUN_2C6D0 | **sensor 1** 3FB2F0 < 600 rpm (0x4B0A2) at > 40 km/h (0x4B0A6) and rpm > 1500 (0x4B0A4); **sensor 2** 3FB2EE < 600 (0x4B09C) only with **target gear 4th** (3FB7DF = 3) and no shift in progress (3FB7E3 = 0), > 40 km/h, > 1500 rpm. Not in fail-safe, not with gear request 0x84 | 0x4B0A7 / 0x4B0A1 = 100 ticks | "irregularity only at 4th gear for turbine revolution sensor 2" ✓ |
| P1731 1st engine braking | FUN_2BD9C | outside manual mode and outside a 1st request (3FB774 ≠ 0x83): **solenoid monitors show the 1st + LC/B pattern** (I/C, FR/B, D/C ≥ 9615, HLR/C < 9615, LC/B on) for 2 ticks (0x4B062); **or the pressure switches do** (SW1 + SW2 + SW6 on, SW3 + SW5 off) with rpm ≥ **1,200** (0x4B060) for a time from FUN_2B5BC | 2 ticks / computed | FSM confirm procedure uses **1,200 rpm** ✓; "engine brake of 1st gear acts other than at M1" ✓ |
| P1815 manual-mode switch | FUN_2BF44 | impossible switch pattern 3FB1F3 b7 (TCM 09 §2) | 0x4B063 = 40 ticks | ✓ |
| P0615 start signal | FUN_2BF9C | in P/N: starter-relay command 3FB1DC b1 ≠ its readback 3FB2C4 b1; outside P/N: the readback shows the relay ON at all | 0x4B064 = 40 ticks | "starter relay ON other than at P or N" ✓ |
| P1730 interlock | FUN_2DDA8 → 2DF18 (via 2E1D4) | pressure switches report an element applied that the current gear doesn't command (pointer table 0x4BA38…), forming one of three locking patterns 3FB772 & 0x9A / 0xC8 / 0x52 (code 3FB845 = 1/2/3) | 0x4B083 = **95 ticks (1.9 s)** | FSM confirm "2 consecutive seconds" ✓; fail-safe gear from table 0x4B6C0 (FSM: "fixed in 2nd") |
| P0705 PNP switch | FUN_3E174 | range-switch pattern 3FB773 maps to 0xFF in table 0x4B298 (0x4B277 = 0 selects it over 0x4B278) | 0x4B046 = 40 checks, one per 5 calls | ✓ |
| U1000 CAN | FUN_257E4 | any of the CAN error / timeout bits 3FB274 b0/b1/b2/b4 | immediate | ✓ |
| P1825 | FUN_2C07C | **disabled**: enable bit ROM 0x4B13C b0 = 0 (matches its absence from the FSM) | (0x4B0D8 = 40) | — |

**P17xx / P184x debounce (§3, RAM 3FB654)** is set by FUN_2B528: **40 ticks (0.8 s, 0x4B072)** when the ATF temperature value
3FB864 ≥ 0x4B0AD = 45 raw, else **160 ticks (3.2 s, 0x4B074)**. So it waits longer with cold fluid. 3FB864 = ATF temp a (3FB794), or
temp b (3FB7A5) / the constant 35 (0x4B0AE) when the P1710 range bits are set.

**Still open:** FUN_2B5BC's P1731 time, the 3FB15C b4/b5 meanings, and the task
that runs FUN_3E634 → 3E174 (P0705 tick).

## 5. ATF temperature: sensor → RAM → threshold units (2026-11-20, desk + the 11-19 RAM dump)

```
sensor voltage  3FB77B / 77C = ADC_mV × 10 / 196          (FUN at dec line 22283; 1 count = 19.6 mV, 255 = 5.0 V)   [CONFIRMED code]
filtered, inverted  3FB792 / 793 ≈ 255 − voltage          (FUN_40664 / 40758: 1/24 lag, or 1/4 with 3FB88B b4)       [CONFIRMED code]
ATF temp        3FB794 = curve 0x60375(3FB792)             sensor 1, id 110B                                          [CONFIRMED live]
                3FB7A5 = curve 0x603F7(3FB793)             sensor 2, id 110C
```

Live check (TCM RAM dump 2026-11-19 16:21): 3FB77B = 47 → 3FB792 = 207 → 3FB794 = 132, which is exactly curve 0x60375(207).
Both curves are now in the definition (category Sensors). Report 01 §5 had them down as solenoid curves; that was wrong.

Against the FSM reference values (ATF TEMP SE 1: 2.2 V at 0 °C, 1.8 V at 20 °C, 0.6 V at 80 °C), the sensor-1 curve gives
**0 °C ≈ 88, 20 °C ≈ 100, 80 °C ≈ 151 raw**. The thermistor is non-linear, so use the curve, not an offset. This makes every "cold"
threshold in this ROM a deep-cold one: the P17xx slow debounce (< 45 raw), the cold 4→5 inhibit (< 55 raw, 0x606D6) and the P1710
open check all sit well below 0 °C.

**Open (needs no car, but no answer found):** the K-line ids 110B/110C read about **18 lower** than 3FB794/7A5 at the same voltage
(drive logs: voltage 47 ↔ id 110B 114, against 132 in RAM). The id handler (table 0x48594, FUN_23FC4 → FUN_4331C) is a plain copy, so
the difference comes from somewhere not yet traced. For tuning, read 3FB794 over RAM or use the curve.
