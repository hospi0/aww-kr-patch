# -*- coding: utf-8 -*-
"""세션13 — 16×16 한글 글리프의 「계조 규약」 비교표 (외곽 지저분 문제).

★문제: 게임 팔레트(state1 CRAM pal0/pal7)는 **1=밝은회색(0x788078) … 15=검정** 램프다.
  원본 일본어 글리프는 이걸 **「검정 본체(15) + 1px 밝은 외곽선(1)」**으로 쓴다(よ 실측).
  우리 render_kr는 커버리지를 그대로 0→15에 매핑해서 **본체가 10~14(어두운 회색)** 이고
  **AA 가장자리가 1~2 = 가장 밝은 색**으로 나간다 ⇒ 빨간 띠 위에서 흰 후광처럼 지저분.

비교안: A=현재 / B=원본규약(하드, 외곽1+본체15) / C=B+중간계조 / D=C 대비강화.
배경 2종(빨간 메시지 띠 pal0, 베이지 타이틀 pal2)에서 렌더.  출력 work/font_compare4.png
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec
from hangul import render_kr, REGULAR
from state_analyze import rzip_decompress, find_sections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = r"D:\hospi\RetroArch\screenshots\Advanced World War - Sennen Teikoku no Koubou - Last of the Millennium (Japan) (Rev B) (22M).state"
CELL = 16


# ── 팔레트 ────────────────────────────────────────────────────────────────
def cram_palettes(path=STATE):
    blob, _ = rzip_decompress(path)
    o, s = find_sections(blob, 'CRAM')[0]
    c = blob[o:o + s]
    pals = []
    for grp in range(8):
        row = []
        for i in range(16):
            w = struct.unpack_from('<H', c, (grp * 16 + i) * 2)[0]
            row.append(((w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8))
        pals.append(row)
    return pals


# ── 커버리지(0~1) 맵 ──────────────────────────────────────────────────────
def coverage(ch, px=14, ss=4, dy=0, fontpath=REGULAR):
    S = CELL * ss
    font = ImageFont.truetype(fontpath, px * ss)
    img = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S - w) / 2 - bb[0], (S - h) / 2 - bb[1] + dy * ss), ch, font=font, fill=255)
    small = img.resize((CELL, CELL), Image.LANCZOS)
    p = small.load()
    return [[p[x, y] / 255.0 for x in range(CELL)] for y in range(CELL)]


# 어두운계조 계열: 이름 → (floor, lo, hi).  floor = 가장 옅은 픽셀이 받을 색인.
#   ★팔레트 명도: 1=0x78 2=0x70 3=0x68 4=0x60 5=0x58 6=0x50 7=0x48 8=0x38 … 15=0x00
#   패널 회색(~0xB0)보다 **인덱스 1(0x78)도 더 어둡다** → 밝은 패널에선 1~7이 정상 AA로 보이고,
#   빨간 띠(0xC00000)에선 1~2가 흰 후광처럼 튄다. 그래서 floor로 「가장 옅은 값」을 조절한다.
DARK = {
    'H':  (8, 0.10, 0.55),      # 세션13 1차 기록본 — 후광 0이지만 밝은 패널에서 굵고 뭉툭
    'H2': (8, 0.30, 0.55),      # H + 옅은 픽셀 버림 → 얇게
    'M':  (4, 0.12, 0.55),      # 중간톤(0x60)까지 허용 = AA 살림, 후광은 약하게
    'M2': (6, 0.16, 0.55),      # 그 중간
    'M3': (4, 0.12, 0.75),      # M + 검정(15) 문턱을 높여 굵기를 A수준으로 되돌림
    'M4': (2, 0.10, 0.80),      # 거의 A의 굵기·부드러움, 다만 가장 밝은 1은 안 씀
}


def levels_from_cov(cov, mode, t_ink=0.50, lo=0.10, hi=0.55, gamma=0.75):
    """cov(16×16) → 니블 레벨(16×16). 0=투명, 1=밝은외곽, 15=검정본체.

    A=현재(0→15 직매핑) / B=8이웃 외곽선+하드 / C=B+중간계조 / D=C+S커브
    E=외곽선 추가 없음(폰트 AA만 1~15로) / F=2계조(본체15·나머지 투명) / G=4이웃 얇은외곽
    """
    ink = [[cov[y][x] >= t_ink for x in range(CELL)] for y in range(CELL)]

    def near_ink(y, x, four=False):
        offs = ((-1, 0), (1, 0), (0, -1), (0, 1)) if four else \
               tuple((dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        for dy, dx in offs:
            yy, xx = y + dy, x + dx
            if 0 <= yy < CELL and 0 <= xx < CELL and ink[yy][xx]:
                return True
        return False

    out = [[0] * CELL for _ in range(CELL)]
    for y in range(CELL):
        for x in range(CELL):
            c = cov[y][x]
            if mode == 'A':                        # 현재 방식
                out[y][x] = min(15, int(round((c ** gamma) * 15)))
                continue
            if mode == 'F':                        # 2계조
                out[y][x] = 15 if ink[y][x] else 0
                continue
            if mode in DARK:                       # 어두운 쪽 계조만 사용(외곽 밝음 금지)
                floor, lo, hi = DARK[mode]
                if c < lo:
                    continue
                t = (c - lo) / (hi - lo)
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                out[y][x] = min(15, floor + int(round(t * (15 - floor))))
                continue
            ring = (mode in 'BCD' and near_ink(y, x)) or \
                   (mode == 'G' and near_ink(y, x, four=True))
            if c <= 0 and not ring:
                continue                            # 투명
            if mode == 'B':                        # 하드: 본체15 / 외곽1
                out[y][x] = 15 if ink[y][x] else 1
            else:                                   # C·D·E·G: 1~15 사이 계조
                if ink[y][x] and c >= hi:
                    out[y][x] = 15
                else:
                    t = (c - lo) / (hi - lo)
                    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                    if mode == 'D':                 # 대비강화 (S커브)
                        t = t * t * (3 - 2 * t)
                    out[y][x] = max(1, min(15, 1 + int(round(t * 14))))
    return out


def glyph_bytes(lv):
    out = bytearray(128)
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                n = lv[cy + y][cx + x]
                i = t * 32 + y * 4 + x // 2
                if x % 2 == 0:
                    out[i] = (out[i] & 0x0F) | (n << 4)
                else:
                    out[i] = (out[i] & 0xF0) | n
    return bytes(out)


def levels_of_glyph(g):
    lv = [[0] * CELL for _ in range(CELL)]
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                b = g[t * 32 + y * 4 + x // 2]
                lv[cy + y][cx + x] = (b >> 4) if x % 2 == 0 else (b & 15)
    return lv


# ── 원본 폰트에서 일본어 글리프 ────────────────────────────────────────────
def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def jp_glyphs(text):
    f = open(TRACK1, 'rb')
    _, lba, size, _ = find_dirrec(f, 'ASCGSCG')[0][0]
    font = read_file(f, lba, size)
    f.close()
    m = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['ASCGSCG']
    rev = {v: int(k) for k, v in m.items()}
    return [font[rev[c] * 128:(rev[c] + 1) * 128] for c in text]


# ── 렌더 ─────────────────────────────────────────────────────────────────
def draw_line(levels_list, pal, bg, scale):
    n = len(levels_list)
    img = Image.new('RGB', (n * CELL, CELL), bg)
    px = img.load()
    for i, lv in enumerate(levels_list):
        for y in range(CELL):
            for x in range(CELL):
                v = lv[y][x]
                if v:
                    px[i * CELL + x, y] = pal[v]
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def main():
    pals = cram_palettes()
    P_RED, P_TAN = pals[0], pals[2]
    BG_RED, BG_TAN = (0xC0, 0x00, 0x00), (0x98, 0x98, 0x90)
    KR = '캠페인모드 이어하기 병기도감모드 계속할까요？'
    JP = 'キャンペーンモード コンティニュー 兵器図鑑モード よろしいですか？'
    covs = {c: coverage(c) for c in KR if '가' <= c <= '힣'}
    blank = [[0] * CELL for _ in range(CELL)]
    jpmap = {}
    for c in set(JP + KR):
        if c == ' ' or ('가' <= c <= '힣'):
            continue
        try:
            jpmap[c] = levels_of_glyph(jp_glyphs(c)[0])
        except KeyError:
            jpmap[c] = blank

    def kr_levels(mode):
        return [levels_from_cov(covs[c], mode) if c in covs
                else (blank if c == ' ' else jpmap[c]) for c in KR]

    rows = [('원본 일본어 (기준)', [blank if c == ' ' else jpmap[c] for c in JP]),
            ('A 최초빌드(흰후광)', kr_levels('A')),
            ('H 현재 기록본(뭉툭)', kr_levels('H')),
            ('M4 A굵기+밝은1 회피', kr_levels('M4')),
            ('M3 4~15 얇게', kr_levels('M3')),
            ('M 4~15', kr_levels('M')),
            ('F 2계조', kr_levels('F'))]

    BG_PANEL = (0xB0, 0xB0, 0xA8)                  # 메인메뉴 버튼 패널 회색(스샷 추정)
    scale = 3
    lab_w = 215
    blk = CELL * scale * 3 + 16
    W = lab_w + max(len(r[1]) for r in rows) * CELL * scale + 30
    H = blk * len(rows) + 34
    sheet = Image.new('RGB', (W, H), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    try:
        f14 = ImageFont.truetype(r'C:\Windows\Fonts\malgun.ttf', 15)
    except OSError:
        f14 = None
    d.text((lab_w, 8), '각 안: ①메인메뉴 패널 회색  ②빨간 메시지 띠  ③베이지 타이틀',
           fill=(230, 230, 230), font=f14)
    y = 30
    for lab, lv in rows:
        d.text((8, y + 20), lab, fill=(230, 230, 230), font=f14)
        sheet.paste(draw_line(lv, P_RED, BG_PANEL, scale), (lab_w, y))
        sheet.paste(draw_line(lv, P_RED, BG_RED, scale), (lab_w, y + CELL * scale))
        sheet.paste(draw_line(lv, P_TAN, BG_TAN, scale), (lab_w, y + CELL * scale * 2))
        y += blk
    out = os.path.join(ROOT, 'work', 'font_compare4.png')
    sheet.save(out)
    print('->', out)
    for lab, lv in rows:
        import collections
        h = collections.Counter(v for g in lv for row in g for v in row)
        print('%-18s 0:%3d 1:%3d 중간(2~14):%3d 15:%3d'
              % (lab, h[0], h[1], sum(h[i] for i in range(2, 15)), h[15]))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
