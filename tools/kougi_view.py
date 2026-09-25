# -*- coding: utf-8 -*-
"""사관학교 강의 화면(/KOUGI) 조사 뷰어 — 세션21.

세션20 `build_kougi.py` 와 같은 구조 상수를 쓴다.
  · NBG0, 8bpp 타일, 패턴네임 2워드, PNT @0x24000
  · 캐릭터주소 = (패턴네임 & 0x7FFF) * 32,  팔레트오프셋 = ((PN>>16)&0x70)<<4
  · VRAM → KOUGI 파일 오프셋 보정 = -0x58F90

사용:
  python tools/kougi_view.py <화면번호> [--grid] [--writable] [--crop x0 y0 x1 y1]
    --grid      : 8px 셀 격자 + 10칸마다 좌표 라벨
    --writable  : 「이 화면에서 1회만 쓰이는 캐릭터」(=글자를 넣어도 되는 칸) 표시
    --crop      : 셀 좌표로 잘라서 4배 확대 저장
"""
import os
import sys
import struct
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw

from isoread import TRACK1, read_sector, walk, read_range

STATE_DIR = (r'C:\claude\project\aww-kr-patch\my files\todo'
             r'\2사관학교\사관학교 모든 스테이트')
STATE_BASE = ('Advanced World War - Sennen Teikoku no Koubou - '
              'Last of the Millennium (Japan) (Rev B) (22M).state')
OUTDIR = r'C:\claude\project\aww-kr-patch\my files\todo\2사관학교'
PNT, CW, CH = 0x24000, 44, 28
# ⚠️DELTA 는 **화면마다 다르다** — 상수를 쓰지 말고 `build_kougi.derive_delta()` 로
#   매번 역산한다. 아래 값은 화면1 전용 옛 상수라 참고용으로만 남긴다.
DELTA_SCREEN1 = -0x58F90


def load_state(n):
    from vdp1_dump import load
    return load(os.path.join(STATE_DIR, STATE_BASE + str(n)))


def cells_of(v2):
    out = {}
    for cy in range(CH):
        for cx in range(CW):
            w = struct.unpack_from('>I', v2, PNT + (cy * 64 + cx) * 4)[0]
            out[(cx, cy)] = ((w & 0x7FFF) * 32, w)
    return out


def rgb_of(cram, cofs, i):
    w = struct.unpack_from('<H', cram, ((cofs + i) % 2048) * 2)[0]
    return ((w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8)


def render(v2, cram, cells):
    im = Image.new('RGB', (CW * 8, CH * 8), (0, 0, 0))
    px = im.load()
    for (cx, cy), (addr, w) in cells.items():
        # ⚠️스테이트가 전환 도중이면 캐릭터 주소가 VRAM 밖을 가리키는 셀이 섞인다
        #   (사용자가 「윗부분이 깨진다」고 한 화면에서 9칸). 건너뛴다.
        if addr < 0 or addr + 64 > len(v2):
            continue
        cofs = ((w >> 16) & 0x70) << 4
        vf, hf = (w >> 31) & 1, (w >> 30) & 1
        for y in range(8):
            for x in range(8):
                v = v2[addr + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                px[cx * 8 + x, cy * 8 + y] = (0, 0, 0) if v == 0 else rgb_of(cram, cofs, v)
    return im


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1])
    S = load_state(n)
    v2, cram = S['vdp2'], S['cram']
    cells = cells_of(v2)
    use = collections.Counter(a for a, _ in cells.values())

    with open(TRACK1, 'rb') as f:
        pvd = read_sector(f, 16)
        rl = struct.unpack_from('<I', pvd[156:190], 2)[0]
        rs = struct.unpack_from('<I', pvd[156:190], 10)[0]
        ent = {e['path']: e for e in walk(f, rl, rs) if not e['dir']}
        KE = ent['/KOUGI']
        K = read_range(f, KE['lba'], KE['size'])

    from build_kougi import derive_delta
    DELTA = derive_delta(K, v2, cells, use)
    print('VRAM→파일 보정 = %s (자동 역산)' % hex(DELTA))

    def writable(cx, cy):
        addr, _ = cells[(cx, cy)]
        ko = addr + DELTA
        return use[addr] == 1 and 0 <= ko and ko + 64 <= len(K)

    im = render(v2, cram, cells)
    scale = 4
    big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(big)

    if '--writable' in sys.argv:
        for cy in range(CH):
            for cx in range(CW):
                if not writable(cx, cy):
                    d.rectangle([cx * 8 * scale, cy * 8 * scale,
                                 (cx + 1) * 8 * scale - 1, (cy + 1) * 8 * scale - 1],
                                outline=(255, 0, 0))
    if '--grid' in sys.argv:
        for cx in range(CW + 1):
            d.line([(cx * 8 * scale, 0), (cx * 8 * scale, big.height)],
                   fill=(0, 255, 255) if cx % 5 == 0 else (0, 90, 90))
        for cy in range(CH + 1):
            d.line([(0, cy * 8 * scale), (big.width, cy * 8 * scale)],
                   fill=(0, 255, 255) if cy % 5 == 0 else (0, 90, 90))
        for cx in range(0, CW, 5):
            d.text((cx * 8 * scale + 2, 2), str(cx), fill=(255, 255, 0))
        for cy in range(0, CH, 5):
            d.text((2, cy * 8 * scale + 2), str(cy), fill=(255, 255, 0))

    out = os.path.join(OUTDIR, '_view_state%d.png' % n)
    big.save(out)
    print('저장:', out, big.size)

    # 셀 통계
    tot = CW * CH
    ok = sum(1 for cy in range(CH) for cx in range(CW) if writable(cx, cy))
    print('쓸 수 있는 칸 %d / %d (%.0f%%)' % (ok, tot, ok * 100 / tot))

    if '--crop' in sys.argv:
        i = sys.argv.index('--crop')
        x0, y0, x1, y1 = (int(v) for v in sys.argv[i + 1:i + 5])
        c = im.crop((x0 * 8, y0 * 8, x1 * 8, y1 * 8))
        c = c.resize((c.width * 8, c.height * 8), Image.NEAREST)
        o2 = os.path.join(OUTDIR, '_crop_state%d_%d_%d.png' % (n, x0, y0))
        c.save(o2)
        print('crop 저장:', o2)


if __name__ == '__main__':
    main()
