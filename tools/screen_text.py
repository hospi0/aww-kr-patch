# -*- coding: utf-8 -*-
"""세이브스테이트의 VDP2 NBG 플레인 → 「화면에 실제로 찍힌 글리프 인덱스」 복원.

nbg_text.py 의 확장판. 차이점:
  · ASC16CG(charmap.CHARS) 를 기본 폰트로 쓴다 — fontmaps.json 에 없는 폰트다.
  · 셀 값을 **원본 문자 / 현재 한글** 두 벌로 같이 보여준다.
    ⇒ 깨진 한글이 보이는 자리의 **원본 일본어**를 바로 읽을 수 있다.

사용: python tools/screen_text.py <state> [--raw]
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap
from state_analyze import rzip_decompress

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sections(blob):
    out = {}
    i, n = 0, len(blob)
    while i < n - 8:
        L = blob[i]
        if 2 <= L <= 16:
            nm = blob[i + 1:i + 1 + L]
            if all(32 <= c < 127 for c in nm):
                sz = struct.unpack_from('<I', blob, i + 1 + L)[0]
                if 64 <= sz <= 2 * 1024 * 1024 and i + 1 + L + 4 + sz <= n:
                    out.setdefault(nm.decode(), []).append((i + 1 + L + 4, sz))
                    i = i + 1 + L + 4 + sz
                    continue
        i += 1
    return out


def plane_addrs(regs):
    mpofn = struct.unpack_from('<H', regs, 0x3C)[0]
    out = []
    for n in range(4):
        mpab = struct.unpack_from('<H', regs, 0x40 + n * 4)[0]
        hi = (mpofn >> (n * 4)) & 7
        a = (((hi << 6) | (mpab & 0x3F)) * 0x2000) & 0x7FFFF
        b = (((hi << 6) | ((mpab >> 8) & 0x3F)) * 0x2000) & 0x7FFFF
        out.append((a, b))
    return out


def hangul_map():
    """슬롯 -> 지금 그 자리에 그려진 한글"""
    m = {}
    for fn in ('asc16_slots.json', 'shared_unit_slots.json'):
        p = os.path.join(ROOT, 'work', fn)
        if os.path.exists(p):
            for syl, idx in json.load(open(p, encoding='utf-8')).items():
                m.setdefault(int(idx), syl)
    return m


def main():
    path = sys.argv[1]
    blob, _ = rzip_decompress(path)
    sec = sections(blob)
    ro, rs = sec['RawRegs'][0]
    regs = blob[ro:ro + rs]
    vo, vs = sec['VRAM'][1]          # VDP2 VRAM
    v2 = blob[vo:vo + vs]
    HG = hangul_map()

    def cell(o):
        if o + 1 >= len(v2):
            return None
        ch = struct.unpack_from('>H', v2, o)[0] & 0xFFF
        if ch >= 240 and (ch - 240) % 4 == 0:
            return (ch - 240) // 4
        return None

    for n, (a, b) in enumerate(plane_addrs(regs)):
        for tag, base in (('A', a), ('B', b)):
            if tag == 'B' and b == a:
                continue
            rows = []
            for ry in range(64):
                jp, kr, idxs = [], [], []
                for rx in range(64):
                    g = cell(base + (ry * 64 + rx) * 2)
                    if g is None:
                        jp.append(' '); kr.append(' '); idxs.append(None)
                    else:
                        jp.append(charmap.CHARS.get(g, '〈%d〉' % g))
                        kr.append(HG.get(g, charmap.CHARS.get(g, '?')))
                        idxs.append(g)
                sj, sk = ''.join(jp).rstrip(), ''.join(kr).rstrip()
                if sj.strip():
                    rows.append((ry, sj, sk, idxs))
            if rows:
                print('── NBG%d plane%s @0x%05x' % (n, tag, base))
                for ry, sj, sk, idxs in rows:
                    print('  %2d| 화면:%s' % (ry, sk))
                    print('    | 원본:%s' % sj)
                    if '--raw' in sys.argv:
                        print('    | idx :%s' % [i for i in idxs if i is not None])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
