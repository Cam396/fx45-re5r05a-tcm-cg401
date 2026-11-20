"""CG401 (2004.0 FX45 RE5R05A, Bosch GS19 / MPC555) calibration checksum: CRC-16/XMODEM
(poly 0x1021, init 0x0000, no reflection, no final xor) over 0x60090-0x6FFFB, stored big-endian at 0x6FFFC.

usage:
  python3 cg401_cal_crc.py <image.bin>            check only
  python3 cg401_cal_crc.py <image.bin> --fix      recompute and write the stored CRC in place (keeps a .bak copy)

Research tool, not flash-tested. Only the calibration-region CRC is handled here; the 13 block/header CRCs
(TCM report 01 §3) cover code/header areas that a calibration edit doesn't touch.
"""
import shutil
import sys

START, END, STORE = 0x60090, 0x6FFFC, 0x6FFFC   # CRC covers START .. END-1 (= 0x6FFFB)
SIZE = 0x70000                                     # 448 kB internal flash image


def crc16_xmodem(data, crc=0):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path, fix = sys.argv[1], '--fix' in sys.argv[2:]
    img = bytearray(open(path, 'rb').read())
    if len(img) != SIZE:
        sys.exit('expected a %d-byte image, got %d' % (SIZE, len(img)))
    calc = crc16_xmodem(img[START:END])
    stored = int.from_bytes(img[STORE:STORE + 2], 'big')
    print('cal CRC calculated 0x%04X, stored 0x%04X: %s' % (calc, stored, 'OK' if calc == stored else 'MISMATCH'))
    if fix and calc != stored:
        shutil.copyfile(path, path + '.bak')
        img[STORE:STORE + 2] = calc.to_bytes(2, 'big')
        open(path, 'wb').write(img)
        print('written 0x%04X at 0x%05X (backup: %s.bak)' % (calc, STORE, path))
    sys.exit(0 if calc == stored or fix else 1)


if __name__ == '__main__':
    main()
