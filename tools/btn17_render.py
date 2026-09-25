# -*- coding: utf-8 -*-
"""시나리오 화면 버튼 17종 한글 양각 렌더 (세션17).

방식은 세션13-e에 **사용자가 확정한 안 A**(`build_ketei2`)를 그대로 따른다:
    획(core) = 배경보다 어둡게, **계조 유지**(배경 − DARK×커버리지)
    rim      = **위/왼쪽 방향만** 배경 + LIGHT   (사방 rim 은 윤곽선처럼 지저분하다)

이 버튼들이 `決定` 과 다른 점:
  · 8bpp(개발중만 4bpp) — 색 후보가 넓다
  · 배경이 **좌→우 그라데이션 + 세로 변화** 라, 글자를 지운 배경을 따로 복원해야 한다
    ⇒ 글자 세로범위 위·아래 행에서 **세로 선형 보간**(글자 없는 열로 검증: 오차 평균 3.8)
  · 원문과 한글의 **글자 수가 전부 같다**(4→4, 3→3, 5→5) ⇒ 원본 글자 자리를 그대로 쓴다
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hangul import render_kr, CELL
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from btn17_data import BUTTONS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★★원본 실측(세션17, `作戦情報` 의 배경 복원본 대비 ±맵):
#   · 획 **내부는 배경색 그대로**다(차이 12 미만). 획을 어둡게 칠하는 게 아니다.
#   · 획의 **왼쪽·위 가장자리 = 밝게(+30~+50)**, **오른쪽·아래 가장자리 = 어둡게(−30~−80)**.
#   ⇒ 「글자를 파낸」 게 아니라 **배경 자체를 양각으로 새긴** 것이다(사용자 지적 2026-07-26).
#   표준 emboss = (좌상 이웃 커버리지 − 우하 이웃 커버리지) 에 비례해 배경을 밝히거나 어둡게.
# ★사용자 최종 확정(2026-07-26): 계조 emboss + 감마 0.35, +60/-95, 글자 14px.
LIGHT, DARK = 60, 120         # 위/왼쪽 밝기 · 아래/오른쪽 그림자 (사용자 확정: 안 A)
EDGE = 0.35                   # 획으로 볼 커버리지 문턱
FONT_PX = 14                  # 글자 크기(px)
GAMMA = 0.30                  # 음영 기울기 감마(<1 이면 약한 경계를 살린다)


def read_disk(path, _cache={}):
    if path not in _cache:
        m = {q: (l, s) for q, l, s in files(skip_media=False)}
        lba, size = m[path]
        out = bytearray()
        with open(TRACK1, 'rb') as f:
            for k in range(0, size, USER):
                f.seek((lba + k // USER) * RAW + HDR)
                out += f.read(min(USER, size - k))
        _cache[path] = bytes(out)
    return _cache[path]


def get_tex(row):
    jp, kr, W, H, bpp, locs = row
    p, off = locs[0]
    return read_disk(p)[off:off + W * H * bpp // 8]


def px_get(tex, W, bpp, x, y):
    if bpp == 8:
        return tex[y * W + x]
    b = tex[y * (W // 2) + x // 2]
    return (b >> 4) if x % 2 == 0 else (b & 0xF)


def px_set(tex, W, bpp, x, y, v):
    if bpp == 8:
        tex[y * W + x] = v
        return
    i = y * (W // 2) + x // 2
    if x % 2 == 0:
        tex[i] = (tex[i] & 0x0F) | ((v & 0xF) << 4)
    else:
        tex[i] = (tex[i] & 0xF0) | (v & 0xF)


def cell_mask(ch, w, h, px=None, ss=4, dy=0):
    """글자를 **셀 크기 그대로** 렌더한 커버리지 맵(0~1).

    ⚠️16×16 글리프를 셀에 늘려 넣으면 행·열이 중복돼 **획이 뭉툭해진다**(사용자 지적).
      셀 치수로 직접 렌더하면 스케일 왜곡이 없다.
    """
    from PIL import Image, ImageDraw, ImageFont
    from hangul import REGULAR
    if px is None:
        px = h - 4
    S = (w * ss, h * ss)
    font = ImageFont.truetype(REGULAR, px * ss)
    img = Image.new('L', S, 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S[0] - tw) / 2 - bb[0], (S[1] - th) / 2 - bb[1] + dy * ss),
           ch, font=font, fill=255)
    small = img.resize((w, h), Image.LANCZOS)
    p = small.load()
    return [[p[x, y] / 255.0 for x in range(w)] for y in range(h)]


def glyph_levels(g):
    """render_kr 의 128B 글리프 → 16×16 계조표.

    ⚠️**선형 16×16이 아니다.** `hangul.to_glyph` 는 8×8 타일 4개로 저장한다
      (`i = t*32 + y*4 + x//2`, t = 좌상·우상·좌하·우하). 선형으로 읽으면 글자가 잡음이 된다.
    """
    lv = [[0] * CELL for _ in range(CELL)]
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                i = t * 32 + y * 4 + x // 2
                lv[cy + y][cx + x] = (g[i] >> 4) if x % 2 == 0 else (g[i] & 0xF)
    return lv


def glyph_bbox(row, lum=None):
    """원본 글자 bbox. 104×40 은 **실측 상수**를 쓴다(자동검출은 테두리를 잡는다)."""
    jp, kr, W, H, bpp, locs = row
    if (W, H) == (104, 40):
        from btn17_data import GLYPH_BOX_104
        return GLYPH_BOX_104
    if (W, H) == (144, 40):
        from btn17_data import GLYPH_BOX_144
        return GLYPH_BOX_144
    if (W, H) == (32, 32):
        from btn17_data import GLYPH_BOX_32
        return GLYPH_BOX_32
    return _glyph_bbox_auto(row, lum)


def _glyph_bbox_auto(row, lum):
    """원본 글자가 차지한 영역 = 배경(세로보간 추정)과 크게 다른 픽셀의 bbox."""
    jp, kr, W, H, bpp, locs = row
    tex = get_tex(row)
    # 1차: 각 행이 '단조로운 배경 행'인지로 세로범위를 좁힌다
    rows = []
    for y in range(H):
        vals = [px_get(tex, W, bpp, x, y) for x in range(W)]
        rows.append(vals)
    # 세로 보간으로 배경을 만들고 차이를 본다 (반복 2회로 범위를 조인다)
    y0, y1 = 1, H - 2
    for _ in range(3):
        top, bot = max(0, y0 - 1), min(H - 1, y1 + 1)
        diff_rows = []
        for y in range(H):
            if not (top < y < bot):
                diff_rows.append(0)
                continue
            f = (y - top) / (bot - top) if bot != top else 0
            d = 0
            for x in range(W):
                pred = rows[top][x] * (1 - f) + rows[bot][x] * f
                d = max(d, abs(lum[rows[y][x]] - lum[int(round(pred))]))
            diff_rows.append(d)
        ys = [y for y, d in enumerate(diff_rows) if d > 40]
        if not ys:
            break
        y0, y1 = min(ys), max(ys)
    # 가로범위
    top, bot = y0 - 1, y1 + 1
    xs = []
    for x in range(W):
        d = 0
        for y in range(y0, y1 + 1):
            f = (y - top) / (bot - top)
            pred = rows[top][x] * (1 - f) + rows[bot][x] * f
            d = max(d, abs(lum[rows[y][x]] - lum[int(round(pred))]))
        if d > 40:
            xs.append(x)
    return min(xs), max(xs), y0, y1


def fill_bg(tex, W, H, bpp, x0, x1, y0, y1):
    """글자 영역을 위·아래 행에서 세로 선형 보간해 메운다."""
    top, bot = y0 - 1, y1 + 1
    out = bytearray(tex)
    for x in range(x0, x1 + 1):
        a = px_get(tex, W, bpp, x, top)
        b = px_get(tex, W, bpp, x, bot)
        for y in range(y0, y1 + 1):
            f = (y - top) / (bot - top)
            px_set(out, W, bpp, x, y, int(round(a * (1 - f) + b * f)))
    return out


def cells(kr, x0, x1, y0, y1, rows=1):
    """글자 셀 좌표. 원본 글자 자리를 글자 수로 균등 분할한다."""
    n = len(kr)
    if rows == 2:                      # 開発中 = 2행(2글자/1글자)
        per = [2, 1]
        out = []
        h = (y1 - y0 + 1) // 2
        k = 0
        for r, cnt in enumerate(per):
            w = (x1 - x0 + 1) / cnt
            for i in range(cnt):
                out.append((round(x0 + i * w), y0 + r * h, round(w), h, kr[k]))
                k += 1
        return out
    w = (x1 - x0 + 1) / n
    return [(round(x0 + i * w), y0, round(w), y1 - y0 + 1, kr[i]) for i in range(n)]


def draw(row, lum, cand=None):
    jp, kr, W, H, bpp, locs = row
    tex = get_tex(row)
    x0, x1, y0, y1 = glyph_bbox(row, lum)
    # ★지울 범위 = bbox + 여유(WIPE_PAD). 원본 글자가 bbox 를 넘어 삐져나온 픽셀이 남으면
    #   흰 노이즈로 보인다(세션13-e 실제 사고). 글자를 **그리는** 자리는 bbox 그대로다.
    from btn17_data import WIPE_PAD as PAD
    if (W, H) == (32, 32):
        # 開発中 패널은 배경이 거의 단색이다 — 세로 보간을 쓰면 줄무늬가 된다.
        # 글자 영역 **바깥 테두리 안쪽**의 최빈 색인으로 평평하게 메운다.
        ring = collections.Counter(
            px_get(tex, W, bpp, x, y)
            for y in range(1, H - 1) for x in range(1, W - 1)
            if not (x0 <= x <= x1 and y0 <= y <= y1))
        flat = ring.most_common(1)[0][0]
        out = bytearray(tex)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px_set(out, W, bpp, x, y, flat)
    else:
        out = fill_bg(tex, W, H, bpp,
                      max(1, x0 - PAD), min(W - 2, x1 + PAD),
                      max(1, y0 - PAD), min(H - 2, y1 + PAD))

    # ★후보는 **이 텍스처가 실제로 쓰는 색인**으로 제한한다.
    #   256색 전체를 후보로 두면 명도만 맞는 엉뚱한 색조가 튀어나온다(build_ketei2 주석 그대로).
    if cand is None:
        used = collections.Counter(px_get(tex, W, bpp, x, y)
                                   for y in range(H) for x in range(W))
        cand = [i for i, n in used.items() if n >= 3 and i != 0]
        if not cand:
            cand = [i for i in used if i != 0]

    def pick(t):
        return min(cand, key=lambda i: abs(lum[i] - t))

    # ★開発中(32×32 4bpp)도 **밝은 양각**이다(사용자 확인) — 배너와 같은 방식으로 간다:
    #   획은 계조로 밝게, 그림자는 우하단에 계조로 어둡게. 목표값에 **수렴**시켜
    #   4bpp 12색이라도 대비가 확보되게 한다.
    if (W, H) == (32, 32):
        for cx, cy, cw, chh, ch in cells(kr, x0, x1, y0, y1, 2):
            cov = cell_mask(ch, cw, chh, px=FONT_PX)

            def c(y, x):
                return cov[y][x] if 0 <= y < chh and 0 <= x < cw else 0.0

            for gy in range(chh):
                for gx in range(cw):
                    tx, ty = cx + gx, cy + gy
                    if tx > x1 or ty > y1:
                        continue
                    bg = lum[px_get(out, W, bpp, tx, ty)]
                    v = c(gy, gx)
                    if v > 0.08:
                        a2 = min(1.0, v) ** K32_INK_G
                        px_set(out, W, bpp, tx, ty, pick(bg * (1 - a2) + K32_INK * a2))
                    else:
                        sh = (max(c(gy - 1, gx - 1), c(gy - 1, gx), c(gy, gx - 1)) * 0.7
                              + max(c(gy - 2, gx - 2), c(gy - 2, gx), c(gy, gx - 2)) * 0.3)
                        if sh > 0.08:
                            a2 = min(1.0, sh) ** K32_SH_G
                            px_set(out, W, bpp, tx, ty, pick(bg * (1 - a2) + K32_SHADOW * a2))
        return bytes(out), (x0, x1, y0, y1)

    two = (jp == '開発中')
    for cx, cy, cw, chh, ch in cells(kr, x0, x1, y0, y1, 2 if two else 1):
        cov = cell_mask(ch, cw, chh, px=FONT_PX)

        def c(sy, sx):
            if 0 <= sy < chh and 0 <= sx < cw:
                return cov[sy][sx]
            return 0.0

        # ★계조 emboss: 이웃 커버리지의 **기울기**로 음영을 준다.
        #   오른쪽·아래에 획이 있으면 + (획의 왼쪽·위 바깥 = 빛),
        #   왼쪽·위에 획이 있으면 −  (획의 오른쪽·아래 바깥 = 그림자).
        #   획 **안쪽**은 양쪽이 상쇄되어 0 ⇒ 배경색이 그대로 남는다(양각의 핵심).
        #   1px 이진 선보다 계조가 살아 원본처럼 부드럽다.
        for gy in range(chh):
            ty = cy + gy
            for gx in range(cw):
                tx = cx + gx
                if tx > x1 or tx >= W or ty > y1:
                    continue
                d = ((c(gy, gx + 1) + c(gy + 1, gx)) / 2.0
                     - (c(gy, gx - 1) + c(gy - 1, gx)) / 2.0)
                if abs(d) < 0.06:
                    continue
                # 감마로 약한 기울기를 끌어올린다 — 얇은 획도 또렷해진다.
                d = (1 if d > 0 else -1) * abs(d) ** GAMMA
                bg = lum[px_get(out, W, bpp, tx, ty)]
                t = bg + (LIGHT * d if d > 0 else DARK * d)
                px_set(out, W, bpp, tx, ty, pick(max(0, min(255, int(round(t))))))
    return bytes(out), (x0, x1, y0, y1)


# ── 배너(144×40) 전용 ────────────────────────────────────────────────────
# 104×40 버튼과 **스타일이 다르다**:
#   · 배경이 각각 다른 전장 사진 ⇒ 세로 보간은 줄무늬로 뭉갠다. 오른쪽 사진을 가로 타일 복사.
#   · 글자는 배경색 양각이 아니라 **흰 획 + 검은 그림자**(사진 위 가독성용).
#     계조로 그려야 예쁘다(이진으로 찍으면 딱딱하다).
# 사용자 확정(2026-07-26): 글자 16px · 자간 86% · **왼쪽 위 정렬**.
BN_PX, BN_INK_G, BN_SH_G, BN_TIGHT = 16, 0.45, 0.32, 0.86
# ★그림자는 「배경 − 일정량」이 아니라 **검정으로 수렴**시킨다.
#   빼기 방식이면 배경이 밝은 배너(`戦略的敗北`)에서 그림자가 덜 진해 글자가 떠 보인다(사용자 지적).
BN_INK_TARGET, BN_SHADOW_TARGET = 252, 35   # 사용자 최종 확정(2026-07-26)
# 그림자 두께 가중치(1·2·3px 바깥) — 실기에서 양각이 약해 보여 강화(사용자 2026-07-26)
BN_SH_W1, BN_SH_W2, BN_SH_W3 = 1.0, 0.85, 0.55
SAT_MAX = 40                  # 이보다 채도가 높은 색인은 글자에 쓰지 않는다(초록 튐 방지)
# 開発中(32×32 4bpp) — 밝은 양각. 색이 12개뿐이라 목표값 수렴이 특히 중요하다.
K32_INK, K32_SHADOW, K32_INK_G, K32_SH_G = 250, 20, 0.45, 0.5
K32_PX = 12                   # 사용자 확정(2026-07-26)


def draw_banner(row, lum, lum2=None):
    """lum2 를 주면 **두 팔레트 모두**에서 적절한 밝기가 되는 색인을 고른다.

    ★배너는 같은 텍스처를 금색(CMDCOLR 0x3000)·어두운(0x3800) **두 팔레트**로 그린다.
      한쪽만 보고 고르면 다른 쪽에서 대비가 무너진다 — 어두운 팔레트 기준 최암 색인(2)이
      금색에서는 명도 11이라 **그림자가 회색**이 됐다(실기에서 그림자가 안 보인 원인).
      두 팔레트의 명도 범위가 달라(0~128 / 0~210) 각각 정규화해 평균으로 고른다.
    """
    from btn17_data import GLYPH_BOX_144
    jp, kr, W, H, bpp, locs = row
    X0, X1, Y0, Y1 = GLYPH_BOX_144
    tex = get_tex(row)
    out = bytearray(tex)
    # 배경 복원 = 글자영역 **위·아래 사진을 세로로 미러링**해 채우고 중앙에서 섞는다.
    #   오른쪽에서 가로로 타일 복사하면 그 배너만 오른쪽이 밝을 때 사각형 자국이 남는다
    #   (`戦略的敗北` 에서 실제로 발생). 같은 열의 사진을 쓰면 색·질감이 이어진다.
    #   ⚠️위쪽으로 반사하면 **프레임의 밝은 선**을 끌어와 줄무늬가 생긴다(실제로 겪음).
    #     ⇒ 글자영역 **아래쪽 사진만** 세로로 반복해 위로 채운다(같은 열이라 색·질감이 이어진다).
    ty0, ty1 = Y0 - 2, Y1 + 2
    SRC0, SRC1 = ty1 + 1, min(H - 5, ty1 + 9)      # 프레임 아래를 피한 사진 구간
    band = SRC1 - SRC0 + 1
    for x in range(X0 - 2, X1 + 3):
        for y in range(ty0, ty1 + 1):
            k = (ty1 - y) % (band * 2)
            sy = SRC0 + (k if k < band else band * 2 - 1 - k)    # 왕복 반사
            out[y * W + x] = tex[sy * W + x]
    cand = sorted({tex[i] for i in range(W * H)})
    # ★★★색인은 **원본 글자가 실제로 쓰는 것만** 쓴다.
    #   명도만 맞춰 고르면 팔레트의 엉뚱한 색조(어두운 초록 등)가 뽑혀 배너에 색이 튄다.
    #   원본 글자 픽셀 = 배경 복원본(out)과 원본(tex)이 다른 자리 ⇒ 그 색인 집합이 정답이다.
    ink_cand = sorted({tex[y * W + x]
                       for y in range(Y0 - 2, Y1 + 3)
                       for x in range(X0 - 2, X1 + 3)
                       if tex[y * W + x] != out[y * W + x]})
    if len(ink_cand) >= 4:
        cand = ink_cand
    if lum2 is None:
        def pick(t):
            return min(cand, key=lambda i: abs(lum[i] - t))
    else:
        m1 = max(1, max(lum[i] for i in cand))
        m2 = max(1, max(lum2[i] for i in cand))

        def pick(t):
            g = t / 255.0
            return min(cand, key=lambda i: abs(lum[i] / m1 - g) + abs(lum2[i] / m2 - g))

    n = len(kr)
    pitch = (X1 - X0 + 1) / n * BN_TIGHT
    chh = BN_PX + 2                               # 글자 높이 + 여유 → 위 정렬
    for i, ch in enumerate(kr):
        cx = int(round(X0 + i * pitch))           # ★왼쪽 정렬
        cw = int(round(pitch))
        cov = cell_mask(ch, cw, chh, px=BN_PX)

        def c(y, x):
            return cov[y][x] if 0 <= y < chh and 0 <= x < cw else 0.0

        for gy in range(chh):
            ty = Y0 + gy                          # ★위 정렬
            for gx in range(cw):
                tx = cx + gx
                if tx > X1 or tx < X0 or ty > Y1:
                    continue
                bg = lum[out[ty * W + tx]]
                v = c(gy, gx)
                if v > 0.08:
                    a = min(1.0, v) ** BN_INK_G
                    out[ty * W + tx] = pick(bg * (1 - a) + BN_INK_TARGET * a)
                else:
                    sh = min(1.0,
                             max(c(gy - 1, gx - 1), c(gy - 1, gx), c(gy, gx - 1)) * BN_SH_W1
                             + max(c(gy - 2, gx - 2), c(gy - 2, gx), c(gy, gx - 2)) * BN_SH_W2
                             + max(c(gy - 3, gx - 3), c(gy - 3, gx), c(gy, gx - 3)) * BN_SH_W3)
                    if sh > 0.08:
                        a = min(1.0, sh) ** BN_SH_G
                        out[ty * W + tx] = pick(bg * (1 - a) + BN_SHADOW_TARGET * a)
    return bytes(out), (X0, X1, Y0, Y1)
