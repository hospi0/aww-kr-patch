# -*- coding: utf-8 -*-
"""시나리오 타이틀(VDP1 스프라이트) 한글 렌더러 — 2026-10-03 재작업(사용자 «완벽해»).

★위치 (세이브스테이트 VDP1 텍스처와 12,800B 전부 일치로 확정)
  · `/INTERM` 파일 오프셋 **0x3DFF8, 스왑 없음**, 320x80 4bpp, 간격 0x3200, 11장.
  · 🐞세션19~20 의 「0x3E1E0 + swap16」 은 틀렸다 — 3줄+16px 밀리고 2px 쌍이 맞바뀌어
    글자가 규칙적으로 끊겨 보였다(「띄어쓰기」).
★팔레트(CRAM 실측) = 1 흰색(248) → 2..11 회색 → 13·14·15 검정. 0 투명.
★원본 글자 구조와 한글 재현
  · 검은 테두리 2px = 글자 바깥 1px(15) + 안쪽 1px(15/14/13).
  · 위·오른쪽 가장자리 안쪽 줄 = 흰 하이라이트 줄(원본 실측 위 32%·오른쪽 34% 흰색, 아래·왼쪽 3~5%).
  · 속 = 오른쪽 위 조명 — ↗/↙ 방향 획 길이로 위치(5단계)를 재서 **원본의 같은 구간 값 분포**에서 뽑는다.
  · 글꼴 Noto Sans KR VF 굵기 900, 제목마다 같은 굵기 확장(토폴로지 보존 한도, 0.25px 단위).
  · 1940/1944/1945 숫자(x≥205)와 아래 영문 부제는 원본 그대로.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont, ImageChops

BASE = 0x3DFF8          # /INTERM 안 파일 오프셋(스왑 없음)
STEP = 0x3200
W, H = 320, 80
ROW = W // 2
FONT = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'
WEIGHT = 900
GROW = 1                # 굵기 확장 상한(px)
SEED = 20261003
DIGIT = {1: 205, 5: 205, 6: 205}      # 이 x 부터 원본 숫자 보존
INNER = [15] * 6 + [14] * 3 + [13] * 2
HLV = [1] * 7 + [2] * 2 + [3]
PAL = [(0, 0, 0), (248, 248, 248), (200, 208, 216), (160, 176, 176), (144, 152, 160),
       (136, 144, 152), (128, 144, 152), (128, 136, 144), (120, 136, 144), (120, 128, 136),
       (112, 120, 128), (88, 96, 96), (56, 64, 64), (16, 16, 16), (8, 8, 8), (0, 0, 0)]

TITLES = {
    0:  '선전포고',        # 宣戦布告        / DECLARE WAR
    1:  '서부전선1940',    # 西部戦線1940    / VICTORY IN THE WEST
    2:  '배틀오브브리튼',   # バトル・オブ・ブリテン / BATTLE OVER CHANNEL
    3:  '북아프리카전선',   # 北アフリカ戦線   / N.AFRICA CAMPAIGN
    4:  '바르바로사',      # バルバロッサ     / EASTERN FRONT
    5:  '서부전선1944',    # 西部戦線1944    / WESTERN FRONT
    6:  '동부전선1945',    # 東部戦線1945    / END OF THE THIRD REICH
    7:  '제도붕괴',        # 帝都崩壊        / LAST OF THE MILLENNIUM
    8:  '대륙상륙',        # 大陸上陸        / GREAT VICTORY
    9:  '잃어버린시대',     # 失われし時代     / LOST WORLD
    10: '동부전선',        # 東部戦線        / RUSSIAN CAMPAIGN
}


def _font(sz):
    f = ImageFont.truetype(FONT, sz)
    f.set_variation_by_axes([WEIGHT])
    return f


def grid(D, k):
    b = BASE + k * STEP
    return [[(D[b + y * ROW + x // 2] >> 4) if x % 2 == 0 else D[b + y * ROW + x // 2] & 15
             for x in range(W)] for y in range(H)]


def pack(g):
    out = bytearray(W * H // 2)
    for y in range(H):
        for x in range(0, W, 2):
            out[y * ROW + x // 2] = (g[y][x] << 4) | g[y][x + 1]
    return bytes(out)


def _dmap(cells):
    dm, q = {}, []
    for k, v in cells.items():
        if not v:
            dm[k] = 0
            q.append(k)
    i = 0
    while i < len(q):
        y, x = q[i]
        i += 1
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = (y + dy, x + dx)
            if k in cells and k not in dm:
                dm[k] = dm[(y, x)] + 1
                q.append(k)
    return dm


def _comps(m, val):
    w, h = m.size
    px = m.load()
    seen = set()
    n = 0
    for y in range(h):
        for x in range(w):
            if (px[x, y] > 0) == val and (x, y) not in seen:
                n += 1
                st = [(x, y)]
                seen.add((x, y))
                while st:
                    a, b = st.pop()
                    for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                        if 0 <= c < w and 0 <= d < h and (c, d) not in seen and (px[c, d] > 0) == val:
                            seen.add((c, d))
                            st.append((c, d))
    return n


def _topo(m):
    bb = m.getbbox()
    if not bb:
        return (0, 0)
    m = m.crop((max(bb[0] - 3, 0), max(bb[1] - 3, 0), bb[2] + 3, bb[3] + 3))
    return (_comps(m, True), _comps(m, False))


def top_of(g):
    """제목/부제 경계 행(빈 행, 없으면 가장 빈 행)."""
    rows = [any(g[y]) for y in range(H)]
    for y in range(30, 70):
        if not rows[y]:
            return y
    cnt = [sum(1 for v in g[y] if v) for y in range(H)]
    return min(range(44, 58), key=lambda y: cnt[y])


def _spans(g, top):
    col = [any(g[y][x] for y in range(top)) for x in range(W)]
    out, cur = [], None
    for x, v in enumerate(col + [False]):
        if v:
            cur = [x, x] if cur is None else [cur[0], x]
        elif cur:
            if cur[1] - cur[0] >= 6:
                out.append(tuple(cur))
            cur = None
    return out


def _run(m, y, x, dy, dx, top):
    n = 0
    while 0 <= y < top and 0 <= x < W and m(y, x):
        n += 1
        y += dy
        x += dx
    return n


def _edgefeat(m, y, x, top):
    r = {sd: _run(m, y, x, dy, dx, top)
         for sd, (dy, dx) in (('T', (-1, 0)), ('R', (0, 1)), ('B', (1, 0)), ('L', (0, -1)))}
    d = min(r.values())
    if d > 3:
        return None
    f = {sd for sd, v in r.items() if v == d}
    return (d, 'TR' if f <= {'T', 'R'} else ('BL' if f <= {'B', 'L'} else 'X'))


def _learn_shade(gs):
    """원본 획 속 값 분포를 ↗/↙ 위치 5단계별로 모은다(오른쪽 위 조명)."""
    shade = {}
    for g in gs:
        tp = top_of(g)
        m = lambda yy, xx, g=g: g[yy][xx] != 0
        for y in range(tp):
            for x in range(W):
                v = g[y][x]
                if v and v < 13:
                    ur = _run(m, y, x, -1, 1, tp)
                    dl = _run(m, y, x, 1, -1, tp)
                    shade.setdefault(round((dl - ur) / (dl + ur) * 2), []).append(v)
    return shade


def _render(g, kr, keep, shade, rnd):
    top = top_of(g)
    sp = _spans(g, top)
    ys = [y for y in range(top) if any(g[y])]
    y0, y1 = ys[0], ys[-1]
    if keep:
        kr = ''.join(c for c in kr if not c.isdigit())
        sp = [(sp[0][0], keep - 2)]
    n = len(kr)
    if len(sp) == n:
        boxes = sp
        bw = sorted(b - a + 1 for a, b in boxes)[len(boxes) // 2]
    else:
        x0, x1 = sp[0][0], sp[-1][1]
        st = (x1 - x0 + 1) / n
        boxes = [(x0 + st * i, x0 + st * (i + 1) - 1) for i in range(n)]
        bw = min(b - a + 1 for a, b in boxes)
    hh = y1 - y0 + 1
    ss, size = 4, 200
    f = _font(size * ss)
    bb = ImageDraw.Draw(Image.new('L', (10, 10))).textbbox((0, 0), '깊', font=f)
    sc = min((hh - 1.5 * GROW - 2) / ((bb[3] - bb[1]) / ss),
             (bw - 1.5 * GROW) / ((bb[2] - bb[0]) / ss))
    f = _font(int(size * sc * ss))

    def draw(swd):
        ms = []
        for ch, (a, b) in zip(kr, boxes):
            cx, cy = (a + b) / 2, (y0 + y1) / 2
            mask = Image.new('L', (W * ss, top * ss), 0)
            dr = ImageDraw.Draw(mask)
            bb = dr.textbbox((0, 0), ch, font=f, stroke_width=swd)
            dr.text((cx * ss - (bb[0] + bb[2]) / 2, cy * ss - (bb[1] + bb[3]) / 2), ch, font=f,
                    fill=255, stroke_width=swd, stroke_fill=255)
            ms.append(mask.resize((W, top), Image.BOX).point(lambda v: 255 if v >= 128 else 0))
        return ms

    # 제목 전체에 같은 굵기 — 획이 붙거나 속 구멍이 막히지 않는 최대값
    base = draw(0)
    ref = [_topo(m) for m in base]
    for swd in range(4 * GROW, 0, -1):
        ms = draw(swd)
        if [_topo(m) for m in ms] == ref:
            base = ms
            break
    total = Image.new('L', (W, top), 0)
    for m in base:
        total = ImageChops.lighter(total, m)
    keepcols = set(range(keep, W)) if keep else set()
    cells = {(y, x): (1 if total.getpixel((x, y)) >= 128 else 0) for y in range(top) for x in range(W)}
    dm = _dmap(cells)
    ring = set()
    for (y, x), v in cells.items():
        if not v and any(cells.get((y + dy, x + dx)) for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
            ring.add((y, x))
    inside = lambda yy, xx: cells.get((yy, xx), 0)
    full = lambda yy, xx: bool(cells.get((yy, xx), 0)) or (yy, xx) in ring
    out = [r[:] for r in g]
    for y in range(top):
        for x in range(W):
            if x in keepcols:
                continue
            if (y, x) in ring:
                out[y][x] = 15
                continue
            if not cells[(y, x)]:
                out[y][x] = 0
                continue
            d = min(dm[(y, x)], 4)
            if d == 1:
                out[y][x] = rnd.choice(INNER)
                continue
            if d == 2:
                ft = _edgefeat(full, y, x, top)
                if ft and ft[1] == 'TR':
                    out[y][x] = rnd.choice(HLV)
                    continue
            ur = _run(inside, y, x, -1, 1, top)
            dl = _run(inside, y, x, 1, -1, top)
            out[y][x] = rnd.choice(shade[round((dl - ur) / (dl + ur) * 2)])
    return out


def render_all(D):
    """INTERM 원본 바이트 D → {k: 새 320x80 격자}. 시드 고정(재현 가능)."""
    gs = [grid(D, k) for k in range(11)]
    shade = _learn_shade(gs)
    rnd = random.Random(SEED)
    return {k: _render(gs[k], kr, DIGIT.get(k), shade, rnd) for k, kr in sorted(TITLES.items())}


def preview(D, res, path):
    def img(g):
        im = Image.new('RGB', (W, H))
        for y in range(H):
            for x in range(W):
                im.putpixel((x, y), PAL[g[y][x]] if g[y][x] else (40, 70, 40))
        return im
    sheet = Image.new('RGB', (W * 2 + 8, 11 * (H + 4)), (20, 20, 20))
    for k in range(11):
        sheet.paste(img(grid(D, k)), (0, k * (H + 4)))
        sheet.paste(img(res[k]), (W + 8, k * (H + 4)))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(path)
