# TCM 06: live RAM, shift watch, WOT 1→2, learned cells (2026-11-19 evening)

All reads were read-only (KWP 0x2C-free: `AC 81` type 83 address list + `21 81`, header 81 18 FC), run from FX Sport's probe runner with
Cam at the car. Data: `docs/ecm_decode/data/session_20261119/` (TCM files: `probe_out_20261119_171322` learned cells,
`_174909` full SRAM 3F9800-3FFFFF + learned, `_191851` / `_192110` shift watch on two short drives up to ~45 mph) and the
FX Sport TRANS-profile drive logs in `docs/tcm_decode/data/drives_20261119/`.

## 1. Tick periods: 10 ms base, 20 ms for shifts [CONFIRMED]

The u16 counter **3FA438** rose 201 counts in 2,004 ms (low byte 0x0B → 0xD4 over 21 reads at idle in P), so **9.97 ms per count**.
**Task schedule (ROM 0x10C00):** ERCOSEK runs a 100 ms cycle of 18 slots, each {delay in 0.5 µs units, task-activation stub}. Over one
cycle T45 starts 10× (every 20,000 units = **10 ms**), T44 5× (**20 ms**), T43 2× (**50 ms**), T42 once (**100 ms**). Task records:
0x10B28 (T45, process list 0x10AC8), 0x10B58 (T44, list 0x10B40), 0x10B88 (T43), 0x10BC0 (T42). The 0x6X and 0x8X task groups (records
0x10D50... and 0x10F6C..., same slot timing at 0x10E30 / 0x11048) hold alternative copies of the same processes.

| task | period | what runs there (writers traced through dec_all.c) |
|---|---|---|
| T45 | 10 ms | 3FA438 counter and the lever-sequence (engineering-mode) check FUN_21184, engine torque 3FB310, turbine torque 3FB4FA, ratio/progress 3FB2FC |
| T44 | 20 ms | sequencers A/B (FUN_3FCA4 / 401A8) and their phase timers 3FB49C/49E, apply ramp 3FB502 += 3FB3D4 + 3FB3DE (FUN_2879C), end target FUN_261A8, shift time 3FB67A, learning FUN_2F540, torque-cut request 3FB872 |

So **every "ticks" value in the phase-timer, apply-ramp-step, shift-time-target, deadband and downshift-detection tables is 20 ms**
(1→2 shift-time target 15 = 300 ms; 2→3 55-90 = 1.1-1.8 s). The engineering-mode window (500 ticks) is 10 ms ticks = 5 s. The live
ramp step every ~20-25 ms (§2) matches T44.

## 2. Element sequencers A/B [CONFIRMED for upshifts]

The shift watch logged 3FB502 (A), 3FB506 (B), the target terms 3FB46E/470, floor 3FB522, progress 3FB2FC and, every ~3 s, the ramp
3FB3E0/3FB3D4, the active learned cell 3FB694, the converter torque ratio 3FB312 (×1024; probe header called it engine torque by mistake) and input speed 3FB2E2.

- **Upshifts:** A starts at a value from the initial-apply table (300-750 seen), **climbs linearly while B holds 10000**, then jumps to
  **10000** (full) when the shift completes, and returns to 0 before the next shift. So **A = the engaging element's apply command**.
  During the climb 3FB46E (target term) falls toward 0 and 3FB522 (floor) is 1354 / 2100 / 2283 depending on the shift.
- **Coast downshifts:** A holds 10000 while **B** drops to 0 and climbs slowly (+8-16 per ~100 ms), then jumps to 10000.
- **Slope follows 3FB3D4:** 3D4 = 8 → A climbs ~32-40 per 100 ms; 9 → ~36; 25 → ~100; 43 → ~170-230. That's about **one 3D4 step every
  20-25 ms**, i.e. one per T44 run (§1) (TCM 03's `3FB502 += 3FB3D4 + 3FB3DE`).
- **3FB3DE = torque-cut extra ramp, off in stock [CONFIRMED]:** FUN_25E9C/25E44: 3DE = min(K × 3FB510 / 1024, max), with 3FB510 =
  (engine torque 3FB310 − 3FB30E) × converter ratio / 1024, only while the torque-reduction request 3FB872 (CAN 0x253 b3) has been on for
  more than 3FB4BC ticks (counter 3FB46A) or ended no more than 3FB4BE ticks ago (3FB46C). Table 0x65628, 4 upshifts × {min ticks, max ticks
  since, K, max}: stock K = 0 for all four (max 1430/710/1460/240), so 3DE = 0, as logged. Defs v3.2 item "Torque-cut extra apply ramp".
- **3FB46E/470 [STRONG, code in TCM 05 §2]:** 46E = a·|T_turbine|/1024·gain/1024 (+ b·hold, b = 0); 470 = A at phase start − c·|T|/1024,
  latched once (3FB1AF b4), so the end target 3FB504 = max(46E + 470, floor 3FB522) starts at the pressure the clutch already has and rises
  with torque. Live: 46E falls toward 0 as turbine torque drops during the shift (torque cut + ratio change); 470 is negative on light
  throttle (−1421 seen) because c·|T| exceeds the captured A. Consistent with the code. A direct numeric check needs 3FB4FA in the log. 3FB3D4 = 3FB3E0 in every upshift seen, because the
  stock clamp pins the learned cell to 256 (§3).
- **Which shift:** the active learned cell 3FB694 equals the learned value of the shift/band being executed: 237 (1→2 band 0),
  20 (1→2 band 2), 47 (2→3 band 0), 69 (3→4 band 0). This gives a way to tag shifts in a RAM log without a gear signal.

## 3. Learned cells: updated, but ignored in stock [CONFIRMED]

Learned cells 3FBA8A[shift][band] (same in RAM, NV shadow 3FA1F4, and reads at 17:49 and 19:06):

| shift | bands 0-3 | bands 4-8 |
|---|---|---|
| 1→2 | 237, 3, 20, 23 | 256 |
| 2→3 | 47, 14, 0, 256 | 256 |
| 3→4 | 69, 3, 96, 77 | 256 |
| 4→5 | 256 | 256 |

**Update (FUN_2F540):** target = shift-time table 0x6890C[shift] by turbine torque (3FB867); deadband 0x6864C = 1 tick; measured =
3FB67A. If measured < target − 1: new = old × measured / (target − 1); if measured > target + 1: new = old × measured / (target + 1);
otherwise unchanged; a 0 cell is treated as 256. **Low cells = shifts that keep finishing faster than the (very short) targets**
(1→2 target 12-25 ticks, 2→3 55-90, 3→4 50-70, 4→5 17-47).

**Use (FUN_41CCC):** ramp used 3FB3D4 = base ramp 3FB3E0 × clamp(cell, min 3FB57C, max 3FB57A) / 256, with min/max from table 0x668AC
by shift and turbine torque. **Stock min = max = 256 for every shift and band**, so the clamped cell is always 256 and the learning has
**no effect** on shifts. Live proof: 3FB3D4 = 3FB3E0 in every logged upshift. The drifted cells on this car are harmless. Widening the
clamp would turn shift-time adaptation on (defs v3.1 item "Adaptive cell clamp"). The earlier notes in this report's first draft and in chat
("slowing to its floor", then "low = faster apply") are both superseded: in stock the cell doesn't touch the ramp at all.

## 4. WOT 1→2 [matches factory]

Two D-range WOT pulls in the 07:49 and 16:30 TRANS logs: 1st held to 6,176-6,208 rpm (turbine 6,080), ratio leaves 3.59 at
**41 mph ≈ 66 km/h**, reaches 2.30 within 0.6-0.8 s. FSM: 64-68 km/h. The ROM's 54 km/h WOT line is the decision point; the shift
lands ~1 s later (TCM 04 §6 explanation confirmed in shape). Converter slip falls from ~89 % at launch to 1.6 % at redline.

## 4b. Line-pressure unit vs the factory line-pressure test (FSM AT-53) [0.1 kPa STRONG]

FSM AT-53 (2004 FX45, VK45DE): line pressure **D/M idle 373-422 kPa, D/M stall 1,310-1,500 kPa; R idle 392-441, R stall 1,700-1,890**;
stall speed 2,300-2,600 rpm (AT-350).

- **Stall:** the base line pressure is clamped to 0x67EAE = 13720. At stall the input torque (engine torque × converter ratio 1.82 at
  speed ratio 0, curve 0x60474) drives the 1st-gear steady curve 0x68458 past 13720 (it crosses it at T_in ≈ 6,350 raw), so the target
  saturates at the clamp: **13720 × 0.1 kPa = 1,372 kPa, inside the FSM's 1,310-1,500**. The same value is the failsafe fixed maximum
  0x67EA4, which fits the FSM note that a dead line-pressure solenoid gives maximum pressure (AT-? "Line Pressure Solenoid").
- **Idle:** the minimum clamp / fixed-minimum mode 0x67EAC / 0x67EA2 = 4900 = 490 kPa, above the FSM's 373-422 in D. Either the TCM's
  scale is absolute (490 − 101 = 389 kPa gauge, inside spec; but then stall = 1,271 kPa gauge, just under 1,310), or the regulator can't
  follow targets that low at idle. Open; a gauge on the line-pressure port at idle would settle it in two minutes.
- **R:** FSM R stall (1,700-1,890) is above the TCM's 1,372 maximum, so the R boost is hydraulic (valve body), not a TCM table.
- Log check attempted: TRANS log id 1111 (line-pressure solenoid measured duty) reads 96-97 at idle and 86-87 at WOT (lower duty =
  more pressure, as the FSM says for this normally-high-pressure solenoid); id 1127 (T_in) is stale in that log, so no numeric fit.

**Verdict:** pressure tables are in **0.1 kPa** (STRONG, FSM stall match); possible absolute-vs-gauge offset of ~100 kPa at the low end.

## 5. Still open

- ~~Phase-timer tick~~ (20 ms, §1), ~~3FB3DE~~ (off in stock, §2), ~~3FB46E/470~~ (§2; numeric check wants 3FB4FA logged), pressure unit: 0.1 kPa STRONG (§4b, FSM AT-53); idle offset open (A/B are 0-10000 "per-mille-ish" of full; the kPa link needs a pressure reference).
- Learned-cell update and use: DONE (§3, inert in stock).
- ~~CAN 0x2A5~~ (20:05): the TCM reads only byte 3 bits 0-1 (FUN_20BC4, mailbox 14). Both set → latched 3FB76B = 1 → 3FB2BF b0 →
  fallback phase-timer banks 0x492BC/0x496AC below 5 km/h with no shift in progress. Every capture on this car shows
  `00 00 00 80 00 00 00 00` (62 Hz), so it never triggers. Sender unknown: no plain 0x2A5 id entry in the ECM ROM. A fuse-pull test
  (AWD / ABS-VDC / meter) with CAN logging would name it. It doesn't matter for tuning.
- Desk: manual-mode logic (lead: FUN_3EB20 builds the switch words 3FB15C/3FB150/3FB20F from inputs 3FB769-76B and CAN bytes
  3FB885-889), P07xx/P17xx thresholds.
