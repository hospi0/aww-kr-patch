# -*- coding: utf-8 -*-
"""사관학교 화면 그래픽 한글화 — VDP1 스프라이트 텍스처 3장 제자리 교체 (세션13-e).

★사용자가 VDP1 디버거로 찍어준 정보(→ 스테이트에서 텍스처 추출 → 디스크 전수검색):
  · `受講` 버튼  = VDP1 `0x79B40`, 16×32 4bpp, CMDCOLR 0x30B80 → **/SCHOOL `0xB274`**
  · `受験` 버튼  = VDP1 `0x79C40`, 16×32 4bpp, 같은 뱅크      → **/SCHOOL `0xB174`**
  · `士官学校` 타이틀 = VDP1 `0x7C380`, 176×64 4bpp(Distorted), CMDCOLR 0x30780 → **/SCHOOL `0x7534`**
  전부 평문이라 **코드주입 불필요**.

★★팔레트 베이스 = **(디버거 CMDCOLR 값 ÷ 8) & 0x7FF** (세션13-e 확정)
  · 타이틀 base 0x0F0: **1 = f8f8f8(흰) … 15 = 000000(검정)** — 원본은 「흰 글자 + 검은 외곽선」
  · 버튼  base 0x170: 1 = 9098a0(밝음) … 11 = 080808(검정), 12~15 = 초록(LED)
    ⇒ 버튼 글자는 패널보다 **어두운** 색이다(잉크 11, 중간톤 9·10).

★렌더 방침
  · 타이틀: 한글을 **흰 채움 + 검은 외곽선**으로(PIL stroke_width), AA는 팔레트 회색 램프에 매핑.
  · 버튼: 프레임·패널을 보존하고 **글자 칸만** 행별 배경으로 메운 뒤 어두운 계조로 한글을 얹는다
    (병기도감 세로버튼 build_ketei2와 같은 방법).

빌드: python tools/build_school.py            드라이런(+미리보기)
      python tools/build_school.py --write     F: ISO 기록
      python tools/build_school.py --revert    원상복구
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from PIL import Image, ImageDraw, ImageFont
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

# ── 실측 팔레트(세션13-e, state3 CRAM에서 base=(CMDCOLR÷8)&0x7FF로 확정) ──
#   ★스테이트 없이도 빌드되도록 상수로 박아둔다. 0번은 VDP1 투명색.
PAL = {
 0x0F0: [(0x80,0x80,0xf8),(0xf8,0xf8,0xf8),(0xe0,0xe0,0xe8),(0xd0,0xd0,0xd8),
         (0xc0,0xc0,0xc8),(0xb0,0xb0,0xb8),(0x98,0x98,0x98),(0x88,0x88,0x88),
         (0x78,0x78,0x70),(0x68,0x68,0x60),(0x58,0x58,0x50),(0x40,0x40,0x40),
         (0x30,0x30,0x30),(0x20,0x20,0x20),(0x10,0x10,0x10),(0x00,0x00,0x00)],
 0x170: [(0x00,0x00,0x00),(0x90,0x98,0xa0),(0x70,0x78,0x80),(0x58,0x60,0x68),
         (0x50,0x58,0x60),(0x48,0x50,0x60),(0x38,0x40,0x50),(0x30,0x30,0x40),
         (0x28,0x28,0x38),(0x20,0x20,0x30),(0x10,0x10,0x18),(0x08,0x08,0x08),
         (0x60,0xa0,0x60),(0x60,0xa0,0x60),(0x60,0xa0,0x60),(0x60,0xa0,0x60)],
}


def cram_color(_cram, idx):
    base, i = idx & ~0xF, idx & 0xF
    return PAL[base][i]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
BOLD = r'C:\Windows\Fonts\malgunbd.ttf'
REGULAR = r'C:\Windows\Fonts\malgun.ttf'

# (라벨, /SCHOOL 오프셋, 폭, 높이, 팔레트base, 한글)
TITLE = ('title', 0x7534, 176, 64, 0x0F0, '사관학교')
BUTTONS = [('受講', 0xB274, 16, 32, 0x170, '강의'),
           ('受験', 0xB174, 16, 32, 0x170, '시험')]
BTN_BG = 2                        # 글자칸 배경 = 707880 (사용자 요청: 깨끗한 균일 회색)
BTN_INK = 11                      # 080808 = 검정 (원본처럼 어두운 글자)


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def school():
    f = open(TRACK1, 'rb')
    l, s = [(l, s) for p, l, s in files(skip_media=False) if p == '/SCHOOL'][0]
    d = read_file(f, l, s)
    f.close()
    return l, d


def unpack(buf, off, w, h):
    g = []
    for y in range(h):
        row = []
        for x in range(w):
            b = buf[off + y * (w // 2) + x // 2]
            row.append((b >> 4) if x % 2 == 0 else (b & 15))
        g.append(row)
    return g


def pack(g, w, h):
    out = bytearray(w * h // 2)
    for y in range(h):
        for x in range(w):
            i = y * (w // 2) + x // 2
            n = g[y][x]
            if x % 2 == 0:
                out[i] = (out[i] & 0x0F) | (n << 4)
            else:
                out[i] = (out[i] & 0xF0) | n
    return bytes(out)


def lum_table(cram, base):
    return [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in PAL[base]]


def render_title(orig, cram):
    """176×64 — 상단 한자 4자를 한글로. 아래 MILITARY ACADEMY(부제)는 보존."""
    w, h = TITLE[2], TITLE[3]
    lum = lum_table(cram, TITLE[4])
    g = [row[:] for row in orig]
    # 한자 영역 = y 0..44 (부제는 y>=45), x 0..175 → 전체 지우고 새로 그림
    TOP, BOT = 0, 45
    for y in range(TOP, BOT):
        for x in range(w):
            g[y][x] = 0
    # 4배 슈퍼샘플링으로 흰 글자 + 검은 외곽선
    SS = 4
    img = Image.new('L', (w * SS, (BOT - TOP) * SS), 0)      # 0 = 배경(투명)
    d = ImageDraw.Draw(img)
    px_size = 40 * SS
    font = ImageFont.truetype(BOLD, px_size)
    text = TITLE[5]
    bb = d.textbbox((0, 0), text, font=font, stroke_width=3 * SS)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    ox = (w * SS - tw) / 2 - bb[0]
    oy = ((BOT - TOP) * SS - th) / 2 - bb[1]
    # 외곽선 = 값 40(어두움), 채움 = 값 255(흰색)
    d.text((ox, oy), text, font=font, fill=255, stroke_width=3 * SS, stroke_fill=40)
    small = img.resize((w, BOT - TOP), Image.LANCZOS)
    sp = small.load()
    for y in range(BOT - TOP):
        for x in range(w):
            v = sp[x, y]
            if v < 12:
                continue                                     # 배경 유지(투명)
            # 밝기(0~255) → 팔레트에서 가장 가까운 명도의 색인(1~15)
            target = v / 255.0 * 248
            best = min(range(1, 16), key=lambda i: abs(lum[i] - target))
            g[TOP + y][x] = best
    return g


def render_button(orig, cram, kr, base):
    """16×32 — 프레임·패널 보존, 글자 칸만 행별 배경으로 메우고 어두운 계조로 한글."""
    w, h = 16, 32
    lum = lum_table(cram, base)
    g = [row[:] for row in orig]
    cells = [(3, 14), (17, 28)]     # (y0,y1) 원본 한자 실측 위치(각 12행)
    X0, X1 = 2, 13
    # ★패널 내부를 **전부** 균일한 회색으로 깐다 — 글자칸만 덮으면 위아래 밴드와 좌우 1열에
    #   원본 디더가 남아 얼룩으로 보인다(사용자 지적). 초록 LED(색인 12~15)와 외곽 1픽셀은 보존.
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if orig[y][x] < 12:
                g[y][x] = BTN_BG
    for (y0, y1), ch in zip(cells, kr):
        # ① 행별 배경 = 그 행에서 글자칸 밖(x=2..13 제외)의 최빈 색인… 프레임이라 안 맞으므로
        #    글자칸 내부의 최빈값(=패널색)을 쓴다
        # ② 한글 렌더(칸 크기에 맞춤)
        bw, bh = X1 - X0 + 1, y1 - y0 + 1
        SS = 8
        img = Image.new('L', (bw * SS, bh * SS), 0)
        d = ImageDraw.Draw(img)
        font = ImageFont.truetype(REGULAR, int(bh * SS * 0.95))
        bb = d.textbbox((0, 0), ch, font=font)
        d.text(((bw * SS - (bb[2] - bb[0])) / 2 - bb[0],
                (bh * SS - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=font, fill=255)
        sm = img.resize((bw, bh), Image.LANCZOS).load()
        ink = BTN_INK
        for y in range(bh):
            for x in range(bw):
                c = sm[x, y] / 255.0
                if c < 0.12:
                    continue
                t = min(1.0, (c - 0.12) / 0.63)
                target = lum[BTN_BG] * (1 - t) + lum[ink] * t
                cand = [i for i in range(1, 12)]              # 12~15는 초록(LED) 제외
                g[y0 + y][X0 + x] = min(cand, key=lambda i: abs(lum[i] - target))
    return g


def preview(pairs, cram, path):
    tiles = []
    for label, g, w, h, base in pairs:
        img = Image.new('RGB', (w, h))
        p = img.load()
        for y in range(h):
            for x in range(w):
                v = g[y][x]
                if v == 0:                        # 투명 — 체커로 표시
                    p[x, y] = (60, 60, 66) if (x // 4 + y // 4) % 2 else (44, 44, 48)
                else:
                    p[x, y] = cram_color(cram, base + v)
        sc = 2 if w > 100 else 6
        tiles.append(img.resize((w * sc, h * sc), Image.NEAREST))
    W = max(t.width for t in tiles)
    H = sum(t.height + 8 for t in tiles)
    sh = Image.new('RGB', (W, H), (20, 20, 24))
    y = 0
    for t in tiles:
        sh.paste(t, (0, y))
        y += t.height + 8
    sh.save(path)
    print('미리보기 ->', path)


def main():
    revert = '--revert' in sys.argv
    write = '--write' in sys.argv or revert
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    cram = None
    lba, d = school()

    jobs = []                                                # (off, w, h, orig_bytes, new_bytes)
    prev = []
    # 타이틀
    _, off, w, h, pb, kr = TITLE
    o = unpack(d, off, w, h)
    # 앵커 검증: 타이틀은 「흰 채움 1 + 검은 외곽 15」 구조라 두 색인이 지배적이어야 한다
    cnt = collections.Counter(v for row in o for v in row)
    if not (cnt[1] > 2000 and cnt[15] > 1000):
        raise SystemExit('★0x%X 가 예상 타이틀 텍스처가 아니다 (1:%d, 15:%d)'
                         % (off, cnt[1], cnt[15]))
    n = render_title(o, cram)
    jobs.append((off, w, h, d[off:off + w * h // 2], pack(n, w, h)))
    prev += [('title 원본', o, w, h, pb), ('title 새것', n, w, h, pb)]
    # 버튼 2개
    for label, off, w, h, pb, kr in BUTTONS:
        o = unpack(d, off, w, h)
        n = render_button(o, cram, kr, pb)
        jobs.append((off, w, h, d[off:off + w * h // 2], pack(n, w, h)))
        prev += [('%s 원본' % label, o, w, h, pb), ('%s→%s' % (label, kr), n, w, h, pb)]

    preview(prev, cram, os.path.join(ROOT, 'work', 'school_cmp.png'))
    print('/SCHOOL lba=%d — 텍스처 %d장 (%s)'
          % (lba, len(jobs), ', '.join('0x%X %dx%d' % (o, w, h) for o, w, h, _, _ in jobs)))
    if not write:
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return

    touched = set()
    with open(dst, 'r+b') as w_:
        for off, w, h, ob, nb in jobs:
            src, dstb = (nb, ob) if revert else (ob, nb)
            for k in range(len(ob)):
                lo = off + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w_.seek(pos)
                if w_.read(1) != src[k:k + 1]:
                    raise SystemExit('0x%x 대조실패 — %s'
                                     % (lo, '패치본아님' if revert else '이미패치?'))
                w_.seek(pos)
                w_.write(dstb[k:k + 1])
                touched.add(sec)
        for sec in sorted(touched):
            w_.seek(sec * RAW)
            raw = w_.read(RAW)
            w_.seek(sec * RAW)
            w_.write(ecc.fix_sector(raw))
    print('%s 완료 — %d섹터' % ('원상복구' if revert else '패치', len(touched)))
    with open(dst, 'rb') as r:
        for off, w, h, ob, nb in jobs:
            want = ob if revert else nb
            cur = read_file(r, lba, off + len(want))[off:]
            if cur != want:
                raise SystemExit('독립검증 실패 — 0x%x 되읽기 불일치' % off)
        for sec in sorted(touched):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                raise SystemExit('독립검증 실패 — 섹터 %d EDC/ECC' % sec)
    print('독립검증 통과.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
