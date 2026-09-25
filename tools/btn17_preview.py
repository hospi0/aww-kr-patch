# -*- coding: utf-8 -*-
"""버튼 17종 한글 렌더 미리보기 (세션17). ISO 는 건드리지 않는다.

사용: python tools/btn17_preview.py <승리화면 스테이트>
      (팔레트를 스테이트 CRAM 에서 읽는다)
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from btn17_data import BUTTONS, COLOR_BANK
from btn17_render import get_tex, draw, glyph_bbox
from state_analyze import rzip_decompress
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'btn17')


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


def palette(state, base):
    blob, _ = rzip_decompress(state)
    sec = sections(blob)
    off, size = sec['CRAM'][0]
    # ★스테이트 섹션은 **swap16 저장**이다(VDP1 VRAM·WorkRAM 과 동일). 안 풀면 색이 엉망이 된다.
    from state_analyze import swap16
    d = swap16(blob[off:off + size])
    cols = []
    for i in range(256):
        w = struct.unpack_from('>H', d, ((base + i) % (size // 2)) * 2)[0]
        cols.append((((w) & 0x1F) << 3, ((w >> 5) & 0x1F) << 3, ((w >> 10) & 0x1F) << 3))
    lum = [int(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in cols]
    return cols, lum


def to_img(tex, W, H, bpp, cols):
    im = Image.new('RGB', (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            if bpp == 8:
                v = tex[y * W + x]
            else:
                b = tex[y * (W // 2) + x // 2]
                v = (b >> 4) if x % 2 == 0 else (b & 0xF)
            px[x, y] = cols[v]
    return im


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(OUT, exist_ok=True)
    state = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    cols, lum = palette(state, 0x300)          # 104x40 버튼 뱅크 0x1800 → base 0x300
    cand = None
    rows = [r for r in BUTTONS if (only is None or r[0] == only)]
    tiles = []
    for row in rows:
        jp, kr, W, H, bpp, locs = row
        new, bbox = draw(row, lum, cand)
        old = get_tex(row)
        tiles.append((jp, kr, to_img(old, W, H, bpp, cols), to_img(new, W, H, bpp, cols)))
        print('%-8s → %-6s  글자영역 x=%d..%d y=%d..%d' % (jp, kr, *bbox))
    Wmax = max(t[2].width for t in tiles)
    sheet = Image.new('RGB', (Wmax * 2 + 24, sum(t[2].height + 8 for t in tiles)), (18, 18, 22))
    y = 0
    for jp, kr, a, b in tiles:
        sheet.paste(a, (0, y))
        sheet.paste(b, (Wmax + 24, y))
        y += a.height + 8
    sheet = sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST)
    p = os.path.join(OUT, 'preview.png')
    sheet.save(p)
    print('미리보기(왼쪽=원본 / 오른쪽=한글) →', p)


if __name__ == '__main__':
    main()
