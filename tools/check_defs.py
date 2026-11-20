"""2026-11-19: sanity checks for the TCM RomRaider XML: well-formed, every table inside the 448 kB image and the calibration
block, no two tables overlapping, and the shift-quality banks printed for a plausibility look.
usage: check_defs.py <xml> <tcm.bin>"""
import sys, struct, xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
x, binp = sys.argv[1], sys.argv[2]
rom = open(binp, 'rb').read()
root = ET.parse(x).getroot()
SZ = {'uint8': 1, 'int8': 1, 'uint16': 2, 'int16': 2, 'uint32': 4}
spans = []
for t in root.iter('table'):
    a = t.get('storageaddress')
    if a is None:
        continue
    a = int(a, 16); n = SZ[t.get('storagetype')]
    cnt = int(t.get('sizex', 1)) * int(t.get('sizey', 1))
    spans.append((a, a + n * cnt, t.get('name')))
spans.sort()
bad = [s for s in spans if not (0x60090 <= s[0] and s[1] <= 0x6FFFC)]
ov = [(p, q) for p, q in zip(spans, spans[1:]) if q[0] < p[1]]
print('tables', len(spans), '| outside cal 0x60090-0x6FFFB:', len(bad), '| overlaps:', len(ov))
for b in bad[:10]: print('  OUT', '%05X-%05X' % b[:2], b[2])
for p, q in ov[:10]: print('  OVL', '%05X-%05X %s  <>  %05X-%05X %s' % (p[0], p[1], p[2], q[0], q[1], q[2]))
u16 = lambda a: struct.unpack('>H', rom[a:a + 2])[0]
names = ['1-2', '2-3', '3-4', '4-5', '2-1', '3-1', '3-2', '4-1', '4-2', '4-3', '5-1', '5-2', '5-3', '5-4']
for base, lab in ((0x608FE, 'A'), (0x610DE, 'B')):
    print('bank', lab, '%05X' % base, '(rows: phase 1-4; col0 = progress thr, cols 1-8 = ticks by torque band)')
    for sh in (0, 1, 2, 3, 6, 13):
        a = base + sh * 72
        print('  %-4s' % names[sh], ' | '.join(' '.join('%5d' % u16(a + 18 * ph + 2 * c) for c in range(9)) for ph in range(4)))
