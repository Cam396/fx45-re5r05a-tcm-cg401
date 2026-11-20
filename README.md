# FX45 RE5R05A TCM (CG401) calibration definition

A calibration map for the transmission control module in the **2004.0 Infiniti FX45** (VK45DE, RE5R05A 5-speed): a Bosch GS19 on an
MPC555, ROM id **CG401**. It was built from a K-line read of one car's TCM, using code analysis, logged drives, read-only live RAM reads and
the factory service manual.

**Research grade. Nothing here has been flash-tested.** Use it as a map that saves you mapping time, not as a proven tune base.

Start with **[`README_for_tuner.md`](README_for_tuner.md)**. It covers the module, the checksum, the formats and every area of the
definition, with a confidence level for each.

## At a glance

- **422 items / 553 RomRaider tables**, all inside the calibration block 0x60090-0x6FFFB with no overlaps. Confidence: 85 CONFIRMED,
  337 STRONG, 0 CANDIDATE.
- **What's covered:**
  - shift lines for every pattern, range and gear (D normal checked against the FSM AT-62 shift speeds and on the car);
  - lock-up;
  - line pressure;
  - shift-quality and phase timers;
  - CAN torque-cut requests;
  - the manual mode;
  - every DTC monitor threshold;
  - the ATF temperature curves.
- **Checksum:** CRC-16/XMODEM over 0x60090-0x6FFFB, stored big-endian at 0x6FFFC (stock value `0xFF97`).
  [`tools/cg401_cal_crc.py`](tools/cg401_cal_crc.py) checks it, and fixes it with `--fix`.
- **Formats:**
  - TunerPro XDF;
  - RomRaider XML;
  - a tool-neutral CSV;
  - Markdown with stock values;
  - JSON.

## Layout

| path | what |
|---|---|
| `CG401_tcm.xdf`, `CG401_tcm_romraider.xml` | the definition in TunerPro and RomRaider formats |
| `CG401_tcm_tables.csv` | one row per item: address, layout, scaling, confidence, source, notes |
| `CG401_tcm.md`, `CG401_tcm.json` | readable dump with stock values / machine-readable version |
| `reports/01-09` | the analysis behind every item (layout and CRCs, shift schedule, solenoids and line pressure, shift quality, apply elements, live RAM, FSM cross-checks, DTCs, manual mode) |
| `img/` | shift lines against the FSM windows, sequencer and timer plots, task schedule |
| `tools/` | CRC checker/fixer, the definition generator (`gen_tcm_defs.py <bin> <outdir>`), overlap/bounds checker (`check_defs.py <xml> <bin>`) |

## The stock image

The 448 kB stock image (`tcm_RE5R05A_20261119.bin`) is attached to the **[Releases](../../releases)** page, along with a zip of the whole
package. It's kept out of the git tree.

- md5 `987776c9c8e483312ad23c55c69e41e6`
- sha256 `475147bd13f2a2d9b5834ef8d266764eb9c403e4f84ed7aeb5aa0b35321a77f5`

The image holds no VIN and no immobilizer data, because the TCM isn't part of NATS.

## Corrections welcome

If you have a 2004.5+ FX, another RE5R05A vehicle (Titan, Armada, QX56, 350Z/G35 5AT variants), or a flash method for this module, please
open an issue. Comparing a second image would move a lot of STRONG items to CONFIRMED.

## License

- Definitions, reports and images: [CC BY 4.0](LICENSE). Use, share and adapt them, including commercially, as long as you credit
  this repo.
- Scripts in `tools/`: [MIT](tools/LICENSE).
- These licenses cover only the work in this repo. The stock TCM image in the Releases is the manufacturer's software and is provided
  for research and interoperability only.
