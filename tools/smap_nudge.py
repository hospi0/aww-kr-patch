# -*- coding: utf-8 -*-
"""충돌하는 SMAP 라벨의 **최소 이동량**을 실측한다.

한글이 원본보다 넓어 깃발·거점 아이콘 위에 올라타는 라벨이 생긴다. 눈대중으로
옮기면 세션21처럼 어긋나므로, (dx,dy) 격자를 전수로 돌려 **덮는 픽셀 0**이 되는
가장 가까운 위치를 뽑는다. 최종 판단은 미리보기로 한다.

usage: python tools/smap_nudge.py [최소충돌수]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw

import mapkr
from smap_scan import entries, smap, W, H

INK, SHD = 31, 17


def glyph_pixels(ko, px, x0, y0, x1, y1, anc, dx, dy):
    f = mapkr.font(px)
    bb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), ko, font=f)
    gw, gh = bb[2] - bb[0], bb[3] - bb[1]
    ow = x1 - x0 + 1
    tx = x0 if anc == 'L' else (x1 - gw + 1 if anc == 'R' else x0 + (ow - gw) // 2)
    ty = y0 + ((y1 - y0 + 1) - gh) // 2
    tx = max(0, min(tx + dx, W - gw))
    ty = max(0, min(ty + dy, H - gh - 1))
    can = Image.new('L', (W, H), 0)
    ImageDraw.Draw(can).text((tx - bb[0], ty - bb[1]), ko, font=f, fill=255)
    out = []
    for y in range(H):
        for x in range(W):
            if can.getpixel((x, y)) >= 128:
                out.append((x, y))
                if x + 1 < W and y + 1 < H:
                    out.append((x + 1, y + 1))      # 그림자도 아이콘을 가린다
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    thr = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    f, ent = entries()
    todo = dict(mapkr.SMAP_LABELS)
    for d, s in mapkr.SMAP_ALIAS.items():
        todo[d] = mapkr.SMAP_LABELS[s]
    for mi, labels in sorted(todo.items()):
        e = ent['/M%02d/SMAP' % mi]
        img = smap(f, e)
        mask = mapkr.text_mask(img, W, H)
        for lb in labels:
            jp, ko, x0, y0, x1, y1, anc = lb[:7]
            dx0, dy0 = lb[7] if len(lb) > 7 else (0, 0)
            base = glyph_pixels(ko, mapkr.SMAP_PX, x0, y0, x1, y1, anc, dx0, dy0)
            hit = sum(1 for x, y in base if img[y * W + x] and not mask[y * W + x])
            if hit < thr:
                continue
            best = []
            for dy in range(-7, 8):
                for dx in range(-10, 11):
                    px = glyph_pixels(ko, mapkr.SMAP_PX, x0, y0, x1, y1, anc,
                                      dx0 + dx, dy0 + dy)
                    n = sum(1 for x, y in px
                            if img[y * W + x] and not mask[y * W + x])
                    best.append((n, abs(dx) + abs(dy), dx0 + dx, dy0 + dy))
            best.sort()
            print('M%02d %-12s 현재(%+d,%+d) 덮음 %d' % (mi, ko, dx0, dy0, hit))
            seen = set()
            for n, cost, dx, dy in best[:40]:
                if (n, cost) in seen:
                    continue
                seen.add((n, cost))
                print('        -> (%+d,%+d) 덮음 %d (이동 %d)' % (dx, dy, n, cost))
                if len(seen) >= 5:
                    break


if __name__ == '__main__':
    main()
