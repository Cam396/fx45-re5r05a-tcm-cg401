"""TCM (RE5R05A, ROM id CG401 / RX0612, MPC555) definitions: RomRaider XML + JSON + markdown.

Research grade: every item carries its confidence and the report that backs it. NOT flash-tested.
The calibration CRC (CRC-16/XMODEM, stored at 0x6FFFC, over 0x60090-0x6FFFB, TCM 01 §3) must be recomputed
after any edit; RomRaider does not do that.

Segment-curve formats (all evaluate y = y0 + slope*(x - x0)/16 on (x0, next x0]):
  seg8     3-byte records {x u8, y u8, slope u8}, ends when the next x >= 0xFF   (FUN_4427C)
  seg16    6-byte records {x u16, y u16, slope u16}, ends when the next x >= 0xFFFF (FUN_44310)
  seg8x16  6-byte records {x u8, pad, y u16, slope u16}, ends when the next x >= 0xFF (FUN_44434)

usage: python3 gen_tcm_defs.py <tcm.bin> <out_dir>
"""
import sys, os, json, struct
from xml.sax.saxutils import escape

rom = open(sys.argv[1], 'rb').read()
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
u8 = lambda a: rom[a]
u16 = lambda a: struct.unpack('>H', rom[a:a + 2])[0]
s16 = lambda a: struct.unpack('>h', rom[a:a + 2])[0]
u32 = lambda a: struct.unpack('>I', rom[a:a + 4])[0]


def seg(addr, fmt):
    recs = []
    step = {'seg8': 3, 'seg16': 6, 'seg8x16': 6}[fmt]
    for k in range(100):
        a = addr + step * k
        if fmt == 'seg8':
            r = (u8(a), u8(a + 1), u8(a + 2))
            end = r[0] == 0xFF
        elif fmt == 'seg16':
            r = (u16(a), u16(a + 2), u16(a + 4))
            end = r[0] == 0xFFFF
        else:
            r = (u8(a), u16(a + 2), u16(a + 4))
            end = r[0] == 0xFF
        if end:          # terminator: only its x field belongs to this curve; the rest is the next table
            break
        if k and r[0] <= recs[-1][0]:
            break
        recs.append(r)
    return recs


def ev(recs, x, top):
    for i, (x0, y0, s) in enumerate(recs):
        nxt = recs[i + 1][0] if i + 1 < len(recs) else top
        if x <= nxt or nxt >= top:
            return min(y0 + (s * (x - x0) >> 4), 0xFFFF if top > 0xFF else 0xFF)
    return recs[-1][1]


ITEMS = []

CONST = {'Shift schedule': {}, 'Lock-up': {}}


def const_line(recs, a, bucket_all):
    """A one-record line with zero slope and y 0 or 255 is a constant "never"/"always" cell: count it, don't list it."""
    if len(recs) == 1 and recs[0][2] == 0 and recs[0][1] in (0, 0xFF):
        bucket_all.setdefault('_', []).append((a, recs[0][1]))
        return True
    return False

# Shift index 3FB7E4 = table 0x4B1E0[from_gear*5 + to_gear] (gears 0-based; FUN_3BB1C) [CONFIRMED, TCM 04 §1]
SHIFT_NAMES = []
_inv = {}
for f in range(5):
    for t in range(5):
        v = rom[0x4B1E0 + f * 5 + t]
        if v < 14: _inv[v] = '%d→%d' % (f + 1, t + 1)
SHIFT_NAMES = [_inv[i] for i in range(14)]
SHIFT_LIST = ', '.join('%d = %s' % (i, n) for i, n in enumerate(SHIFT_NAMES))


def add(**k):
    ITEMS.append(k)


# ---------------- constants ----------------
add(kind='curve', name='Gear ratios (1st-5th)', addr=0x6843C, storage='uint16', n=5, axis=['1st', '2nd', '3rd', '4th', '5th'],
    units='ratio', expr='x/1024', to_byte='x*1024', fmt='0.000', cat='Gearbox', conf='CONFIRMED', rep='TCM 02 §1',
    note='Matches the logged turbine/output ratio. FX Sport RATIOS must use these.',
    raw=[u16(0x6843C + 2 * i) for i in range(5)])
for a, nm, units, expr, tob, conf, rep, note in (
        (0x606D6, 'Cold-ATF 5th-gear inhibit threshold', 'ATF raw', 'x', 'x', 'CONFIRMED', 'TCM 02 §5', 'No 4→5 upshift while ATF temp 3FB794 < this (unless cal 0x6055E bit 5).'),
        (0x60352, 'Shift-schedule pedal source flags', 'bits', 'x', 'x', 'CONFIRMED', 'TCM 02 §2', 'Bit 1 = 0 (stock): shift lines read throttle_b 3FB766 (from ECM CAN 0x23E b6); 1: read the accel pedal 3FB992 (0x23D b2). The factory shift speeds (FSM AT-62) match the lines at y = 128 (half) and 255 (full), so y is a 0-255 full-travel scale. Rescales every line if flipped.'),
        (0x6055E, 'Pattern-selection feature flags', 'bits', 'x', 'x', 'STRONG', 'TCM 02 §3', 'b0 mode switch → pattern 1, b2/b4 manual inputs → patterns 2/6, b5 analog-input path.'),
        (0x60568, 'Sporty pattern: pedal hold level', 'throttle_b', 'x', 'x', 'STRONG', 'TCM 02 §3', 'Pattern 5 stays latched while throttle_b ≥ this.'),
        (0x6059B, 'Sporty pattern: hold timer below 60 km/h', 'ticks', 'x', 'x', 'STRONG', 'TCM 02 §3', ''),
        (0x6059C, 'Sporty pattern: hold timer above 60 km/h', 'ticks', 'x', 'x', 'STRONG', 'TCM 02 §3', ''),
):
    add(kind='scalar', name=nm, addr=a, storage='uint8', units=units, expr=expr, to_byte=tob, fmt='0', cat='Shift schedule',
        conf=conf, rep=rep, note=note, raw=[u8(a)])
add(kind='curve', name='Sporty pattern: speed band edges', addr=0x6059D, storage='uint8', n=3, axis=['band 1', 'band 2', 'band 3'],
    units='km/h', expr='x', to_byte='x', fmt='0', cat='Shift schedule', conf='STRONG', rep='TCM 02 §3', note='',
    raw=[u8(0x6059D + i) for i in range(3)])
add(kind='map', name='Sporty pattern: throttle-rate trigger', addr=0x6058B, storage='uint8', nx=4, ny=4,
    xaxis=['pedal 0-25%', '25-50%', '50-75%', '75-100%'], yaxis=['< 30 km/h', '30-60', '60-90', '> 90 km/h'],
    units='throttle_b rise / 3 ticks', expr='x', to_byte='x', fmt='0', cat='Shift schedule', conf='STRONG', rep='TCM 02 §3',
    note='Pattern 5 ("sporty") latches when the throttle rise over 3 ticks exceeds this. Lower = triggers more easily.',
    raw=[u8(0x6058B + i) for i in range(16)])
for a, nm, note in ((0x67EAC, 'Line pressure: minimum clamp', 'Base line pressure is clamped to [min, max].'),
                    (0x67EAE, 'Line pressure: maximum clamp', ''),
                    (0x67EA2, 'Line pressure: fixed minimum mode', 'Used when 3FB1E4 bit 7.'),
                    (0x67EA4, 'Line pressure: fixed maximum (failsafe) mode', 'Used when 3FB1E3 bit 0.')):
    add(kind='scalar', name=nm, addr=a, storage='uint16', units='kPa', expr='x/10', to_byte='x*10', fmt='0', cat='Line pressure',
        conf='STRONG', rep='TCM 03 §3', note=note + ' Unit 0.1 kPa STRONG: the max clamp 1372 kPa matches the FSM D-range stall line pressure 1310-1500 kPa (AT-53, TCM 07 §1); the 490 kPa minimum sits ~100 kPa above the FSM idle spec (absolute vs gauge, open).', raw=[u16(a)])
add(kind='curve', name='Line pressure: manual/limit range floors', addr=0x68452, storage='uint16', n=3,
    axis=['lever 0x83', 'lever 0x82', 'lever 0x81'], units='kPa', expr='x/10', to_byte='x*10', fmt='0', cat='Line pressure',
    conf='STRONG', rep='TCM 03 §3', note='Unit CANDIDATE.', raw=[u16(0x68452 + 2 * i) for i in range(3)])

# ---------------- shift lines: every slot x range x gear of pointer table 0x6D4F8 ----------------
SHIFT_PTR = 0x6D4F8
SENT = {0x6D4D9: 'never upshift', 0x6D4D5: 'never downshift', 0x6D4F1: 'cold-ATF 5th down-line', 0x6D4DD: 'special', 0x6D4ED: 'special'}
RANGE = ['D', 'range 1 (lever 0x85)', 'range 2 (lever 0x81)', 'range 3 (lever 0x82)', 'range 4 (lever 0x83)']
SLOT = {0: 'normal', 6: 'sporty'}
seen = {}
users_of = {}
for slot in range(7):
    for rg in range(5):
        for g in range(5):
            i = (slot * 50 + rg * 10 + g * 2) * 4
            for half, dirn in ((0, 'up'), (1, 'down')):
                if dirn == 'up' and g == 4 or dirn == 'down' and g == 0:
                    continue
                a = u32(SHIFT_PTR + i + 4 * half)
                if a in SENT or not 0x60000 <= a < 0x6FFF0:
                    continue
                lab = ('%d→%d' % (g + 1, g + 2)) if dirn == 'up' else ('%d→%d' % (g + 1, g))
                users_of.setdefault(a, []).append('slot %d %s %s %s' % (slot, RANGE[rg].split(' (')[0], dirn, lab))
for a, us in sorted(users_of.items()):
    first = us[0].split()
    slot, rg = int(first[1]), first[2]
    dirn, lab = first[-2], first[-1]
    recs = seg(a, 'seg8')
    if const_line(recs, a, CONST['Shift schedule']):
        continue
    nm = 'Shift line %s %s %s %s' % (SLOT.get(slot, 'slot %d' % slot), rg if rg == 'D' else 'range ' + rg, dirn, lab)
    conf = 'CONFIRMED' if slot == 0 and rg == 'D' else 'STRONG'
    add(kind='seg', fmt='seg8', name='%s @%05X' % (nm, a), addr=a, recs=recs,
        units='throttle_b 0-255 (x = km/h)', cat='Shift schedule', conf=conf, rep='TCM 02 §3-4, §6b',
        note=('Upshift wanted while throttle_b < line(speed); y=255 = forced.' if dirn == 'up' else
              'Downshift wanted while throttle_b ≥ line(speed).') +
             ' Used by %d slot(s): %s. Slot = pattern index (slot 0 normal D; slot 6 sporty per TCM 02 §3; slots 4/5 manual-mode always-up lines).' % (len(us), '; '.join(us[:8]) + (' …' if len(us) > 8 else ''))
             + (' MANUAL MODE: slot-4 lines are also the tap permission lines (TCM 09 §4): an UP tap is refused while throttle_b ≥ the up line, a DOWN tap while throttle_b < the down line (over-rev guard).' if slot == 4 else ''),
        xtop=0xFF, sample=[(x, ev(recs, x, 0xFF)) for x in (20, 40, 60, 80, 100, 130, 160, 200)])
    seen[a] = nm

# ---------------- lock-up: every mode x range x gear of 0x6E99C (full) / 0x6EF14 (slip) / 0x6F48C (slip, 3FB829 != 0) ----------------
lu_users = {}
for base, nm in ((0x6E99C, 'Lock-up (full)'), (0x6EF14, 'Lock-up (slip)'), (0x6F48C, 'Lock-up (slip, alt 3FB829≠0)')):
    for mode in range(7):
        for rg in range(5):
            for g in range(5):
                for half, hn in ((0, 'on-line'), (1, 'off-line')):
                    a = u32(base + (mode * 25 + rg * 5 + g) * 8 + 4 * half)
                    if not 0x60000 <= a < 0x6FFF0:
                        continue
                    lu_users.setdefault(a, []).append((nm, hn, mode, RANGE[rg].split(' (')[0], g))
for a, us in sorted(lu_users.items()):
    recs = seg(a, 'seg8')
    if const_line(recs, a, CONST['Lock-up']):
        continue
    nm, hn, mode, rg, g = us[0]
    flat = len(recs) == 1
    add(kind='seg', fmt='seg8', name='%s %s, mode %d %s %s @%05X' % (nm, hn, mode, rg, ('1st', '2nd', '3rd', '4th', '5th')[g], a), addr=a, recs=recs,
        units='throttle_b 0-255 (x = km/h)', cat='Lock-up', conf='CONFIRMED' if nm.startswith('Lock-up (full)') else 'STRONG', rep='TCM 02 §7',
        note='Lock-up wanted while throttle_b < line(speed). Pair halves = on-line / off-line hysteresis: full lock-up naming CONFIRMED 2026-11-20 against FSM AT-63 (D 5th: on 71 / off 58 km/h at closed throttle vs 66-74 / 53-61; on 196 / off 142 at half pedal y = 128 vs 191-199 / 136-144). The slip pair is the light-pedal (< 32) set from 44 km/h, matching the FSM closed-throttle slip lock-up in 4th/5th [STRONG]. '
             'Used by %d slot(s): %s.%s' % (len(us), '; '.join('%s %s m%d %s g%d' % u for u in us[:6]) + (' …' if len(us) > 6 else ''),
                                           ' Single record: constant line (often "never").' if flat else ''),
        xtop=0xFF, sample=[(x, ev(recs, x, 0xFF)) for x in (40, 60, 80, 100, 130, 160, 200)])

for cat, b in CONST.items():
    cells = b.get('_', [])
    if cells:
        z = sum(1 for _, y in cells if y == 0); f = len(cells) - z
        add(kind='note', name='%s: %d constant cells not listed' % (cat, len(cells)), addr=min(a for a, _ in cells), cat=cat, conf='CONFIRMED',
            rep='TCM 04 §4', note='%d one-record lines with y = 0 and %d with y = 255 (slope 0): "never" / "always" for that slot. Each is its own '
            '3-byte cell (%05X-%05X), so a slot can be changed in place, but only to another constant: a real line needs a new curve and a '
            'repointed table entry.' % (z, f, min(a for a, _ in cells), max(a for a, _ in cells)))

# ---------------- line pressure curves ----------------
done = set()
for i, lab in enumerate(['lever 0x8C', 'lever 0x84', '1st', '2nd', '3rd', '4th', '5th', 'failsafe']):
    a = u32(0x684EC + 4 * i)
    if a in done:
        continue
    done.add(a)
    users = [l for j, l in enumerate(['lever 0x8C', 'lever 0x84', '1st', '2nd', '3rd', '4th', '5th', 'failsafe']) if u32(0x684EC + 4 * j) == a]
    recs = seg(a, 'seg16')
    add(kind='seg', fmt='seg16', name='Line pressure base, steady (%s)' % ', '.join(users), addr=a, recs=recs,
        units='0.1 kPa (x = input torque 3FB324)', cat='Line pressure', conf='STRONG', rep='TCM 03 §3',
        note='Steady-state base line pressure vs input torque (engine torque × converter ratio). Pointer table 0x684EC.',
        xtop=0xFFFF, sample=[(x, ev(recs, x, 0xFFFF)) for x in (0, 500, 1000, 2000, 3000, 4000, 6000)])
for i in range(14):
    a = u32(0x68404 + 4 * i)
    if a in done:
        continue
    done.add(a)
    users = [SHIFT_NAMES[j] for j in range(14) if u32(0x68404 + 4 * j) == a]
    recs = seg(a, 'seg16')
    add(kind='seg', fmt='seg16', name='Line pressure base, during shift %s' % ', '.join(users), addr=a, recs=recs,
        units='0.1 kPa (x = input torque 3FB324)', cat='Line pressure', conf='STRONG', rep='TCM 01 addendum, TCM 03 §3, TCM 04 §1',
        note='Used while a shift is in progress (3FB7E3 ≠ 0). Shift index → shift from the from×to table 0x4B1E0 [CONFIRMED]: %s.' % SHIFT_LIST + '',
        xtop=0xFFFF, sample=[(x, ev(recs, x, 0xFFFF)) for x in (0, 1000, 2000, 4000, 6000)])
for a, fmt, nm, units, note in (
        (0x60474, 'seg16', 'Converter torque ratio vs speed ratio', 'x/1024 torque ratio (x = speed ratio 3FB2D2)', 'Input torque = engine torque × this / 1024. Evaluated with negative slope.'),
        (0x604F2, 'seg8x16', 'Line pressure throttle floor', 'input-torque units (x = throttle_b)', 'Floor on input torque from throttle (3FB36A).'),
        (0x60534, 'seg8x16', 'Line pressure ATF-temperature factor', '/65536 × 0x100 (x = ATF raw)', 'Multiplies input torque before the pressure curves.')):
    recs = seg(a, fmt)
    add(kind='seg', fmt=fmt, name=nm, addr=a, recs=recs, units=units, cat='Line pressure', conf='STRONG', rep='TCM 03 §3',
        note=note, xtop=0xFF if fmt == 'seg8x16' else 0xFFFF, sample=[])

# ---------------- ATF temperature sensors (TCM 08 §5, 2026-11-20) ----------------
for a, sn, out, fsm in ((0x60375, 1, '3FB794 (id 110B)', 'FSM reference ATF TEMP SE 1: 2.2 V at 0 °C, 1.8 V at 20 °C, 0.6 V at 80 °C → curve ≈ 88 / 100 / 151.'),
                        (0x603F7, 2, '3FB7A5 (id 110C)', 'FSM ATF TEMP SE 2: 2.2 V at 0 °C, 1.7 V at 20 °C, 0.45 V at 80 °C → curve ≈ 83 / 95 / 153.')):
    recs = seg(a, 'seg8')
    add(kind='seg', fmt='seg8', name='ATF temperature sensor %d curve' % sn, addr=a, recs=recs,
        units='ATF temp raw (x = 255 − sensor voltage raw, 19.6 mV/count)', cat='Sensors', conf='CONFIRMED', rep='TCM 08 §5',
        note='Converts the filtered inverted sensor voltage (3FB792/793 = 255 − 3FB77B/77C) into the ATF temperature %s that every '
             'ATF-temp threshold in this calibration uses (cold 4→5 inhibit 0x606D6, P17xx debounce 0x4B0AD, lift-foot minimum 0x606E9, '
             'line-pressure ATF factor 0x60534). CONFIRMED live: 3FB77B 47 → 3FB792 207 → 3FB794 132 = this curve. %s So the "cold" '
             'thresholds near 45-55 raw are well below 0 °C. Note: the K-line id reads about 18 lower than 3FB794 at the same voltage '
             '(conversion not found); use the RAM value with this curve.' % (out, fsm),
        xtop=0xFF, sample=[(x, ev(recs, x, 0xFF)) for x in (143, 163, 188, 208, 224)])

# ---------------- torque reduction ----------------
for sh in range(14):
    rp = u32(0x6906C + 4 * sh)
    tp = u32(0x69AC8 + 4 * sh)
    rpm = [u16(rp + 2 * i) for i in range(16)]
    rows = []
    a = tp
    for k in range(16):
        key = s16(a)
        rows.append((a, key, list(rom[a + 2:a + 18])))
        if key >= 0x7000:
            break
        a += 18
    add(kind='tqcut', name='Shift torque cut %s (index %d)' % (SHIFT_NAMES[sh], sh), addr=tp, rpm_addr=rp, rpm=rpm, rows=rows,
        cat='Torque reduction', conf='CONFIRMED' if sh < 2 else 'STRONG', rep='TCM 03 §6, TCM 04 §1',
        note='Cut sent to the ECM in CAN 0x253 byte 3 = value/256 of engine torque, during the inertia phase. Rows: engine torque '
             '(0x23E raw, ~0.125 N·m/bit CANDIDATE), first row with key ≥ torque; columns: first rpm breakpoint ≥ rpm. '
             'Enabled per shift by 0x68E8E. Alternate set 0x6A2BC when 3FB187 bit 2. Shift index from table 0x4B1E0 [CONFIRMED].')

# ---------------- shift quality (TCM 04) ----------------
TB = [u16(0x608EE + 2 * i) for i in range(8)]
add(kind='curve', name='Shift-phase torque-band edges', addr=0x608EE, storage='uint16', n=8, axis=['band %d ≤' % (i + 1) for i in range(8)],
    units='turbine torque 3FB4FA', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='CONFIRMED', rep='TCM 04 §2',
    note='Column selector for the phase-timer banks: first edge ≥ turbine torque (engine torque × converter ratio, 3FB4FA). 32767 = open end.',
    raw=TB)
PH_X = ['progress threshold'] + ['T ≤ %d' % t if t < 32767 else 'T > %d' % TB[-2] for t in TB]
for base, side, alt in ((0x608FE, 'A', 'normal'), (0x60CEE, 'A', 'continuous-shift (3FB187 b2)'),
                        (0x610DE, 'B', 'normal'), (0x614CE, 'B', 'continuous-shift (3FB187 b2)')):
    for sh in range(14):
        a = base + sh * 4 * 0x12
        raw = [u16(a + 2 * i) for i in range(36)]
        add(kind='grid', name='Shift phase timers %s %s, %s' % (side, SHIFT_NAMES[sh], alt), addr=a, storage='uint16', nx=9, ny=4,
            xaxis=PH_X, yaxis=['phase 1 (0x10)', 'phase 2 (0x20)', 'phase 3 (0x30)', 'phase 4 (0x40)'],
            units='20 ms ticks (col 0: speed-ratio progress 3FB2FC)', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG',
            rep='TCM 04 §2',
            note='Sequencer %s (%s, FUN_%s): each phase lasts the tick count of the turbine-torque column, or ends early once shift progress '
                 '3FB2FC passes column 0 (upshift: progress > col 0; downshift: < col 0). Phase 1 adds the learned offset 3FB3D2; phase 2 of an '
                 'upshift adds 3FB54A and is at least 0x6883E[shift]. A/B = the two element sequencers. On upshifts A (3FB502) is the engaging-element apply command: it starts at the initial-apply table and climbs by 3FB3D4 per step while B holds 10000, then jumps to 10000 when the shift completes; on coast downshifts B ramps while A holds (CONFIRMED live 2026-11-19, TCM 06). 1 tick = 20 ms: the sequencers run in the 20 ms task T44 (schedule table 0x10C00, CONFIRMED; live ramp steps every ~20-25 ms, TCM 06 §1).' % (side, '3FB7DA' if side == 'A' else '3FB7D9', '3FCA4' if side == 'A' else '401A8'),
            raw=raw)
for base, side in ((0x618BE, 'A'), (0x619BE, 'B')):
    for sh in range(4):
        a = base + sh * 0x40
        add(kind='grid', name='Shift phase timers %s %s, lift-foot upshift' % (side, SHIFT_NAMES[sh]), addr=a, storage='uint16', nx=8, ny=4,
            xaxis=PH_X[1:], yaxis=['phase 1', 'phase 2', 'phase 3', 'phase 4'], units='20 ms ticks', expr='x', to_byte='x', fmt='0',
            cat='Shift quality', conf='STRONG', rep='TCM 04 §2',
            note='Used while 3FB17B b0 = lift-foot upshift (pedal backed off as the upshift starts; TCM 05 §3). DISABLED in stock: the ATF gate 0x606E9 = 255 is never met, so these never run. Only the 4 upshifts listed.',
            raw=[u16(a + 2 * i) for i in range(32)])
add(kind='curve', name='Upshift phase-2 minimum time', addr=0x6883E, storage='uint16', n=4, axis=SHIFT_NAMES[:4], stride=4,
    units='20 ms ticks', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG', rep='TCM 04 §2',
    note='Floor on sequencer A phase 2 during upshifts (u16 every 4 bytes; only read when 3FB7E3 = 1, so 4 entries). Stock 0 = no floor.', raw=[u16(0x6883E + 4 * i) for i in range(4)])
add(kind='grid', name='Initial engaging-element pressure', addr=0x62854, storage='uint16', nx=4, ny=14,
    xaxis=['D/C', 'HLR/C', 'I/C', 'FR/B'], yaxis=SHIFT_NAMES, units='kPa', expr='x/10', to_byte='x*10', fmt='0',
    cat='Shift quality', conf='STRONG', rep='TCM 04 §3, TCM 05 §1',
    note='3FB502 start value = table[shift*4 + 3FB7F8] (FUN_41B50), skipped when 3FB7F8 = 0xFF. Columns = engaging element (CONFIRMED, TCM 05 §1: element tables 0x4B2E8/0x4B406/0x4B414 match the FSM clutch chart, and every nonzero stock cell sits in its shift\'s engaging-element column). Unit 0.1 kPa CANDIDATE.',
    raw=[u16(0x62854 + 2 * i) for i in range(56)])
add(kind='grid', name='Torque-cut extra apply ramp', addr=0x65628, storage='uint16', nx=4, ny=4,
    xaxis=['min cut ticks (3FB46A >)', 'max ticks since cut (3FB46C ≤)', 'gain K (/1024)', 'max step'], yaxis=SHIFT_NAMES[:4],
    units='raw', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='CONFIRMED', rep='TCM 06 §2',
    note='Extra apply-ramp step 3FB3DE added to 3FB502 every 20 ms with 3FB3D4 (FUN_25E9C/25E44): 3DE = min(K × 3FB510 / 1024, max step), '
         '3FB510 = (engine torque 3FB310 − 3FB30E) × converter ratio 3FB312 / 1024. Gated by the torque-reduction request 3FB872 (CAN 0x253 b3): '
         'active once the cut has lasted more than col 0 ticks (3FB46A) and until col 1 ticks after it ends (3FB46C). Stock K = 0 for all four '
         'upshifts, so 3DE = 0 (CONFIRMED live). A higher K firms up the apply while the engine torque is being cut.',
    raw=[u16(0x65628 + 2 * i) for i in range(16)])
# ---- TCM 05: apply-pressure end target, downshift start detection, mode enables ----
add(kind='grid', name='Upshift apply-pressure end target coefficients', addr=0x65648, storage='uint16', nx=5, ny=4,
    xaxis=['a (torque gain)', 'b (hold term)', 'c (start offset gain)', 'd (start offset hold)', 'floor'], yaxis=SHIFT_NAMES[:4],
    units='raw (a-d /1024)', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG', rep='TCM 05 §2',
    note='Engaging-element pressure end target 3FB504 = max(a·|T_turbine|/1024 · gain/1024 + b·hold/1024 + offset, floor) (FUN_261A8); offset = '
         'captured pressure − (c·|T| + d·hold)/1024 so the target starts at the current pressure. a = the main firmness-vs-torque knob. '
         'Pedal released → floor only. Stock b = d = 0. Same pressure unit as the apply ramp (10000 = full).',
    raw=[u16(0x65648 + 2 * i) for i in range(20)])
add(kind='grid', name='Downshift apply-pressure end target coefficients', addr=0x65670, storage='uint16', nx=3, ny=10,
    xaxis=['a (torque gain)', 'b (base term)', 'floor'], yaxis=SHIFT_NAMES[4:], units='raw (a, b /1024)', expr='x', to_byte='x', fmt='0',
    cat='Shift quality', conf='STRONG', rep='TCM 05 §2',
    note='3FB508 = max(a·|T_turbine|/1024 + b·3FB430/1024, floor) (FUN_2624C); 3FB430 = 0x64E40 or the released element\'s initial-apply cell. Stock b = 0.',
    raw=[u16(0x65670 + 2 * i) for i in range(30)])
for a, nm in ((0x65784, 'Downshift start detection A (3FB17F b6)'), (0x657AC, 'Downshift start detection B (3FB187 b5)'),
              (0x657D4, 'Downshift start detection C (3FB187 b5, other branch)')):
    add(kind='grid', name=nm, addr=a, storage='uint16', nx=2, ny=10, xaxis=['ratio threshold (x1024)', 'tick limit'], yaxis=SHIFT_NAMES[4:],
        units='raw', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG', rep='TCM 05 §4',
        note='Flag sets when the measured ratio 3FB2FC (turbine/output x1024) passes the threshold or the shift timer 3FB4A0 reaches the tick '
             'limit (20 ms ticks). Stock thresholds = from-gear ratio x1024 + 1-2 % (2339/1528/1044/874), i.e. "the ratio has left the old gear".',
        raw=[u16(a + 2 * i) for i in range(20)])
for a, nm, note in (
        (0x6077D, 'Continuous-shift timing enable', 'b0 = 1 (stock): a same-direction request during a shift sets 3FB187 b2 and switches to the continuous-shift phase-timer/ramp banks. b1: only in patterns 4/7.'),
        (0x606E7, 'Lift-foot upshift: pedal look-back samples', 'Pedal is compared with its value this many samples ago (max 10). Stock 0.'),
        (0x606E8, 'Lift-foot upshift: detection window', 'Cycles after arming in which a lift-off counts. Stock 0.'),
        (0x606E9, 'Lift-foot upshift: minimum ATF temp', 'ATF raw gate. Stock 255 = never met = feature DISABLED.'),
        (0x606EA, 'Lift-foot upshift: pedal-was-high level', 'accel pedal 3FB992 raw. Stock 0.'),
        (0x606EB, 'Lift-foot upshift: pedal-now-low level', 'accel pedal 3FB992 raw. Stock 0.'),
        (0x6036C, 'Fallback phase-timer set enable', 'b0 = 1 (stock): allows 3FB2BF b1 (fallback banks 0x492BC/0x496AC) below 0x6036D km/h when CAN 0x2A5 b3 bits 0-1 = 11 [meaning CANDIDATE].'),
        (0x6036D, 'Fallback phase-timer set speed limit', 'km/h (stock 5).')):
    add(kind='scalar', name=nm, addr=a, storage='uint8', units='raw', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG',
        rep='TCM 05 §3', note=note, raw=[rom[a]])
# apply-ramp steps: upshifts only; rows keyed by turbine torque, sub-rows by speed
for sh in range(4):
    p = u32(0x629D4 + 4 * sh)
    a = p
    for k in range(16):
        key = s16(a); sub = u32(a + 4); b = sub
        for j in range(8):
            sp = rom[b]; v = u16(b + 2)
            add(kind='scalar', name='Apply ramp steps %s, T ≤ %s, speed ≤ %s' % (SHIFT_NAMES[sh], key if key < 32767 else 'max', sp if sp < 255 else 'max'),
                addr=b + 2, storage='uint16', units='20 ms ticks', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG', rep='TCM 04 §3',
                note='Number of ticks the engaging-element pressure takes to ramp from its start to the target (3FB3E0 = (target − start) / steps, '
                     'FUN_41B88/41C28). Fewer steps = steeper ramp = firmer, shorter shift. One step per 20 ms (task T44). The adaptive cell would scale the ramp, but the stock clamp holds it at 256 (TCM 06 §3). '
                     'Table 0x629D4 (alt 0x62A38 when 3FB187 b2 = continuous same-direction shift, TCM 05 §3). Speed = processed vehicle speed 3FB797, km/h.', raw=[v])
            if sp == 0xFF:
                break
            b += 4
        if key >= 0x7FFF:
            break
        a += 8
for sh in range(4):
    p = u32(0x6890C + 4 * sh); recs = []
    a = p
    for k in range(16):
        key = u16(a); recs.append((key, rom[a + 2]))
        if key >= 0x7FFF:
            break
        a += 4
    add(kind='steps', name='Shift-time target %s' % SHIFT_NAMES[sh], addr=p, recs=recs, cat='Shift quality', conf='STRONG', rep='TCM 03 §8',
        note='Adaptive learning compares the measured shift time 3FB67A (20 ms ticks, task T44) with this (4-byte records {turbine torque ≤ u16, target ticks u8, pad}): '
             'cell × measured / (target ∓ deadband 0x6864C), FUN_2F540. In stock the learned cell is clamped to exactly 256 before use '
             '(see "Adaptive cell clamp"), so the learning has no effect on shifts.')
for sh in range(4):
    p = u32(0x668AC + 4 * sh); n = 0
    while True:
        n += 1
        if u16(p + 6 * (n - 1)) >= 0x7FFF: break
    add(kind='grid', name='Adaptive cell clamp %s' % SHIFT_NAMES[sh], addr=p, storage='uint16', nx=3, ny=n,
        xaxis=['turbine torque ≤', 'max (×256)', 'min (×256)'], yaxis=['row %d' % i for i in range(n)], units='raw (256 = 1.0)', expr='x', to_byte='x', fmt='0',
        cat='Shift quality', conf='CONFIRMED', rep='TCM 06 §3',
        note='Apply ramp used = base ramp 3FB3E0 × clamp(learned cell, min, max) / 256 (FUN_41CCC). Stock min = max = 256 for every shift and '
             'torque band, so the learned cells are ignored (CONFIRMED live: 3FB3D4 = 3FB3E0 in every logged upshift). Widening the range '
             'turns shift-time adaptation on.',
        raw=[u16(p + 2 * i) for i in range(3 * n)])
add(kind='scalar', name='Adaptive learning deadband', addr=0x6864C, storage='uint8', units='20 ms ticks', expr='x', to_byte='x', fmt='0',
    cat='Shift quality', conf='CONFIRMED', rep='TCM 06 §3', note='No cell update while |measured − target| ≤ this (FUN_2F540).', raw=[rom[0x6864C]])
add(kind='curve', name='Learning torque-band edges', addr=0x68670, storage='uint16', n=9, axis=['band %d' % i for i in range(9)],
    units='turbine torque', expr='x', to_byte='x', fmt='0', cat='Shift quality', conf='STRONG', rep='TCM 03 §8',
    note='Band edges of the learned cells 3FBA8A[4 upshifts × 9]. The learned cells themselves are RAM/NV: do not write them.',
    raw=[u16(0x68670 + 2 * i) for i in range(9)])

# ---------------- writers ----------------
def xml():
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!-- Infiniti FX45 RE5R05A TCM (ROM id CG401 / RX0612, MPC555, 448 kB) definition v3 (2026-11-19), research grade.',
         '     Generated by docs/tcm_decode/scripts/gen_tcm_defs.py from code analysis + logged and live RAM data (TCM reports 01-06).',
         '     NOT flash-tested. Calibration CRC-16/XMODEM at 0x6FFFC over 0x60090-0x6FFFB must be recomputed by your tool.',
         '     Segment curves are exposed as raw {x0, y0, slope} records; y = y0 + slope*(x-x0)/16 between breakpoints. -->',
         '<roms>', '<rom>', ' <romid>', '  <xmlid>CG401</xmlid>', '  <internalidaddress>6FA61</internalidaddress>',
         '  <internalidstring>CG401</internalidstring>', '  <make>Infiniti</make>', '  <market>USDM</market>', '  <model>FX45</model>',
         '  <submodel>RE5R05A TCM</submodel>', '  <transmission>RE5R05A</transmission>', '  <year>2004</year>', '  <memmodel>MPC555</memmodel>',
         '  <filesize>448kb</filesize>', '  <obsolete>0</obsolete>', ' </romid>']

    def desc(it):
        return ' <description>%s</description>' % escape('[%s, %s] %s' % (it['conf'], it['rep'], it['note']))

    def scaling(nm, units, expr, tob, fmt):
        return '  <scaling name="%s" units="%s" expression="%s" to_byte="%s" format="%s" fineincrement="1" coarseincrement="10" />' % (
            escape(nm), escape(units), expr, tob, fmt)

    for it in ITEMS:
        n = escape(it['name'])
        if it['kind'] == 'scalar':
            L.append(' <table type="1D" name="%s" category="%s" storagetype="%s" endian="big" storageaddress="0x%X">' % (n, it['cat'], it['storage'], it['addr']))
            L.append(scaling(it['name'], it['units'], it['expr'], it['to_byte'], it['fmt']))
            L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'curve' and it.get('stride'):
            for k, lab in enumerate(it['axis']):
                rn = '%s, %s' % (it['name'], lab)
                L.append(' <table type="1D" name="%s" category="%s" storagetype="%s" endian="big" storageaddress="0x%X">' % (escape(rn), it['cat'], it['storage'], it['addr'] + it['stride'] * k))
                L.append(scaling(rn, it['units'], it['expr'], it['to_byte'], it['fmt'])); L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'curve':
            L.append(' <table type="2D" name="%s" category="%s" storagetype="%s" endian="big" sizey="%d" storageaddress="0x%X">' % (n, it['cat'], it['storage'], it['n'], it['addr']))
            L.append(scaling(it['name'], it['units'], it['expr'], it['to_byte'], it['fmt']))
            L.append('  <table type="Static Y Axis" name="item" sizey="%d">' % it['n'] + ''.join('<data>%s</data>' % escape(x) for x in it['axis']) + '</table>')
            L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'map':
            L.append(' <table type="3D" name="%s" category="%s" storagetype="%s" endian="big" sizex="%d" sizey="%d" storageaddress="0x%X">' % (n, it['cat'], it['storage'], it['nx'], it['ny'], it['addr']))
            L.append(scaling(it['name'], it['units'], it['expr'], it['to_byte'], it['fmt']))
            L.append('  <table type="Static X Axis" name="pedal" sizex="%d">' % it['nx'] + ''.join('<data>%s</data>' % escape(x) for x in it['xaxis']) + '</table>')
            L.append('  <table type="Static Y Axis" name="speed" sizey="%d">' % it['ny'] + ''.join('<data>%s</data>' % escape(x) for x in it['yaxis']) + '</table>')
            L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'grid':
            L.append(' <table type="3D" name="%s" category="%s" storagetype="%s" endian="big" sizex="%d" sizey="%d" storageaddress="0x%X">' % (n, it['cat'], it['storage'], it['nx'], it['ny'], it['addr']))
            L.append(scaling(it['name'], it['units'], it['expr'], it['to_byte'], it['fmt']))
            L.append('  <table type="Static X Axis" name="column" sizex="%d">' % it['nx'] + ''.join('<data>%s</data>' % escape(x) for x in it['xaxis']) + '</table>')
            L.append('  <table type="Static Y Axis" name="row" sizey="%d">' % it['ny'] + ''.join('<data>%s</data>' % escape(x) for x in it['yaxis']) + '</table>')
            L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'steps':
            for k, (key, v) in enumerate(it['recs']):
                rn = '%s, T ≤ %s' % (it['name'], key if key < 0x7FFF else 'max')
                L.append(' <table type="1D" name="%s" category="%s" storagetype="uint8" endian="big" storageaddress="0x%X">' % (escape(rn), it['cat'], it['addr'] + 4 * k + 2))
                L.append(scaling(rn, 'ticks', 'x', 'x', '0')); L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'seg' and it['fmt'] in ('seg8', 'seg16'):
            st = 'uint8' if it['fmt'] == 'seg8' else 'uint16'
            m = len(it['recs']) * 3
            L.append(' <table type="2D" name="%s" category="%s" storagetype="%s" endian="big" sizey="%d" storageaddress="0x%X">' % (n, it['cat'], st, m, it['addr']))
            L.append(scaling(it['name'], 'raw', 'x', 'x', '0'))
            lab = []
            for k in range(len(it['recs'])):
                lab += ['r%d x0' % k, 'r%d y0' % k, 'r%d slope' % k]
            L.append('  <table type="Static Y Axis" name="record field" sizey="%d">' % m + ''.join('<data>%s</data>' % x for x in lab) + '</table>')
            L.append(desc(it)); L.append(' </table>')
        elif it['kind'] == 'tqcut':
            for (a, key, vals) in it['rows']:
                rn = '%s, torque ≤ %d' % (it['name'], key)
                L.append(' <table type="2D" name="%s" category="%s" storagetype="uint8" endian="big" sizey="16" storageaddress="0x%X">' % (escape(rn), it['cat'], a + 2))
                L.append(scaling(rn, '% cut', 'x*100/256', 'x*256/100', '0'))
                L.append('  <table type="Static Y Axis" name="rpm ≤" sizey="16">' + ''.join('<data>%d</data>' % r for r in it['rpm']) + '</table>')
                L.append(desc(it)); L.append(' </table>')
    L += ['</rom>', '</roms>']
    open(os.path.join(OUT, 'CG401_tcm_romraider.xml'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')


def js():
    out = []
    for it in ITEMS:
        d = {k: v for k, v in it.items() if k not in ('sample',)}
        d['addr'] = '0x%05X' % it['addr']
        if 'rpm_addr' in d:
            d['rpm_addr'] = '0x%05X' % d['rpm_addr']
            d['rows'] = [{'addr': '0x%05X' % a, 'torque_key': k, 'cut_256': v} for a, k, v in it['rows']]
        out.append(d)
    json.dump(out, open(os.path.join(OUT, 'CG401_tcm.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def md():
    L = ['# CG401 TCM definition (RE5R05A, FX45), research grade', '',
         'Generated by `scripts/gen_tcm_defs.py`. %d items. Every item names its confidence and backing report. **Not flash-tested.**' % len(ITEMS),
         'Any edit needs the calibration CRC-16/XMODEM at **0x6FFFC** (over 0x60090-0x6FFFB) recomputed. Flashing method undecided.', '',
         'Segment curves: `{x0, y0, slope}` records, y = y0 + slope·(x − x0)/16 between breakpoints (formats in the script header).', '']
    cat = None
    for it in sorted(ITEMS, key=lambda i: (i['cat'], i['addr'])):
        if it['cat'] != cat:
            cat = it['cat']; L += ['## %s' % cat, '']
        L.append('### `0x%05X` %s' % (it['addr'], it['name']))
        L.append('*%s · %s.* %s' % (it['conf'], it['rep'], it['note']))
        if it['kind'] in ('scalar', 'curve'):
            vals = it['raw']
            sc = (lambda x: eval(it['expr'], {'x': x}))
            if it['kind'] == 'curve':
                L.append('')
                L.append('| ' + ' | '.join(it['axis']) + ' |'); L.append('|' + '---|' * len(it['axis']))
                L.append('| ' + ' | '.join(('%.3f' % sc(v)).rstrip('0').rstrip('.') for v in vals) + ' |')
            else:
                L.append('Value: **%s** %s (raw %d / 0x%X).' % (('%.3f' % sc(vals[0])).rstrip('0').rstrip('.'), it['units'], vals[0], vals[0]))
        elif it['kind'] == 'grid':
            sc = (lambda x: eval(it['expr'], {'x': x}))
            L += ['', '| | ' + ' | '.join(it['xaxis']) + ' |', '|---|' + '---|' * it['nx']]
            for r_ in range(it['ny']):
                L.append('| %s | ' % it['yaxis'][r_] + ' | '.join(('%.1f' % sc(v)).rstrip('0').rstrip('.') for v in it['raw'][r_ * it['nx']:(r_ + 1) * it['nx']]) + ' |')
        elif it['kind'] == 'steps':
            L += ['', '| turbine torque ≤ | ' + ' | '.join(str(k) if k < 0x7FFF else 'max' for k, _ in it['recs']) + ' |', '|---|' + '---|' * len(it['recs']),
                  '| target ticks | ' + ' | '.join(str(v) for _, v in it['recs']) + ' |']
        elif it['kind'] == 'map':
            L += ['', '| speed \\ pedal | ' + ' | '.join(it['xaxis']) + ' |', '|---|' + '---|' * it['nx']]
            for r in range(it['ny']):
                L.append('| %s | ' % it['yaxis'][r] + ' | '.join(str(v) for v in it['raw'][r * 4:r * 4 + 4]) + ' |')
        elif it['kind'] == 'seg':
            L.append('')
            L.append('Records: ' + ' '.join('(%d, %d, %d)' % r for r in it['recs']) + ' · end marker 0x%X' % (0xFF if it['fmt'] != 'seg16' else 0xFFFF))
            if it['sample']:
                L.append('')
                L.append('| x | ' + ' | '.join(str(x) for x, _ in it['sample']) + ' |'); L.append('|' + '---|' * (len(it['sample']) + 1))
                L.append('| y | ' + ' | '.join(str(y) for _, y in it['sample']) + ' |')
        elif it['kind'] == 'tqcut':
            L += ['', 'rpm breakpoints @0x%05X; values = cut/256.' % it['rpm_addr'], '',
                  '| torque ≤ \\ rpm ≤ | ' + ' | '.join(str(r) for r in it['rpm']) + ' |', '|---|' + '---|' * 16]
            for a, key, vals in it['rows']:
                L.append('| %s | ' % ('max' if key >= 0x7000 else key) + ' | '.join(str(v) for v in vals) + ' |')
        L.append('')
    open(os.path.join(OUT, 'CG401_tcm.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')


def csv_out():
    import csv
    with open(os.path.join(OUT, 'CG401_tcm_tables.csv'), 'w', encoding='utf-8', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['address', 'name', 'category', 'kind', 'storage', 'size', 'x_axis', 'y_axis', 'units', 'raw_to_units', 'units_to_raw',
                     'confidence', 'source', 'note'])
        for it in sorted(ITEMS, key=lambda i: i['addr']):
            k = it['kind']
            if k == 'curve': size, xa, ya = '%d' % it['n'], ' | '.join(it['axis']), ''
            elif k in ('grid', 'map'): size, xa, ya = '%dx%d' % (it['nx'], it['ny']), ' | '.join(map(str, it['xaxis'])), ' | '.join(map(str, it['yaxis']))
            elif k == 'seg': size, xa, ya = '%d records {x0,y0,slope} %s' % (len(it['recs']), it['fmt']), 'x = see units', ''
            elif k == 'steps': size, xa, ya = '%d records {torque<=u16, ticks u8, pad}' % len(it['recs']), 'turbine torque', ''
            elif k == 'tqcut': size, xa, ya = '%d rows x 16' % len(it['rows']), 'rpm breakpoints @0x%05X' % it['rpm_addr'], 'torque key per row'
            else: size, xa, ya = '1', '', ''
            wr.writerow(['0x%05X' % it['addr'], it['name'], it['cat'], k, it.get('storage', it.get('fmt', '')), size, xa, ya, it.get('units', ''),
                         it.get('expr', ''), it.get('to_byte', ''), it['conf'], it['rep'], it.get('note', '')])


def xdf():
    """TunerPro XDF (big-endian, base offset 0, the same tables as the RomRaider XML; seg8x16 curves and notes are left out there too)."""
    from xml.sax.saxutils import escape as esc
    cats = sorted(set(i['cat'] for i in ITEMS if i['kind'] != 'note'))
    cix = {c: k + 1 for k, c in enumerate(cats)}
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<!-- Written by docs/tcm_decode/scripts/gen_tcm_defs.py (definition v3, research grade, NOT flash-tested). -->',
         '<XDFFORMAT version="1.60">', '<XDFHEADER>', '  <flags>0x1</flags>', '  <fileversion>3</fileversion>',
         '  <deftitle>Infiniti FX45 RE5R05A TCM CG401 (MPC555) v3</deftitle>',
         '  <description>%s</description>' % esc('Research-grade definition from code analysis + live data (reports 01-06). Calibration CRC-16/XMODEM at 0x6FFFC over '
                                                 '0x60090-0x6FFFB must be recomputed after any edit; TunerPro does not do it. Segment curves are raw {x0, y0, slope} '
                                                 'records: y = y0 + slope*(x-x0)/16.'),
         '  <author>FX45 owner (fx45bar project)</author>', '  <BASEOFFSET offset="0" subtract="0" />',
         '  <DEFAULTS datasizeinbits="8" sigdigits="2" outputtype="1" signed="0" lsbfirst="0" float="0" />',
         '  <REGION type="0xFFFFFFFF" startaddress="0x0" size="0x70000" regionflags="0x0" name="Binary File" desc="448 kB MPC555 image" />']
    for c in cats: L.append('  <CATEGORY index="0x%X" name="%s" />' % (cix[c] - 1, esc(c)))
    L.append('</XDFHEADER>')
    uid = [0x1000]
    def nid():
        uid[0] += 1; return '0x%X' % uid[0]
    def bits(st): return 16 if st in ('uint16', 'int16') else 8
    def flags(st): return '0x1' if st.startswith('int') else '0x0'
    def math(expr): return '<MATH equation="%s"><VAR id="X" /></MATH>' % (expr or 'x').replace('x', 'X')
    def dec(fmt): return str(len(fmt.split('.')[1])) if '.' in (fmt or '') else '0'
    def desc(it): return '<description>%s</description>' % esc('[%s, %s] %s' % (it['conf'], it['rep'], it['note']))
    def const(name, it, addr, st, units, expr, fmt):
        L.extend(['<XDFCONSTANT uniqueid="%s" flags="0x0">' % nid(), '  <title>%s</title>' % esc(name), '  ' + desc(it),
                  '  <CATEGORYMEM index="0" category="%d" />' % cix[it['cat']],
                  '  <EMBEDDEDDATA mmedtypeflags="%s" mmedaddress="0x%X" mmedelementsizebits="%d" mmedmajorstridebits="0" mmedminorstridebits="0" />' % (flags(st), addr, bits(st)),
                  '  <units>%s</units>' % esc(units), '  <decimalpl>%s</decimalpl>' % dec(fmt), '  <datatype>0</datatype>', '  <unittype>0</unittype>',
                  '  <DALINK index="0" />', '  ' + math(expr), '</XDFCONSTANT>'])
    def axis(id_, labels):
        out = ['  <XDFAXIS id="%s" uniqueid="0x0">' % id_, '    <EMBEDDEDDATA mmedelementsizebits="16" mmedmajorstridebits="-32" mmedminorstridebits="0" />',
               '    <indexcount>%d</indexcount>' % len(labels), '    <datatype>0</datatype>', '    <unittype>0</unittype>', '    <DALINK index="0" />']
        out += ['    <LABEL index="%d" value="%s" />' % (k, esc(str(v))) for k, v in enumerate(labels)]
        out += ['    <MATH equation="X"><VAR id="X" /></MATH>', '  </XDFAXIS>']
        return out
    def table(name, it, addr, st, rows, cols, xl, yl, units, expr, fmt):
        L.extend(['<XDFTABLE uniqueid="%s" flags="0x0">' % nid(), '  <title>%s</title>' % esc(name), '  ' + desc(it),
                  '  <CATEGORYMEM index="0" category="%d" />' % cix[it['cat']]])
        L.extend(axis('x', xl)); L.extend(axis('y', yl))
        L.extend(['  <XDFAXIS id="z">',
                  '    <EMBEDDEDDATA mmedtypeflags="%s" mmedaddress="0x%X" mmedelementsizebits="%d" mmedrowcount="%d" mmedcolcount="%d" mmedmajorstridebits="0" mmedminorstridebits="0" />'
                  % (flags(st), addr, bits(st), rows, cols),
                  '    <units>%s</units>' % esc(units), '    <decimalpl>%s</decimalpl>' % dec(fmt), '    <outputtype>1</outputtype>', '    <DALINK index="0" />',
                  '    ' + math(expr), '  </XDFAXIS>', '</XDFTABLE>'])
    for it in ITEMS:
        k = it['kind']
        if k == 'scalar':
            const(it['name'], it, it['addr'], it['storage'], it['units'], it['expr'], it['fmt'])
        elif k == 'curve' and it.get('stride'):
            for j, lab in enumerate(it['axis']):
                const('%s, %s' % (it['name'], lab), it, it['addr'] + it['stride'] * j, it['storage'], it['units'], it['expr'], it['fmt'])
        elif k == 'curve':
            table(it['name'], it, it['addr'], it['storage'], 1, it['n'], it['axis'], [''], it['units'], it['expr'], it['fmt'])
        elif k in ('map', 'grid'):
            table(it['name'], it, it['addr'], it['storage'], it['ny'], it['nx'], it['xaxis'], it['yaxis'], it['units'], it['expr'], it['fmt'])
        elif k == 'steps':
            for j, (key, v) in enumerate(it['recs']):
                const('%s, T <= %s' % (it['name'], key if key < 0x7FFF else 'max'), it, it['addr'] + 4 * j + 2, 'uint8', 'ticks', 'x', '0')
        elif k == 'seg' and it['fmt'] in ('seg8', 'seg16'):
            st = 'uint8' if it['fmt'] == 'seg8' else 'uint16'
            table(it['name'], it, it['addr'], st, len(it['recs']), 3, ['x0', 'y0', 'slope'], ['r%d' % j for j in range(len(it['recs']))], 'raw', 'x', '0')
        elif k == 'tqcut':
            for (a, key, vals) in it['rows']:
                table('%s, torque <= %d' % (it['name'], key), it, a + 2, 'uint8', 1, 16, [str(r) for r in it['rpm']], [''], '% cut', 'x*100/256', '0')
    L.append('</XDFFORMAT>')
    open(os.path.join(OUT, 'CG401_tcm.xdf'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')


xml(); js(); md(); csv_out(); xdf()
print(len(ITEMS), 'items;', sum(1 for i in ITEMS if i['kind'] == 'seg'), 'segment curves;', sum(1 for i in ITEMS if i['kind'] == 'tqcut'), 'torque-cut tables')
