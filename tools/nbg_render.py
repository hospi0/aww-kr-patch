# -*- coding: utf-8 -*-
"""세이브스테이트의 VDP2 NBG 플레인을 **그림으로** 렌더한다 (세션18).

왜 필요한가
  `screen_text.py` 는 셀 값을 `(ch-240)//4` 로 해석해 글리프 인덱스를 뽑는데,
  그 가정이 안 맞는 화면(개발·생산 = SAKUCG 모듈)에서는 잡음만 나온다.
  화면을 **실제 픽셀로** 그려 보면 어느 플레인의 어느 셀이 어떤 글자인지 확정된다.

사용: python tools/nbg_render.py <state> [out_dir]
출력: <out>/nbgN_planeX.png  +  같은 이름 .txt (셀별 char number)
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_analyze import rzip_decompress
from screen_text import sections, plane_addrs
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cram_pal(cram):
    """CRAM 4096B = RGB555 LE 2048색"""
    pal = []
    for i in range(len(cram) // 2):
        v = struct.unpack_from('<H', cram, i * 2)[0]
        pal.append(((v & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8))
    return pal


def render(v2, base, pal, palbase=0, cell=16):
    """플레인(64x64 셀) → 이미지. 셀 크기 16 = 8x8 타일 4개."""
    tiles = cell // 8
    im = Image.new('RGB', (64 * cell, 64 * cell), (0, 0, 0))
    px = im.load()
    chars = []
    for ry in range(64):
        row = []
        for rx in range(64):
            o = base + (ry * 64 + rx) * 2
            if o + 1 >= len(v2):
                row.append(0)
                continue
            w = struct.unpack_from('>H', v2, o)[0]
            ch = w & 0xFFF
            pn = (w >> 12) & 0xF
            row.append(ch)
            for t in range(tiles * tiles):
                addr = (ch + t) * 0x20
                if addr + 0x20 > len(v2):
                    continue
                tx, ty = t % tiles, t // tiles
                for y in range(8):
                    for x in range(8):
                        b = v2[addr + y * 4 + x // 2]
                        c = (b >> 4) if x % 2 == 0 else (b & 0xF)
                        px[rx * cell + tx * 8 + x, ry * cell + ty * 8 + y] = \
                            pal[(palbase + pn * 16 + c) % len(pal)]
        chars.append(row)
    return im, chars


def main():
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'work', 'nbg')
    os.makedirs(out, exist_ok=True)
    blob, _ = rzip_decompress(path)
    sec = sections(blob)
    ro, rs = sec['RawRegs'][0]
    regs = blob[ro:ro + rs]
    vo, vs = sec['VRAM'][1]
    v2 = blob[vo:vo + vs]
    co, cs = sec['CRAM'][0]
    pal = cram_pal(blob[co:co + cs])
    for n, (a, b) in enumerate(plane_addrs(regs)):
        for tag, base in (('A', a), ('B', b)):
            if tag == 'B' and b == a:
                continue
            im, chars = render(v2, base, pal)
            if not any(any(r) for r in chars):
                continue
            name = 'nbg%d_plane%s' % (n, tag)
            im.save(os.path.join(out, name + '.png'))
            with open(os.path.join(out, name + '.txt'), 'w', encoding='utf-8') as f:
                for ry, row in enumerate(chars):
                    if any(row):
                        f.write('%2d %s\n' % (ry, ' '.join('%4d' % c for c in row)))
            print('%s  base=0x%05x' % (name, base))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
