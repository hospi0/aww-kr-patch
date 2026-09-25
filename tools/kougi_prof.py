# -*- coding: utf-8 -*-
"""지정한 셀 영역 안에서 원본 글자의 **픽셀 단위 위치**를 실측한다.

왜: 강의 화면의 글자는 12px 인데 타일 격자는 8px 라 **줄과 셀행의 위상이 어긋난다.**
    셀행만 보고 배치하면 줄 간격이 최대 2px 씩 밀린다. 원본 글자의 y 프로파일을
    직접 재서 그 자리에 그려야 한다.

사용: python tools/kougi_prof.py <화면> <cx0> <cy0> <cx1> <cy1>
"""
import os
import sys
import struct
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kougi_view import load_state, cells_of, CW, CH


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1])
    x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
    S = load_state(n)
    v2 = S['vdp2']
    cells = cells_of(v2)

    def pix(cx, cy):
        addr, w = cells[(cx, cy)]
        vf, hf = (w >> 31) & 1, (w >> 30) & 1
        return [[v2[addr + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                 for x in range(8)] for y in range(8)]

    W, H = (x1 - x0) * 8, (y1 - y0) * 8
    g = [[pix(x0 + x // 8, y0 + y // 8)[y % 8][x % 8] for x in range(W)]
         for y in range(H)]
    h = collections.Counter(v for r in g for v in r)
    bg = h.most_common(1)[0][0]
    print('영역 (%d,%d)-(%d,%d) = %dx%dpx, 배경 0x%02x' % (x0, y0, x1, y1, W, H, bg))
    print('  y별 잉크 픽셀 수 (화면 절대 y):')
    for y in range(H):
        c = sum(1 for v in g[y] if v != bg)
        ay = y0 * 8 + y
        bar = '#' * min(c, 60)
        print('    y%3d (cy%2d.%d) %3d %s' % (ay, ay // 8, ay % 8, c, bar))
    print('  x별 잉크 픽셀 수 (화면 절대 x):')
    xs = [sum(1 for y in range(H) if g[y][x] != bg) for x in range(W)]
    run = [x for x in range(W) if xs[x]]
    if run:
        print('    잉크 x 범위 = %d ~ %d (폭 %d)'
              % (x0 * 8 + run[0], x0 * 8 + run[-1], run[-1] - run[0] + 1))


if __name__ == '__main__':
    main()
