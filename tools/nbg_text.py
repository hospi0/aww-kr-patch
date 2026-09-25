# -*- coding: utf-8 -*-
"""세션13 — 스테이트의 VDP2 NBG 플레인을 디코드해 **화면에 실제로 뜬 텍스트**를 복원한다.

세션12 레시피(project 메모리)를 도구로 굳힌 것:
  RawRegs(512B LE) → MPOFN(0x3C)·MPABN0~3(0x40/44/48/4C) → 플레인주소
  = ((MPOFN 3비트<<6) | MPABN 6비트) * 0x2000  (VRAM 512KB로 마스크)
  패턴네임 1워드: ch = w & 0xFFF,  16×16 폰트 = (ch-240)//4,  소형 8×8 = ch(<240)
사용: python tools/nbg_text.py .state1 [폰트명]
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vdp1_dump import load, STDIR, BASE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else '.state1'
    fontname = sys.argv[2] if len(sys.argv) > 2 else 'ASCGSCG'
    path = key if os.path.exists(key) else os.path.join(STDIR, BASE + key)
    S = load(path)
    # RawRegs 는 load()가 안 담으므로 여기서 다시 파싱
    from vdp1_dump import sections
    from state_analyze import rzip_decompress
    blob, _ = rzip_decompress(path)
    sec = sections(blob)
    ro, rs = sec['RawRegs'][0]
    regs = blob[ro:ro + rs]
    v2 = S['vdp2']
    fwd = {int(k): v for k, v in
           json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'),
                          encoding='utf-8'))[fontname].items()}
    bgon = struct.unpack_from('<H', regs, 0x20)[0]
    print('BGON=%04x  (%s 기준 디코드)' % (bgon, fontname))
    for n, (a, b) in enumerate(plane_addrs(regs)):
        for tag, base in (('A', a), ('B', b)):
            if tag == 'B' and b == a:
                continue
            rows = []
            for ry in range(64):
                line = []
                for rx in range(64):
                    o = base + (ry * 64 + rx) * 2
                    if o + 1 >= len(v2):
                        line.append(' ')
                        continue
                    ch = struct.unpack_from('>H', v2, o)[0] & 0xFFF
                    if ch >= 240 and (ch - 240) % 4 == 0:
                        line.append(fwd.get((ch - 240) // 4, '·'))
                    elif ch == 0:
                        line.append(' ')
                    else:
                        line.append('¤')            # 소형폰트/기타
                s = ''.join(line).rstrip()
                if s.strip(' ·¤'):
                    rows.append((ry, s))
            if rows:
                print('── NBG%d plane%s @0x%05x' % (n, tag, base))
                for ry, s in rows[:40]:
                    print('   %2d| %s' % (ry, s))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
