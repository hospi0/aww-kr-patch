# -*- coding: utf-8 -*-
"""버튼 17종 원본 텍스처를 디스크에서 떠서 **팔레트 적용 컬러**로 렌더한다 (세션17).

한글을 양각으로 새기려면 원본의 명암 구조를 먼저 실측해야 한다
([[project_aww_ss_kr]] 세션13-e: 획은 어두운 계조, rim 은 위/왼쪽만).

팔레트는 세이브스테이트 CRAM 에서 읽는다. VDP1 8bpp 는 CMDCOLR 상위비트가 팔레트 베이스다.
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from btn17_data import BUTTONS
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


def read_disk(path):
    m = {q: (l, s) for q, l, s in files(skip_media=False)}
    lba, size = m[path]
    out = bytearray()
    with open(TRACK1, 'rb') as f:
        for k in range(0, size, USER):
            f.seek((lba + k // USER) * RAW + HDR)
            out += f.read(min(USER, size - k))
    return bytes(out)


def cram_palette(state_blob):
    """CRAM 4096B → 2048색(15bit BGR555 word). 반환 [(r,g,b)]"""
    sec = sections(state_blob)
    off, size = sec['CRAM'][0]
    d = state_blob[off:off + size]
    pal = []
    for i in range(size // 2):
        w = struct.unpack_from('>H', d, i * 2)[0]
        r = (w & 0x1F) << 3
        g = ((w >> 5) & 0x1F) << 3
        b = ((w >> 10) & 0x1F) << 3
        pal.append((r, g, b))
    return pal


def render(tex, W, H, bpp, pal, base):
    im = Image.new('RGB', (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            if bpp == 8:
                v = tex[y * W + x]
            else:
                b = tex[y * (W // 2) + x // 2]
                v = (b >> 4) if x % 2 == 0 else (b & 0xF)
            px[x, y] = pal[(base + v) % len(pal)] if v else (0, 0, 0)
    return im


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(OUT, exist_ok=True)
    state = sys.argv[1] if len(sys.argv) > 1 else None
    pal = None
    if state:
        from state_analyze import rzip_decompress
        blob, _ = rzip_decompress(state)
        pal = cram_palette(blob)
        print('CRAM %d색 로드' % len(pal))
    disks = {}
    for jp, kr, W, H, bpp, locs in BUTTONS:
        p, off = locs[0]
        if p not in disks:
            disks[p] = read_disk(p)
        n = W * H * bpp // 8
        tex = disks[p][off:off + n]
        # 사본 일치 확인
        same = all(disks.setdefault(pp, read_disk(pp))[oo:oo + n] == tex for pp, oo in locs)
        raw = Image.frombytes('L', (W, H), tex) if bpp == 8 else None
        if raw:
            raw.resize((W * 4, H * 4), Image.NEAREST).save(
                os.path.join(OUT, '%s_gray.png' % jp))
        print('%-8s %3dx%-3d %dbpp  사본%d %s' % (jp, W, H, bpp, len(locs),
                                                 '일치' if same else '❌불일치'))
    print('→ %s' % OUT)


if __name__ == '__main__':
    main()
