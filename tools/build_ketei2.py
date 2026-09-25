# -*- coding: utf-8 -*-
"""병기도감·작전 화면 세로 `決定` 버튼 → 「결정」 (VDP1 8bpp 스프라이트, 세션13).

★정체 = 사용자가 Kronos VDP1 디버거로 잡아준 **Normal Sprite / texture 0x0007BE40 /
  48×80 / 8BPP(256색 뱅크) / color bank 0x00003800**. 스테이트에서 그 3,840B를 떠서 디스크를
  전수 검색 → **`/MUSEUM 0x727D8` 과 `/SAKUSEN 0x42558` 두 사본(바이트 동일)**. 평문이라
  **코드주입 불필요**. (가로 버튼은 별개 자산: GMSELDT 0x2F5C 4bpp → build_ketei.py)

★구조: 왼쪽 세로 패널에 決(위)·定(아래)이 박혀 있고 오른쪽은 슬라이더 트랙.
  패널은 **디더링 심한 금속 그라데이션(패널 영역에 202색)** 이라 배경을 계산으로 만들면 티가 난다
  ⇒ **행별 인접 배경 복제**로 글리프 자리를 메우고(세로 그라데이션이라 같은 행은 톤이 같다)
    그 위에 한글을 그린다.
★색 선택 = 팔레트 실측(work/ketei2_palette.json, color bank 768 = 디버거의 0x3800 대응)에서
  **명도로 역산**. 잉크는 원본 글리프가 쓰는 최저명도 색인, AA는 배경↔잉크 사이 명도에 가장
  가까운 **패널이 이미 쓰는 색인**만 골라(색조 튐 방지) 배정한다.

빌드: python tools/build_ketei2.py            드라이런(+미리보기)
      python tools/build_ketei2.py --write     F: ISO 기록(두 사본)
      python tools/build_ketei2.py --revert    원상복구
"""
import os
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from hangul import render_kr
from fontcompare4 import levels_of_glyph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
W, H = 48, 80
COPIES = [('/MUSEUM', 0x727D8), ('/SAKUSEN', 0x42558)]
PAL = os.path.join(ROOT, 'work', 'ketei2_palette.json')
# 글리프 셀 (원본 실측: 決 y36~51, 定 y52~67, x5~20)
CELLS = [(5, 36, '결'), (5, 52, '정')]
CELL = 16
REF_X = (2, 3)                    # 배경 참조 열(패널 왼쪽 여백, 글리프가 안 닿는다)
# 지울 범위(원본 글리프 실측 bbox y35~66 · x5~21 에 여유 1px)
WIPE_X0, WIPE_X1, WIPE_Y0, WIPE_Y1 = 4, 22, 34, 67


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def load_orig():
    f = open(TRACK1, 'rb')
    texs = []
    for path, off in COPIES:
        l, s = [(l, s) for p, l, s in files(skip_media=False) if p == path][0]
        d = read_file(f, l, s)
        texs.append((path, l, off, d[off:off + W * H]))
    f.close()
    if texs[0][3] != texs[1][3]:
        raise SystemExit('★두 사본이 다르다 — 오프셋 확인 필요')
    return texs


def palette():
    p = json.load(open(PAL))
    cols = [tuple(c) for c in p['colors']]
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in cols]
    return cols, lum


def make_texture(orig, cols, lum):
    tex = bytearray(orig)

    def at(x, y):
        return tex[y * W + x]

    # ① 지울 범위 = **원본 글리프의 실제 bbox + 여유 1px**.
    #   ★셀(16×16) 두 개만 지우면 원본 決의 맨 윗줄(y=35, 3픽셀)과 오른쪽 열(x=21)이 남아
    #     흰 노이즈로 보인다(사용자 지적, 세션13-e). 실측 bbox = y 35~66, x 5~21.
    for y in range(WIPE_Y0, WIPE_Y1 + 1):
        for x in range(WIPE_X0, WIPE_X1 + 1):
            tex[y * W + x] = orig[y * W + REF_X[(x - WIPE_X0) % 2]]

    # ② 패널이 쓰는 색인만 후보로(색조 튐 방지) — 명도 오름차순
    used = collections.Counter(orig[y * W + x] for y in range(H) for x in range(2, 22))
    cand = sorted(used, key=lambda i: lum[i])
    ink = cand[0]                                    # 최저명도 = 원본 글리프 잉크

    def pick(target):
        return min(cand, key=lambda i: abs(lum[i] - target))

    # ③ 한글을 **원본과 같은 양각 구조**로 그린다.
    #   ★★원본 決定 실측(배경 대비 ±명도 맵): **획은 어둡고, 그 둘레에 밝은 테두리**가 있다
    #     — 금속에 새긴 듯한 음영이다. 평면 어두운 글자로 그리면 원본 느낌이 사라진다(사용자 지적).
    #   ⇒ 획(core) = 배경보다 ~70 어둡게, 테두리(rim, 획을 1px 팽창한 고리) = 배경보다 ~45 밝게.
    #   ⇒ 안 A(사용자 확정): 획 = **계조 있는 어두운 색**(배경-80까지), rim = **위/왼쪽 방향만**
    #     배경+60. 사방 rim은 윤곽선처럼 지저분해지고 계조를 버리면 뭉툭해진다(1차 실패).
    DARK, LIGHT = 80, 60
    RIM_OFFS = [(1, 0), (1, 1), (0, 1)]              # 아래·오른쪽에 획이 있으면 = 위/왼쪽 테두리
    for cx, cy, ch in CELLS:
        lv = levels_of_glyph(render_kr(ch, ramp='dark'))
        cov = [[(lv[y][x] - 3) / 12 if lv[y][x] > 3 else 0.0 for x in range(CELL)]
               for y in range(CELL)]
        core = [[cov[y][x] >= 0.45 for x in range(CELL)] for y in range(CELL)]
        for y in range(CELL):
            bg = lum[tex[(cy + y) * W + cx]]          # 그 행의 배경 명도(메운 값)
            for x in range(CELL):
                c = cov[y][x]
                if c > 0.10:
                    tex[(cy + y) * W + cx + x] = pick(max(0, bg - DARK * min(1.0, c / 0.75)))
                elif any(0 <= y + dy < CELL and 0 <= x + dx < CELL and core[y + dy][x + dx]
                         for dy, dx in RIM_OFFS):
                    tex[(cy + y) * W + cx + x] = pick(min(255, bg + LIGHT))
    return bytes(tex), ink


def preview(texs, cols, path):
    from PIL import Image
    sh = Image.new('RGB', (len(texs) * (W + 6), H), (20, 20, 24))
    for i, t in enumerate(texs):
        img = Image.new('RGB', (W, H))
        px = img.load()
        for y in range(H):
            for x in range(W):
                px[x, y] = cols[t[y * W + x]]
        sh.paste(img, (i * (W + 6) + 3, 0))
    sh.resize((sh.width * 4, sh.height * 4), Image.NEAREST).save(path)
    print('미리보기 ->', path)


def main():
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv     # 이미 기록된 (다른) 한글 버전을 새 렌더로 덮는다
    write = '--write' in sys.argv or revert or resync
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    cols, lum = palette()
    texs = load_orig()
    orig = texs[0][3]
    new, ink = make_texture(orig, cols, lum)
    print('사본 %d곳: %s' % (len(texs), ', '.join('%s 0x%X' % (p, o) for p, _, o, _ in texs)))
    print('잉크 색인 %d (명도 %.0f), 글리프 셀 %s' % (ink, lum[ink], [(c[0], c[1], c[2]) for c in CELLS]))
    preview([orig, new], cols, os.path.join(ROOT, 'work', 'ketei2_cmp.png'))
    if not write:
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    src, dstb = (new, orig) if revert else (orig, new)
    touched = set()
    with open(dst, 'r+b') as w:
        for path, lba, off, _ in texs:
            for k in range(W * H):
                lo = off + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if not resync and w.read(1) != src[k:k + 1]:
                    raise SystemExit('%s 0x%x 대조실패 — %s'
                                     % (path, lo, '패치본아님' if revert else '이미패치?'))
                w.seek(pos)
                w.write(dstb[k:k + 1])
                touched.add(sec)
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('%s 완료 — %d섹터' % ('원상복구' if revert else '패치', len(touched)))
    with open(dst, 'rb') as r:
        for path, lba, off, _ in texs:
            cur = read_file(r, lba, off + W * H)[off:]
            if cur != dstb:
                raise SystemExit('독립검증 실패 — %s 되읽기 불일치' % path)
        for sec in sorted(touched):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                raise SystemExit('독립검증 실패 — 섹터 %d EDC/ECC' % sec)
    print('독립검증 통과 — 두 사본 일치, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
