# -*- coding: utf-8 -*-
"""시나리오 타이틀(VDP1 스프라이트) 한글화 — /INTERM 제자리 패치 (세션19).

★구조 (실측)
  · 파일 `/INTERM`(lba 1916). 타이틀 텍스처는 **swap16 상태로 저장**돼 있다
    (파일을 2바이트 스왑해야 VDP1 VRAM 과 같은 바이트열이 된다).
  · 스왑 좌표 기준 첫 타이틀 = **0x3E1E0**, 320x80 4bpp = 12,800 B, **간격 0x3200 으로 11장**.
      #0 宣戦布告 / #1 西部戦線1940 / #2 バトル・オブ・ブリテン / #3 北アフリカ戦線 /
      #4 バルバロッサ / #5 西部戦線1944 / #6 東部戦線1945 / #7 帝都崩壊 /
      #8 大陸上陸 / #9 失われし時代 / #10 東部戦線
  · 한 장의 위 50줄 = 일본어 제목(4~6글자), 아래 30줄 = **영문 부제**(그대로 둔다).
  · 원본 글자는 「돌에 새긴」 질감 — **획 가장자리가 밝고(15) 안쪽이 어둡다**.
    거리별 값 분포를 원본에서 학습해 한글에 그대로 입힌다(시드 고정 = 재현 가능).

⚠️제자리 패치. 스왑 좌표 i 의 실제 파일 오프셋은 **i^1** 이다.

빌드: python tools/build_interm_title.py            드라이런
      python tools/build_interm_title.py --write    F: ISO 기록
      python tools/build_interm_title.py --resync   재기록
      python tools/build_interm_title.py --revert   원상복구
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import Counter, defaultdict

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
BASE = 0x3E1E0          # 스왑 좌표
STEP = 0x3200
W, H, TOP = 320, 80, 50
ROW = W // 2
FONT = r'C:\Windows\Fonts\malgunbd.ttf'   # Bold — 실기에서 또렷하게
PXG = 52
SEED = 20260727
# ★사용자 확정(2026-07-27, 실기 대조 후)
#   🐞1차는 획이 얇아 **배경에 묻혔다**(잉크 2,879px / 원본 6,887px).
#     한글은 한자보다 획이 두꺼워 「거리4~5」(어두운 내부값)가 대부분을 차지하는데,
#     원본 한자는 획이 얇아 거의 「거리1~2」(밝은 값)라 밝게 보였던 것.
#   ⇒ ①마스크 팽창으로 획을 굵게 ②**거리 상한 3** 으로 잘라 어두운 내부값을 배제.
MASK_THR = 45           # ★낮춤 — 높으면 LANCZOS 축소 후 획 가장자리가 임계 아래로
                        #   떨어져 **획에 구멍**이 뚫린다(실기에서 배경이 그대로 비쳤다).
DILATE = 1              # 팽창 1회
# ★★사용자 확정(2026-07-27): 원본은 **콘크리트 판에 글자를 파낸** 구조다.
#     · 획 가장자리(거리1) = 밝은 15  ← 파낸 단면
#     · 획 안쪽            = 콘크리트 질감(원본 텍스처에서 딴 8x8 패치를 랜덤 배치)
#   🐞한글은 획이 두꺼워 안쪽 질감 면적이 원본보다 훨씬 넓다 ⇒ **Regular 폰트로 얇게**
#     그려 원본과 같은 「테두리+좁은 질감」 비율을 만든다.
PATCH = 8               # 질감 패치 한 변

# ★★★팔레트 실측 (2026-07-27, VDP1 뷰어 `Save Bitmap` → 개수 매칭으로 역산)
#   🐞🐞 **값이 클수록 밝다는 가정이 정반대였다.** 15 를 흰색으로 알고 획을 채웠더니
#     실기에서 새까맣게 나왔고, 질감으로 쓴 어두운 값들은 배경에 묻혀 「투명」으로 보였다.
#     이 오해 하나 때문에 여러 번 헛빌드했다.
#   밝기순: 5(248) > 1(206) > 11(171) > 13(150) > 7(142) > 8(140) > 14(134) > 2(132)
#           > 10(126) > 3(118) > 4(94) > 15(16) > 9(8)
PAL_LUM = {5: 248, 1: 206, 11: 171, 13: 150, 7: 142, 8: 140, 14: 134,
           2: 132, 10: 126, 3: 118, 4: 94, 15: 16, 9: 8}
EDGE, EDGE2 = 5, 1              # 윤곽 = 가장 밝은 흰색
FILL = [11, 11, 13, 13, 7, 1, 11]   # 안쪽 콘크리트 질감(밝은 계열)
# ★색 판별 실험: 글자마다 다른 팔레트 인덱스로 칠해 **어느 값이 흰색인지** 실기에서 가려낸다.
#   팔레트(CMDCOLR 0x2680)를 CRAM 에서 읽지 못해 추측으로 15 를 썼다가 검게 나왔다.
#   판별이 끝나면 PROBE = None 로 두고 확정 값만 쓴다.
PROBE = None

# {인덱스: 한글}. 글자 중심·크기는 원본 열구간에서 자동 산출(centers_for).
#   ★원본 열구간 개수 == 한글 글자 수면 **그 구간 중심**을 그대로 쓴다(원본 자간 유지).
#     다르면 원본 글자 범위(x0~x1)에 균등 배치한다.
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


def sw(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def grid(D, base):
    return [[((D[base + y * ROW + x // 2] >> 4) if x % 2 == 0
              else (D[base + y * ROW + x // 2] & 15)) for x in range(W)] for y in range(H)]


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


def learn(src, spans):
    """원본 글자에서 「배경까지의 거리 → 값」 분포를 학습."""
    byd = defaultdict(Counter)
    for x0, x1 in spans:
        cells = {(y, x): src[y][x] for y in range(TOP) for x in range(x0, x1 + 1)}
        dm = _dmap(cells)
        for k, v in cells.items():
            if v:
                byd[min(dm.get(k, 9), 5)][v] += 1
    return {d: ([v for v, _ in c.most_common(8)], [n for _, n in c.most_common(8)])
            for d, c in byd.items()}


def spans_of(src):
    """상단 글자들의 열구간 — 값이 있는 열의 연속 구간."""
    col = [sum(1 for y in range(TOP) if src[y][x]) for x in range(W)]
    runs, cur = [], None
    for x, v in enumerate(col):
        if v:
            cur = [x, x] if cur is None else [cur[0], x]
        else:
            if cur and cur[1] - cur[0] >= 8:
                runs.append(tuple(cur))
            cur = None
    if cur and cur[1] - cur[0] >= 8:
        runs.append(tuple(cur))
    return runs


def centers_for(src, n):
    """원본 열구간에서 한글 n글자의 중심·글자크기를 산출."""
    sp = spans_of(src)
    if len(sp) == n:                       # 자간까지 원본 그대로
        cs = [(a + b) / 2 for a, b in sp]
        # ⚠️최소 폭을 쓰면 **잘린 첫 글자**(x0 부터 시작) 때문에 글자가 작아진다.
        #   원본 첫 글자는 텍스처 왼쪽 밖으로 나가 40px 로 측정된다 → 중앙값을 쓴다.
        ws = sorted(b - a + 1 for a, b in sp)
        px = min(PXG, int(ws[len(ws) // 2] * 1.05))
    else:                                  # 글자 수가 다르면 전체 범위에 균등
        x0, x1 = sp[0][0], sp[-1][1]
        step = (x1 - x0 + 1) / n
        cs = [x0 + step * (i + 0.5) for i in range(n)]
        px = min(PXG, int(step * 0.98))
    return cs, max(px, 20)


def slab_of(src, seed=SEED):
    """원본 텍스처에서 「꽉 찬 PATCH x PATCH 패치」를 모아 콘크리트 판을 재구성."""
    P = PATCH
    pats = []
    for y in range(TOP - P):
        for x in range(W - P):
            blk = [src[y + i][x + j] for i in range(P) for j in range(P)]
            if all(v > 0 for v in blk):
                pats.append(blk)
    if not pats:
        pats = [[15] * (P * P)]
    rnd = random.Random(seed)
    sl = [[0] * W for _ in range(TOP)]
    for by in range(0, TOP, P):
        for bx in range(0, W, P):
            blk = rnd.choice(pats)
            for i in range(P):
                for j in range(P):
                    if by + i < TOP and bx + j < W:
                        sl[by + i][bx + j] = blk[i * P + j]
    return sl


def render(src, kr, centers=None, pxg=PXG):
    """상단 50줄을 한글로 교체한 격자를 돌려준다(아래 30줄은 원본 그대로)."""
    tbl = learn(src, spans_of(src))
    if centers is None:
        centers, pxg = centers_for(src, len(kr))
    ss = 4
    mask = Image.new('L', (W * ss, TOP * ss), 0)
    dr = ImageDraw.Draw(mask)
    f = ImageFont.truetype(FONT, pxg * ss)
    for ch, cx in zip(kr, centers):
        bb = dr.textbbox((0, 0), ch, font=f)
        cw, chh = bb[2] - bb[0], bb[3] - bb[1]
        dr.text((cx * ss - cw / 2 - bb[0], (TOP / 2) * ss - chh / 2 - bb[1]),
                ch, font=f, fill=255)
    m = mask.resize((W, TOP), Image.LANCZOS)
    for _ in range(DILATE):
        m = m.filter(ImageFilter.MaxFilter(3))
    cells = {(y, x): (1 if m.getpixel((x, y)) >= MASK_THR else 0)
             for y in range(TOP) for x in range(W)}
    # ★★획 안에 갇힌 0 = **투명 구멍**. 그 자리로 배경(녹색)이 비친다.
    #   LANCZOS 축소 링잉으로 획 내부에 낮은 값이 생겨 임계 아래로 떨어지는 자리다.
    #   ⇒ 테두리에서 연결된 0 만 진짜 배경으로 두고, **나머지 0 은 전부 메운다**.
    outside = set()
    stack = [(y, x) for y in range(TOP) for x in (0, W - 1) if not cells[(y, x)]]
    stack += [(y, x) for x in range(W) for y in (0, TOP - 1) if not cells[(y, x)]]
    while stack:
        y, x = stack.pop()
        if (y, x) in outside:
            continue
        outside.add((y, x))
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = (y + dy, x + dx)
            if 0 <= k[0] < TOP and 0 <= k[1] < W and not cells[k] and k not in outside:
                stack.append(k)
    filled = 0
    for k in list(cells):
        if not cells[k] and k not in outside:
            cells[k] = 1
            filled += 1
    if filled:
        print('   구멍 메움 %d px' % filled)
    dm = _dmap(cells)
    rnd = random.Random(SEED)
    out = [r[:] for r in src]
    for y in range(TOP):
        for x in range(W):
            if not cells[(y, x)]:
                out[y][x] = 0
                continue
            # ★★실기 확정(2026-07-27): 이 팔레트에서 **눈에 보이는 값은 15 뿐**이다.
            #   🐞질감 값(3·4·9·11·13)으로 획 안쪽을 채웠더니 실기에서 배경에 묻혀
            #     밝은 윤곽 1px 만 가느다란 선으로 남았다(사용자 실기 스샷 2회).
            #     원본 한자는 획이 얇아 15(31%)가 형태를 다 만들지만, 한글은 획이 두꺼워
            #     안쪽 질감이 지배적이 된다 ⇒ **획 전체를 15 로 채운다.**
            d = dm.get((y, x), 9)
            out[y][x] = EDGE if d == 1 else (EDGE2 if d == 2 else rnd.choice(FILL))
    return out


def _gi(x, centers):
    """x 가 몇 번째 글자에 속하는지(색 판별 실험용)."""
    best, bi = 1e9, 0
    for i, c in enumerate(centers):
        d = abs(x - c)
        if d < best:
            best, bi = d, i
    return bi


def plans(D):
    """[(스왑좌표, 원본바이트, 새바이트)] — 상단 50줄만."""
    out = []
    for idx, kr in sorted(TITLES.items()):
        base = BASE + idx * STEP
        src = grid(D, base)
        new = render(src, kr)
        for y in range(TOP):
            for xb in range(ROW):
                o = base + y * ROW + xb
                hi, lo = new[y][xb * 2], new[y][xb * 2 + 1]
                nb = bytes([(hi << 4) | lo])
                # ★★상단 50줄은 **무조건 전부** 계획에 넣는다.
                #   🐞「원본과 다른 바이트만」 넣으면 --resync 가 **이전 빌드 흔적을 안 지운다**
                #     (이전엔 칠했는데 이번엔 안 칠하는 자리가 그대로 남는다).
                #     실기에서 글자 안에 잡색 130px 이 박혀 녹색 배경이 비쳤다.
                #     [[feedback_kr_patch_verification]] §20 과 같은 함정.
                out.append((o, D[o:o + 1], nb))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'INTERM')
        _, lba, size, _ = hits[0]
        orig = read_file(f, lba, size)
    D = sw(orig)
    pl = plans(D)
    print('/INTERM lba=%d size=%d — 타이틀 %d장, 바꿀 바이트 %d개'
          % (lba, size, len(TITLES), len(pl)))
    for idx, kr in sorted(TITLES.items()):
        src = grid(D, BASE + idx * STEP)
        cs, px = centers_for(src, len(kr))
        print('   #%-2d → %-12s %d자 %dpx  중심 %s'
              % (idx, kr, len(kr), px, ' '.join('%.0f' % c for c in cs)))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for o, a, b in pl:
            src_b, dst_b = (b, a) if revert else (a, b)
            real = o ^ 1                       # ★스왑 좌표 → 실제 파일 오프셋
            sec = lba + real // USER
            pos = sec * RAW + HDR + real % USER
            w.seek(pos)
            if w.read(1) != src_b and not resync:
                raise SystemExit('@0x%x 대조 실패 — %s'
                                 % (o, '패치본이 아님' if revert else '이미 패치됨?'))
            w.seek(pos)
            w.write(dst_b)
            touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)
    with open(dst, 'rb') as r:
        cur = sw(read_file(r, lba, size))
    bad = sum(1 for o, a, b in pl if cur[o:o + 1] != (a if revert else b))
    if bad:
        raise SystemExit('독립검증 실패 %d곳' % bad)
    print('독립검증 통과 — 되읽기 일치 (%d바이트)' % len(pl))


if __name__ == '__main__':
    main()
