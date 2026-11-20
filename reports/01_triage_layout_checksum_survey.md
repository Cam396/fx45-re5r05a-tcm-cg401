# TCM 01 · Triage, chip, layout, checksum, data ids, first map survey

**Module:** RE5R05A (Jatco 5-speed) TCM, FX45. Read 2026-11-18/19 by FX Sport over K-line (profile `tcmrom`), 0x00000–0x6FFFF.
**Image:** 458,752 bytes, md5 `987776c9c8e483312ad23c55c69e41e6` (provisional pull taken during FX Sport's verify pass; see
the end of this file for the verified md5).

## 1. Chip: PowerPC (MPC555 class), not SH-2 [CONFIRMED]

The ECM is a Renesas SH7055. **The TCM is a different architecture: Freescale/Motorola PowerPC MPC5xx.**

| evidence | detail |
|---|---|
| reset table | 8-byte entries at 0x0, each `ba <target>` (opcode 18, AA=1). This is the MPC5xx BBC "exception table relocation" format, not SH vectors |
| system reset | entry 1 (vector 0x100) → `ba 0x12C`: fills every GPR with 0x7F7F7F7F, sets r13/r2, jumps to the boot code |
| flash size | exactly 448 kB = MPC555 CMF A (256 kB) + CMF B (192 kB). So **the read covers the whole chip** |
| SRAM | r13 = 0x4017F0 → SDA base 0x3F97F0 + 0x8000. MPC555 internal SRAM is 0x3F9800–0x3FFFFF (26 kB). Every RAM variable is 0x3Fxxxx |
| peripherals | 117 `lis rX,0x30` → the IMB at 0x30xxxx (TPU, QADC, QSMCM, MIOS, TouCAN) |
| small-data bases | boot r13 0x4016F0 / r2 0x16000; application r13 0x4017F0 / r2 0x187DC (`addi r2,r2,-0x7824`) |

Ghidra: language `PowerPC:BE:32:default`, project `/root/fx45_rom/ghidra/FX45_TCM`. Setup is `ghidra_scripts/TCMSetupPPC.java`
(memory map, r2/r13 context, entry points) followed by `TCMProlog.java` (seeds `stwu r1,-N(r1)` prologues and `bl`
targets). Result: **1,372 functions, 63,590 instructions = 254 kB (55 % of the image; ~85 % of the non-erased code area)**.
All 1,372 decompile without errors (`data/dec_all.c`).

## 2. Layout: four signed blocks [CONFIRMED]

| block id | span | header | footer | contents |
|---|---|---|---|---|
| `BB020204` | 0x00000–0x0FFFF | 0x00108 | 0x0FFEC | bootloader (reprogramming, own CRC table at 0xFDE4) |
| `CBBB0202` | 0x10000–0x107DB | 0x10080 | 0x107C8 | small startup stub. Checks the other blocks' headers (0x10258), then jumps to the app |
| `COBB0202` | 0x107DC–0x5FFFF | 0x107DC | 0x5FF6C | **application code** (code ends ~0x4BFFF; 0x4C000–0x5FF6B erased) |
| `DAC14924` | 0x60000–0x6FFFF | 0x60080 | 0x6FFEC | **calibration** (64 kB, all the maps) |

Header/footer format (16 bytes + 4):
```
+0  8 ASCII  block id              ("DAC14924" etc.; the cal id = Nissan software/cal number)
+8  u32      pointer to the partner (header → footer, footer → header)
+C  u16      0xFFFF
+E  u16      CRC-16 of bytes +0..+0xD of this header/footer
footer+0x10  u16  CRC-16 of the whole block (see below), then 0xFFFF
```
Each block also starts with 0x40 bytes of 0x00 then 0x40 bytes of 0xFF (block start markers, checked by 0x10258).

## 3. Checksum: CRC-16-CCITT [CONFIRMED, all 13 values recomputed]

The algorithm is **CRC-16, poly 0x1021, init 0x0000, not reflected, no final XOR** (table-driven: tables at 0xFDE4 and
0x105C8, routines 0xA268 and 0x101AC).

| what | covers | stored at | value |
|---|---|---|---|
| 8 header/footer CRCs | 14 bytes of each header/footer | +0xE | all OK |
| boot | 0x00000–0x0FFFB | 0x0FFFC | 0x7D12 |
| stub | 0x10080–0x107D7 | 0x107D8 | 0x6716 |
| application | 0x107DC–0x5FF7B | 0x5FF7C | 0x7E74 |
| **calibration** | **0x60080–0x6FFFB** | **0x6FFFC** | **0xFF97** |

(Starting the CRC at header+0x10 instead of the header gives the same value. The header's own CRC makes its residue 0.)
**For a calibration edit, recompute one halfword: CRC-16/XMODEM of 0x60090–0x6FFFB → 0x6FFFC.** The header/footer CRCs
only change if the id or pointers change. Script: `scripts/tcmcrc2.py`.

The startup stub (0x10258) checks the start markers, header/footer CRCs, ids and pointers of the app and cal blocks.
The whole-block CRCs aren't checked by 0x10258 itself (probably by the bootloader after reprogramming, or by a background task;
not located yet). That doesn't change what a flasher must write.

## 4. Data id → RAM dictionary (service 0x21/0x22 page 0x11) [STRONG]

Table at **0x48594**: 67 records of 12 bytes `{u32 RAM address, u8 size, u8 type, u16 0, u32 scaling descriptor}`, with
its header at 0x4857C (used by the id handlers at 0x23FC4/0x2315C). Mapping index k → id 0x1101 + k matches **every type
FX Sport's 2026-11-16 drive fit found**: rpm ids are 2-byte /32 types, temps are type 2, voltages type 5.

| id | RAM | size/type | FX Sport name | note |
|---|---|---|---|---|
| 1101 | 3FB796 | 1 | speed | km/h |
| 1102 | 3FB798 | 1 | speed2 | |
| 1103 | 3FB2E0 | 2, ×32 | output rpm | |
| 1104 | 3FB2F2 | 2, ×32 | turbine rpm | input to 0x6746C/0x6742E |
| 1105 | 3FB2EE | 2, ×32 | — | another shaft speed |
| 1106 | 3FB2F0 | 2, ×32 | turbine_b | |
| 1107 | 3FB2E2 | 2, ×32 | engine rpm | |
| 1108 | 3FB2F6 | 2 (desc 0x47404) | — | |
| 1109 | 3FB766 | 1 | throttle_b | input to 0x604F2 |
| 110A | 3FB992 | 1 | accel (pedal) | **the main load input to the shift/pressure code** |
| 110B/110C | 3FB794 / 3FB7A5 | 1, temp type | ATF temp a/b | |
| 110D/110E | 3FB77B / 3FB77C | 1, volt type | ATF sensor V | |
| 110F | 3FB795 | 1 | — | |
| 1110–111B | 3FB994…99E, 3FB92E…938 | 2 (desc 0x47408) | — | 12 values in two groups of 6: per-solenoid (6 solenoids?) commanded and measured currents/pressures [CANDIDATE] |
| 111C | 3FB2FC | 2, volt type | — | battery/supply? |
| 1124–1127 | 3FB310/30E/4FA/324 | | — | 3FB324 is the input to curves 0x684EC/0x68404 |
| 1128–112D | 3FB6C0…6CA | 6 × u16 | — | |
| 112E | 3FB7E4 | 1 | — | **shift index** (×4 into the per-shift tables, §5) |
| 112F | 3FB797 | 1 | — | input to most u8 curves: **processed vehicle speed, km/h** (corrected in TCM 02; was guessed as throttle/load) |
| 1131–1142 | 3FBA02–3FBA24 | | — | 6 groups of {u16, u16, u16}: per-shift **learned** values? [CANDIDATE] |

The second table at 0x47424 (26 records, same format) holds the most important subset (3FB797, accel, throttle, ATF V,
gear 3FB7F3, shift index 3FB7E4, rpm, the 12 solenoid values). It's probably the freeze-frame or dynamic-id list.

## 5. First map survey [structure CONFIRMED, meanings CANDIDATE]

**Lookup library** (0x44000 area), all "segment-slope" tables, **not** axis + value tables like the ECM:

| routine | entry format | callers |
|---|---|---|
| 0x4427C | 3 bytes `{x u8, y u8, slope u8}` | 23 |
| 0x44434 | 6 bytes `{x u8, pad, y u16, slope u16}` | 20 |
| 0x44310 | 6 bytes `{x u16, y u16, slope u16}` | 11 |

`y = y0 ± slope × (x − x0) / 16` for the segment where `x ≤ next x0`. The list ends at x = 0xFF/0xFFFF. The second argument
picks the sign (1 = falling). Decoder: `scripts/tcmseg.py`. Figure: `img/first_curves.png`.

The calibration block has **688 distinct addresses referenced by code** (`data/cal_refs.tsv`). The first ones decoded:

| table | input | shape | likely role |
|---|---|---|---|
| 0x604F2 | throttle_b | 1,310 → 6,860, S-curve, flat above ~60 % | engine torque estimate or base line pressure vs throttle |
| 0x60628 | 3FB797 | 608 → 4,096, exponential | pressure/torque vs vehicle speed (input corrected in TCM 02) |
| 0x60474 | 3FB2D2 (u16) | falling 1,866 → 1,019 | a speed-dependent correction |
| 0x60375 / 0x603F7 | 3FB38C>>5 / 3FB390>>5 | 0 → 220 in 5-unit steps, ~44 points | ~~solenoid characteristic curves~~ **ATF temperature sensor 1 / 2 curves** (x = 255 − sensor voltage, y = ATF temp 3FB794 / 7A5) [CONFIRMED 2026-11-20, TCM 08 §5] |
| 0x6746C / 0x6742E | turbine rpm | flat 28,928 / 35,456 | turbine-speed limits/thresholds (flat in this cal) |
| 0x673F8, 0x678D2/DE, 0x67B28 | accel | signed around 0x8000 | small pedal-based trims (±20 counts) |
| 0x66844/57/6A | ? | 3 related curves | |
| **0x608FE / 0x60CEE / 0x492BC** | shift index 3FB7E4×4 + k, 9 columns | 24 rows × 9 u16 | **per-shift parameter sets** (4 rows per shift: an rpm-like threshold, then 25–100 values per column). Routine 0x3FC4C picks one of three by mode flags (3FB2BF bit 1 → the copy in code at 0x492BC; 3FB187 bit 2 → 0x60CEE; else 0x608FE). Probably normal / alternate (e.g. snow/manual) / limp shift-quality parameters |

The actual **shift schedule** (vehicle speed vs pedal per upshift/downshift) and **lock-up schedule** aren't identified
yet. They're the next targets. The approach: find the code comparing output speed (3FB2E0) against a pedal-indexed table.

## 6. What this means

- **The TCM is fully readable, the checksum is solved, and the calibration is one clean 64 kB block.** That's the
  prerequisite for TCM tuning (shift points, firmness, lock-up, torque-reduction requests) and for public TCM defs.
  Nobody publishes defs for this TCM, and the Nissan PowerPC TCMs are poorly documented in general.
- No VIN, no key/immobilizer data in this image (the TCM isn't part of NATS). The only "VIN-like" strings are zero fill and table data.
- The architecture switch means none of the ECM's SH-2 tooling carries over directly. The Ghidra project, PPC setup and
  lookup decoder are now in place.

## 7. Next steps (TCM goal)

1. Shift schedule + lock-up schedule (output speed vs accel comparisons).
2. Name the 12 solenoid values (1110–111B) by following them to the TPU/MIOS output registers.
3. Shift index 3FB7E4 / gear 3FB7F3 state machine; identify the per-shift parameter rows.
4. Line pressure: 0x604F2/0x60628 chain → solenoid curves.
5. Adaptive learning (1131–1142 candidates) and where it's stored (EEPROM/flash emulation).
6. Torque-reduction request to the ECM (CAN), which ties back into the ECM decode.
7. Defs (RomRaider XML) once tables have names.

## Files

`data/triage.json`, `data/rom_map.png`, `data/func_rank.tsv`, `data/dec_all.c` (all functions), `data/dec_top.c`, `data/dec_cks*.c`,
`data/xrefs_*.tsv`, `data/cal_refs.tsv`, `img/first_curves.png`, scripts in `scripts/` (triage, tcmcrc2, tcmidt, tcmseg,
tcmplot, tcmsched, ppcscan), Ghidra scripts `TCMSetupPPC.java`, `TCMProlog.java`, `TCMStats.java`, `TCMDecompAll.java`.

## Verified image

FX Sport's verify pass finished 01:05 (458,784 verified bytes, nothing rewritten). The pulled file's md5 is **identical** to
the provisional one: `987776c9c8e483312ad23c55c69e41e6`. Archived as `captures/rom/tcm_RE5R05A_20261119.bin` (+ .md5/.sha256),
copies in Desktop\FX45_ROM, Documents\FX45_ROM_backup (read-only) and WSL /root/fx45_rom. FX Sport is back on the `fuel` profile.

## Addendum: per-shift pressure curves (found after the survey)

- **0x68404**: 14 pointers indexed by shift index 3FB7E4 → u16 segment curves of input 3FB324 (id 1127; 0 → ~6,000) giving
  7,500 → 16,100. Several shifts share 0x683BA. **0x684EC**: 8 pointers → a second family (4,420 → 11,230 and 3,700 → 9,500).
  Shape and indexing look like **per-shift line/clutch pressure vs input torque or turbine speed** [CANDIDATE].
- **0x682F8**: 10 curves indexed by 3FB958 (chosen from the gear × target-gear table 0x4B432 in 0x37904), input 3FB797:
  6,900-13,720. This is the **downshift/kickdown branch** (0x37904 tests the range byte 3FB774 = 0x80 D / 0x81-0x85 manual
  ranges, current gear 3FB7F3, target 3FB7DF) [CANDIDATE].
- **0x67668**: 10 accel-indexed curves (signed around 0x8000, +2,000 … +14,000), selected by gear + 3FB7F3: pedal-dependent
  pressure adders [CANDIDATE].
