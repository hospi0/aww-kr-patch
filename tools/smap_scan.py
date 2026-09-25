# -*- coding: utf-8 -*-
"""SMAP(브리핑 소형맵) 지명 라벨을 **자동 검출**하고 판독용 시트를 만든다.

세션21 교훈: 좌표를 격자 렌더에서 눈으로 읽었다가 잔재가 반복됐다
([[feedback_preview_must_match_screen]]). ⇒ bbox 는 **잉크 픽셀 연결성분**으로 실측한다.

구조: /M##/SMAP 은 +0x200 부터 136x128 8bpp 무압축. 글자 잉크 = idx **31**,
그림자 = idx **17**, dot0 = 투명.

usage:
  python tools/smap_scan.py 26 64          # 검출 결과 출력 + 판독시트 PNG
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont

from isoread import TRACK1, read_sector, walk, read_range

W, H = 136, 128
INK, SHD = 31, 17
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'work', 'maps', 'scan')


def entries():
    f = open(TRACK1, 'rb')
    pvd = read_sector(f, 16)
    rl = struct.unpack_from('<I', pvd[156:190], 2)[0]
    rs = struct.unpack_from('<I', pvd[156:190], 10)[0]
    return f, {e['path']: e for e in walk(f, rl, rs) if not e['dir']}


def smap(f, e):
    d = read_range(f, e['lba'], e['size'])
    return bytearray(d[0x200:0x200 + W * H])


def components(img):
    """잉크(31) 8-연결 성분 → bbox 리스트."""
    seen = bytearray(W * H)
    out = []
    for y in range(H):
        for x in range(W):
            i = y * W + x
            if img[i] != INK or seen[i]:
                continue
            st = [(x, y)]
            seen[i] = 1
            x0 = x1 = x
            y0 = y1 = y
            n = 0
            while st:
                cx, cy = st.pop()
                n += 1
                x0 = min(x0, cx); x1 = max(x1, cx)
                y0 = min(y0, cy); y1 = max(y1, cy)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < W and 0 <= ny < H:
                            j = ny * W + nx
                            if img[j] == INK and not seen[j]:
                                seen[j] = 1
                                st.append((nx, ny))
            out.append([x0, y0, x1, y1, n])
    return out


def group(comps, xgap=3, yov=0.4):
    """글자 성분들을 한 줄 라벨로 묶는다 (가로 간격 xgap 이하 + 세로 겹침)."""
    boxes = [c[:] for c in comps]
    boxes.sort(key=lambda b: (b[1], b[0]))
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a is None or b is None:
                    continue
                ov = min(a[3], b[3]) - max(a[1], b[1]) + 1
                hmin = min(a[3] - a[1], b[3] - b[1]) + 1
                gap = max(a[0], b[0]) - min(a[2], b[2]) - 1
                if ov >= yov * hmin and gap <= xgap:
                    a[0] = min(a[0], b[0]); a[1] = min(a[1], b[1])
                    a[2] = max(a[2], b[2]); a[3] = max(a[3], b[3])
                    a[4] += b[4]
                    boxes[j] = None
                    changed = True
        boxes = [b for b in boxes if b]
    boxes.sort(key=lambda b: (b[1], b[0]))
    return boxes


def sheet(img, boxes, path, mi):
    """라벨별 확대 크롭 + 번호 = 판독용 시트."""
    S, PAD = 8, 2
    fnt = ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf', 15)
    rows = []
    for k, (x0, y0, x1, y1, n) in enumerate(boxes):
        cw, ch = x1 - x0 + 1 + PAD * 2, y1 - y0 + 1 + PAD * 2
        crop = Image.new('RGB', (cw, ch), (0, 0, 0))
        px = crop.load()
        for y in range(ch):
            for x in range(cw):
                sx, sy = x0 - PAD + x, y0 - PAD + y
                if 0 <= sx < W and 0 <= sy < H:
                    v = img[sy * W + sx]
                    px[x, y] = ((255, 255, 255) if v == INK else
                                (90, 90, 110) if v == SHD else
                                (0, 0, 0) if v == 0 else (30, 60, 30))
        rows.append((k, crop.resize((cw * S, ch * S), Image.NEAREST),
                     (x0, y0, x1, y1, n)))
    if not rows:
        return
    LW = 250
    hh = sum(r[1].height + 10 for r in rows) + 30
    im = Image.new('RGB', (LW + max(r[1].width for r in rows) + 20, hh), (18, 18, 22))
    d = ImageDraw.Draw(im)
    d.text((10, 6), 'M%02d  라벨 %d개' % (mi, len(rows)), font=fnt, fill=(255, 220, 120))
    y = 28
    for k, crop, (x0, y0, x1, y1, n) in rows:
        d.text((10, y + 4), '#%d (%d,%d)-(%d,%d)' % (k, x0, y0, x1, y1),
               font=fnt, fill=(160, 220, 255))
        d.text((10, y + 22), 'w%d h%d px%d' % (x1 - x0 + 1, y1 - y0 + 1, n),
               font=fnt, fill=(130, 130, 140))
        im.paste(crop, (LW, y))
        y += crop.height + 10
    im.save(path)


def whole(img, boxes, path):
    S = 4
    im = Image.new('RGB', (W * S, H * S), (12, 12, 16))
    px = Image.new('RGB', (W, H))
    p = px.load()
    for y in range(H):
        for x in range(W):
            v = img[y * W + x]
            p[x, y] = ((255, 255, 255) if v == INK else
                       (90, 90, 110) if v == SHD else
                       (12, 12, 16) if v == 0 else (40, 80, 40))
    im.paste(px.resize((W * S, H * S), Image.NEAREST), (0, 0))
    d = ImageDraw.Draw(im)
    fnt = ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf', 13)
    for k, (x0, y0, x1, y1, n) in enumerate(boxes):
        d.rectangle([x0 * S - 2, y0 * S - 2, (x1 + 1) * S + 1, (y1 + 1) * S + 1],
                    outline=(255, 80, 80))
        d.text((x0 * S, y0 * S - 16), str(k), font=fnt, fill=(255, 200, 80))
    im.save(path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 26
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    os.makedirs(OUT, exist_ok=True)
    f, ent = entries()
    for mi in range(a, b + 1):
        e = ent.get('/M%02d/SMAP' % mi)
        if not e:
            print('M%02d 없음' % mi)
            continue
        img = smap(f, e)
        bx = group(components(img))
        bx = [c for c in bx if c[4] >= 8]        # 점·노이즈 제외
        print('M%02d: %d개  %s' % (mi, len(bx),
              ' '.join('#%d(%d,%d,%d,%d)' % (k, c[0], c[1], c[2], c[3])
                       for k, c in enumerate(bx))))
        sheet(img, bx, os.path.join(OUT, 'M%02d_sheet.png' % mi), mi)
        whole(img, bx, os.path.join(OUT, 'M%02d_map.png' % mi), )


if __name__ == '__main__':
    main()
