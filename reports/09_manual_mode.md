# TCM 09: manual mode, from the lever switches to the gear request (2026-11-20)

**Status:** switch path CONFIRMED (code + the 2026-11-16 svc1 CAN captures, where Cam used manual mode). Gear logic CONFIRMED in code.
The live TCM RAM check is PROBE page 9 (last step).

## 1. The switches arrive over CAN 0x2DE, not wires

FSM AT-91/97 lists MANU MODE SW, NON M-MODE SW, UP SW LEVER and DOWN SW LEVER. On this car the TCM reads them from **CAN 0x2DE**
(RX mailbox 10, FUN_20BC4 → 3FB889 = byte 0, 3FB88A = byte 1). FUN_3EB20 debounces them (2-sample agreement) into 3FB7AE / 3FB7B0.

**0x2DE byte 0** (svc1 captures 170822-180749: 26 lever events, every one consistent):

| value | switch | seen when | 3FB150 bit |
|---|---|---|---|
| 0x02 | NON M-MODE SW | lever in the D gate (also all of P/R/N) | b0 |
| 0x01 | MANU MODE SW | lever in the manual gate | b1 |
| 0x04 | UP SW LEVER | tap + (0x251 target gear goes up one) | b2 |
| 0x08 | DOWN SW LEVER | tap − (target goes down one) | b3 |
| 0x00 | none | ~10-30 ms while the lever crosses gates | — |
| bits 4/5 | (unused here; would be 3FB150 b4/b5) | never seen | b4/b5 |

The gate bit drops during a tap (0x01 → 0x08 → 0x01), so the lever's tap position is a third contact. **Byte 1 bit 3** toggles
independently (0/8, at stops and in motion; → 3FB15C b2). CANDIDATE: brake switch. 3FB150 b6/b7 come from ECM 0x23E byte 1 (b7, b2).

## 2. Pattern check (FUN_3E390 → 3FB164) and P1815

The six bits form an index (NON-M = 0x20, M = 0x10, UP = 0x08, DOWN = 0x04, b4 = 0x02, b5 = 0x01) into ROM **0x4B2B8**:

| index | state 3FB164 low nibble | meaning |
|---|---|---|
| 0x20 | 0 | D gate |
| 0x10 | 9 | manual gate, holding |
| 0x08 | 0xD | tap UP |
| 0x04 | 0xB | tap DOWN |
| 0x11 / 0x12 / 0x13 | 0xA / 0xC / 0xE | manual + the unused bits (other models' steering switches?) |
| 0xFF or 0xA5 entries (both gates, up+down, nothing at all…) | — | **impossible pattern**: 3FB1F3 b7 (feeds P1815 MANU MODE SW, FSM AT-172) |

The check is skipped above ROM 0x4B133 km/h when a fault or fail-safe is active. Cal 0x60374 b1 = 1 enables it.

## 3. Gear request (FUN_3DE1C, in range state 3FB7C4 = 4 or 7 = manual)

- **Entering manual:** cal **0x60337 b0 = 1**, so the request 3FB778 starts at the **current gear** (table 0x4B2F6). With the bit
  clear it would start at 5th (0x85).
- **Gear codes:** 0x83 = 1st, 0x82 = 2nd, 0x81 = 3rd, 0x85 = 4th, 0x80 = 5th (index table 0x4B2FB, step table 0x4B30A / 0x4B317).
  0x251 byte 2 (the cluster's M-gear display) = (gear index << 2) | 2, so 2 / 6 / 10 / 14 / 18. Seen in the captures: 10 → 6 → 2 on two
  DOWN taps, then 6 on an UP tap.
- **A tap** is an edge of 3FB164 against its previous value (3FB31A). FUN_3DD70 moves the request one gear up or down. The request then
  moves toward the target at most one gear per pass (permission table 0x4BA14).
- **A tap is refused** (FUN_3DD70 returns "no change") when **3FB2C3 b0 (up inhibited)** or **b1 (down inhibited)** is set.
- **Sync:** whenever the actual gear differs from the request (the TCM shifted by itself: auto-downshift when slowing, forced upshift),
  the request is reset to the actual gear (cal 0x60337 b0 = 1 makes this work both ways).

## 4. Over-rev / lugging guards = the slot-4 shift lines (FUN_33ED0)

In manual (3FB7B6 = 4/7), for the current gear the TCM evaluates two segment curves from the pointer table **0x6FA04** at x = 3FB7A6
(speed input of every shift line, TCM 02):

| gear | "up" curve (inhibit UP when curve ≤ 3FB7FE) | "down" curve (inhibit DOWN when curve > 3FB7FE, or 0xFF) |
|---|---|---|
| 1st | 0x6D1E3 = slot-4 up 1→2 | 0x6D4D5 (dummy) |
| 2nd | 0x6D1C2 = slot-4 up 2→3 | 0x6D210 = slot-4 down 2→1 |
| 3rd | 0x6D19B = slot-4 up 3→4 | 0x6D1F5 = slot-4 down 3→2 |
| 4th | 0x6D17D = slot-4 up 4→5 | 0x6D1D4 = slot-4 down 4→3 |
| 5th | 0x6D4D9 (dummy) | 0x6D1AD = slot-4 down 5→4 |

So the **slot-4 shift lines in the defs** are the manual-mode permission lines: an UP tap is refused below the up line (would lug), and a
DOWN tap is refused above the down line (would over-rev). Editing them changes how low/high manual mode lets you go. 3FB7FE's meaning
(throttle-like y input) follows TCM 02. Defs note: the slot-4 rows in CG401_tcm_tables.csv are these.

## 5. For tuning

- "Won't let me downshift" = the slot-4 down line for that gear at that speed.
- Manual mode holds the gear (no auto-upshift) only as far as the separate manual-range shift lines allow; the sync in §3 follows
  whatever the shift logic does.
- A **"start in 5th"** behaviour is one bit (0x60337 b0) away; stock starts at the current gear.
