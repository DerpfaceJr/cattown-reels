#!/usr/bin/env python3
"""textw.py - measure one caption line with the real font file (no PIL needed).
usage: textw.py FONT.ttf SIZE_PX TEXT   -> prints "W H" in pixels (rounded up)
W = sum of hmtx advance widths * size / unitsPerEm. Kerning is ignored; kern pairs only tighten
    text, so W is >= the width drawtext draws (the logged box is never smaller than the real text).
H = (hhea ascender - descender) * size / unitsPerEm (full line height, >= drawn glyph height).
"""
import math, struct, sys


def u16(d, o):
    return struct.unpack('>H', d[o:o + 2])[0]


def i16(d, o):
    return struct.unpack('>h', d[o:o + 2])[0]


def tables(d):
    t = {}
    for i in range(u16(d, 4)):
        tag, _, off, _ln = struct.unpack('>4sIII', d[12 + 16 * i:28 + 16 * i])
        t[tag.decode('latin1')] = off
    return t


def cmap4(d, base):
    for i in range(u16(d, base + 2)):
        pid, eid, so = struct.unpack('>HHI', d[base + 4 + 8 * i:base + 12 + 8 * i])
        s = base + so
        if u16(d, s) != 4 or not (pid == 0 or (pid == 3 and eid in (1, 10))):
            continue
        segx2 = u16(d, s + 6)
        seg = segx2 // 2
        ends = struct.unpack(f'>{seg}H', d[s + 14:s + 14 + segx2])
        starts = struct.unpack(f'>{seg}H', d[s + 16 + segx2:s + 16 + 2 * segx2])
        deltas = struct.unpack(f'>{seg}h', d[s + 16 + 2 * segx2:s + 16 + 3 * segx2])
        rpos = s + 16 + 3 * segx2
        roffs = struct.unpack(f'>{seg}H', d[rpos:rpos + segx2])

        def gid(c):
            for k in range(seg):
                if c <= ends[k]:
                    if c < starts[k]:
                        return 0
                    if roffs[k] == 0:
                        return (c + deltas[k]) & 0xFFFF
                    a = rpos + 2 * k + roffs[k] + 2 * (c - starts[k])
                    g = u16(d, a)
                    return (g + deltas[k]) & 0xFFFF if g else 0
            return 0
        return gid
    sys.exit('TEXTW_FAIL no cmap format 4 subtable')


def main():
    font, size, text = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    d = open(font, 'rb').read()
    t = tables(d)
    upem = u16(d, t['head'] + 18)
    asc, desc = i16(d, t['hhea'] + 4), i16(d, t['hhea'] + 6)
    nhm = u16(d, t['hhea'] + 34)
    hm = t['hmtx']
    gid = cmap4(d, t['cmap'])
    adv = 0
    for ch in text:
        g = gid(ord(ch))
        adv += u16(d, hm + 4 * min(g, nhm - 1))
    w = math.ceil(adv * size / upem)
    h = math.ceil((asc - desc) * size / upem)
    print(f'{w} {h}')


if __name__ == '__main__':
    main()
