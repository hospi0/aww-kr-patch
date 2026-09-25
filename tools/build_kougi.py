# -*- coding: utf-8 -*-
"""사관학교 강의 화면(/KOUGI) 한글화 — 제자리 패치 (세션20).

★구조 (실측)
  · `/KOUGI`(lba 1199, 986,536B)는 **무압축**. VRAM 0x5A000 부터 그대로 로드된다.
    (스테이트 VDP2 VRAM 의 2KB 블록이 파일에서 그대로 발견됨 = 압축 아님)
  · 강의 화면 = **NBG0, 8bpp 타일, 패턴네임 2워드, PNT @0x24000**
      캐릭터주소 = (패턴네임 & 0x7FFF) * 32
      팔레트오프셋 = ((패턴네임 >> 16) & 0x70) << 4     ← **셀마다 다르다**
      dot 0 = 투명(실기에선 검정)
  · VRAM → KOUGI 파일 오프셋 보정 = **-0x58F90**
  · 화면 26개가 파일 0x001070~0x0F0BA0 을 순서대로 쓴다(화면당 32~45KB).
    캐릭터주소 0x54000~0x5A000 구간은 KOUGI 가 아닌 **공용 UI 타일**이라 건드리지 않는다.

⚠️크기 불변 제자리 패치. 셀 단위로 64B 를 통째로 덮어쓴다.

빌드: python tools/build_kougi.py            드라이런
      python tools/build_kougi.py --write    F: ISO 기록
      python tools/build_kougi.py --resync   대조 없이 재기록
      python tools/build_kougi.py --revert   원상복구
"""
import os
import sys
import collections
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont

import ecc
from isoread import TRACK1, RAW, HDR, USER, read_sector, walk, read_range

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
STATE_DIR = (r'C:\claude\project\aww-kr-patch\my files\todo'
             r'\2사관학교\사관학교 모든 스테이트')
STATE_BASE = ('Advanced World War - Sennen Teikoku no Koubou - '
              'Last of the Millennium (Japan) (Rev B) (22M).state')
PNT, CW, CH = 0x24000, 44, 28
DELTA = -0x58F90
# ★★폰트·렌더 방식 (품질 비교 실측 결과, `_폰트품질비교.png`)
#   🐞기존: 트루타입을 4배로 그린 뒤 LANCZOS 축소 → **12px 에서 획이 전부 뭉갠다.**
#     한글이 작고 흐려 읽을 수 없었던 진짜 원인이 폰트가 아니라 이 축소였다.
#   ⇒ **슈퍼샘플링을 쓰지 않고 목표 크기로 직접 렌더**한다. 굴림/돋움(gulim.ttc)은
#     작은 크기용 임베디드 비트맵·힌팅이 있어 픽셀 격자에 딱 떨어진다.
GULIM = r'C:\Windows\Fonts\gulim.ttc'
FONT_IDX = 2        # 0=굴림 1=굴림체 2=돋움 3=돋움체
FONT = GULIM
FONTB = GULIM       # 이 컬렉션엔 볼드가 없다 — 제목은 크기로 키운다


def _font(size, bold=False):
    return ImageFont.truetype(GULIM, size, index=FONT_IDX)


# 그라데이션 램프 파라미터 — tools/hangul.py `to_glyph_dark` 와 같은 사상.
#   LO 이하 커버리지는 투명, LO~HI 를 램프 전체(밝은→어두운)에 매핑한다.
RAMP_N = 12          # 원본이 쓰는 인덱스 중 빈도 상위 N개로 램프를 만든다
DARK_ONLY = True     # ★램프의 **어두운 절반만** 쓴다(사용자 요구: 훨씬 더 어둡게)
LO, HI = 0.12, 0.75
LOSS_TOL = 6         # 위치 선택 시 감수할 「버려지는 획」 픽셀 수(왼쪽 우선)
CENTER_ALIGN = True  # 제목·라벨을 원본 상자 **중앙**에 놓는다
# ★★글자색은 **한 곳에서 뽑아 전 글자에 고정**한다(사용자 확정).
#   🐞박스마다 원본 픽셀에서 램프를 따로 뽑으면 줄마다 색이 달라진다.
#     배경은 박스마다 다르지만(흰 박스 / 투명) **글자색은 하나여야 한다.**
# ★★글자색은 **RGB 로 고정**한다. 인덱스를 고정하면 셀마다 팔레트가 달라
#   같은 값이 다른 색으로 나온다 ⇒ 박스의 팔레트에서 이 RGB 에 **가장 가까운 인덱스**를 찾는다.
FIX_RGB = (40, 40, 40)        # 검은색에 아주 가까운 회색
FIX_COLOR_FROM = '하늘칸'      # (미사용) 참고용
FIX_EXCEPT = {'PUSH줄'}        # ★녹색 등 **따로 지정된 색**은 예외로 자기 색을 쓴다
GRADIENT = False               # ★★그라데이션 없이 **단색**(사용자 확정).
                               #   계조를 섞으면 자리마다 색이 달라 보인다.
BODY_PX = 12         # 본문 공통 글자 크기(전 줄이 자기 폭에 들어갈 때까지만 줄어든다)
BODY_DY = 0          # 줄 공통 세로 미세조정

# 화면번호(스테이트) → [(이름, cx0, cy0, cx1, cy1, 한글, 최대폰트px, 굵게)]
#   셀 범위는 「잉크맵」(비배경 픽셀 수)으로 실측해 정한다.
SCREENS = {
    1: [
        # ⚠️문구는 **줄별 폭 예산** 안에 넣어야 한다(실측: 본문1 77 / 2 86 / 3 92 /
        #   5 74 / 6 75 / **7 은 52px = 12px 기준 4.3자**).
        #   넘으면 폰트가 자동으로 11·10px 로 줄고, 그 크기에선 받침이 뭉개져 못 읽는다.
        #   → 원문 3줄을 뜻이 통하는 선에서 재배분했다.
        # 원문 대응 — 空面=하늘, 陸面=지상 (사용자 확정 용어)
        ('제목', 8, 1, 37, 4, '육·공 듀얼맵의 개념', 16, True),
        ('하늘칸', 3, 6, 7, 8, '하늘', 15, False),        # 흰 박스 안 라벨(空面)
        ('지상칸', 3, 16, 7, 19, '지상', 15, False),       # 陸面 은 cy16 하단부터 시작한다
        # ⚠️폭 예산은 **두 행이 모두 쓸 수 있는 연속 칸**이다(빌드 로그가 찍는다).
        #   본문7 은 아래 행(cy19)이 통째로 공유 타일이라 글자를 놓을 수 없다 →
        #   앞줄로 뜻을 합치고 이 줄은 비워서 원본 일본어를 지운다.
        ('본문1', 30, 6, 43, 8, '하늘=바둑판', 12, False),
        ('본문2', 30, 8, 43, 10, '지상=벽돌칸', 12, False),
        ('본문3', 30, 10, 43, 12, '모양이다', 12, False),
        # ⚠️cx26~28 은 A버튼 그래픽이다 — 덮으면 버튼이 지워진다. 글자는 cx29 부터.
        ('PUSH줄', 29, 12, 43, 14, 'PUSH로 전환', 12, False),   # 녹색 — 램프 별도
        ('본문5', 30, 14, 43, 16, '하늘 1칸은', 12, False),
        ('본문6', 30, 16, 43, 18, '지상 4칸', 12, False),
        ('본문7', 30, 18, 43, 20, '', 12, False),
    ],
}


def load_state(n):
    from vdp1_dump import load
    return load(os.path.join(STATE_DIR, STATE_BASE + str(n)))


def cells_of(v2):
    import struct
    out = {}
    for cy in range(CH):
        for cx in range(CW):
            w = struct.unpack_from('>I', v2, PNT + (cy * 64 + cx) * 4)[0]
            out[(cx, cy)] = ((w & 0x7FFF) * 32, w)
    return out


def plan_screen(K, v2, cram, boxes):
    def lum(i, cofs=0x500):
        """팔레트 밝기 — 램프를 밝은→어두운 순으로 세우는 데 쓴다."""
        w = struct.unpack_from('<H', cram, ((cofs + i) % 2048) * 2)[0]
        return 0.299 * (w & 31) + 0.587 * ((w >> 5) & 31) + 0.114 * ((w >> 10) & 31)

    """[(KOUGI오프셋, 새 64바이트)] 를 만든다."""
    cells = cells_of(v2)
    # ★★공유 타일 금지 규칙
    #   빈 배경 타일 하나를 화면 전역의 수백 셀이 함께 참조한다. 거기에 획을 그리면
    #   **화면 전체에 점선·줄무늬가 깔린다**(실제로 겪고 되돌렸다).
    #   ⇒ 화면 안에서 **1회만 쓰이는** 캐릭터만 고친다.
    use = collections.Counter(addr for addr, _ in cells.values())

    def pix(cx, cy):
        addr, w = cells[(cx, cy)]
        vf, hf = (w >> 31) & 1, (w >> 30) & 1
        return [[v2[addr + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                 for x in range(8)] for y in range(8)]

    # ── 1차 패스: 그룹 공통 기준을 **한 번만** 정한다 ──────────────────────
    #   ★★사용자 요구 = 「모든 글자를 같은 색·같은 크기·같은 줄맞춤」.
    #     🐞박스마다 램프·크기·정렬을 따로 계산해서 줄마다 색이 달라지고(본문7 만
    #       [74 9a 9f c4 e5 fa]) 들여쓰기가 어긋나고 크기가 12/11/10px 로 갈렸다.
    def writable(cx, cy):
        addr, _ = cells[(cx, cy)]
        ko = addr + DELTA
        return use[addr] == 1 and 0 <= ko and ko + 64 <= len(K)

    body = [b for b in boxes if b[0].startswith('본문')]

    # (1) 색 — 본문 **전체**를 합쳐 램프를 한 번만 만든다
    hall = collections.Counter()
    for name, x0, y0, x1, y1, *_ in body:
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                for row in pix(cx, cy):
                    for v in row:
                        hall[v] += 1
    BG = hall.most_common(1)[0][0]
    BODY_RAMP = sorted([v for v, n in hall.most_common() if v != BG][:RAMP_N],
                       key=lum, reverse=True)
    if DARK_ONLY and len(BODY_RAMP) > 3:
        BODY_RAMP = BODY_RAMP[len(BODY_RAMP) // 2:]

    # ★★글자색 고정 — 각 박스의 팔레트에서 FIX_RGB 에 가장 가까운 인덱스를 고른다.
    def cofs_of(x0, y0, x1, y1):
        c = collections.Counter()
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                _, w = cells[(cx, cy)]
                c[((w >> 16) & 0x70) << 4] += 1
        return c.most_common(1)[0][0]

    def ink_for(cofs):
        best, bi = None, 1
        for i in range(1, 256):
            w = struct.unpack_from('<H', cram, ((cofs + i) % 2048) * 2)[0]
            r, g, b = (w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8
            d = ((r - FIX_RGB[0]) ** 2 + (g - FIX_RGB[1]) ** 2 + (b - FIX_RGB[2]) ** 2)
            if best is None or d < best:
                best, bi = d, i
        return bi

    # (2) 폭 — **위아래 두 행이 모두 쓸 수 있는** 연속 칸만 글자를 놓을 수 있다.
    #     🐞한 행만 보고 폭을 잡으면 아래 행이 없는 자리에서 글자가 반토막 난다
    #       (본문7 은 cy19 전체가 공유 타일이라 받침이 통째로 잘렸다).
    span = {}
    for name, x0, y0, x1, y1, *_ in boxes:
        # ★기준 행 = **원본 글자가 실제로 걸친 행**.
        #   🐞박스의 모든 행을 요구했더니 빈 행(공유 타일)까지 걸려 제목 폭이
        #     사실상 0 이 되고, 그래서 제일 큰 제목이 제일 작게 그려졌다.
        rows = [cy for cy in range(y0, y1)
                if any(any(v for v in r) for cx in range(x0, x1) for r in pix(cx, cy))]
        good = [cx for cx in range(x0, x1)
                if all(writable(cx, cy) for cy in (rows or list(range(y0, y1))))]
        best, cur = [], []
        for cx in good:
            cur = cur + [cx] if (cur and cx == cur[-1] + 1) else [cx]
            if len(cur) > len(best):
                best = cur[:]
        span[name] = best

    # (3) 크기 — 본문 전 줄이 자기 폭에 들어가는 **공통** 크기
    def wid(txt, size):
        b = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
            (0, 0), txt, font=_font(size))
        return b[2] - b[0]

    # ★공통 좌측 = 각 줄 사용가능 구간 시작의 **최댓값**.
    #   🐞최솟값으로 잡았더니, 그 칸이 막힌 줄에서 첫 글자 획이 통째로 사라졌다
    #     (본문3 은 아래 행 cy11 의 첫 칸이 공유 타일 → 「칸」의 ㄴ받침이 날아갔다).
    XC = max((span[b[0]][0] for b in body if span[b[0]] and b[5]), default=0)
    BODY_X = XC * 8

    def avail(nm):
        """공통 좌측부터 그 줄이 실제로 쓸 수 있는 폭(px)."""
        sp = span[nm]
        return (sp[-1] - XC + 1) * 8 if sp and sp[0] <= XC <= sp[-1] else 0

    BODY_SZ = BODY_PX
    while BODY_SZ > 8:
        if all(not b[5] or wid(b[5], BODY_SZ) <= avail(b[0]) for b in body):
            break
        BODY_SZ -= 1
    print('   본문 공통: 좌측 x=%d, 크기 %dpx, 램프[%s]'
          % (BODY_X, BODY_SZ, ' '.join('%02x' % v for v in BODY_RAMP)))
    for b in body:
        if b[5]:
            # ★폭은 **공통 좌측부터** 그 줄이 쓸 수 있는 길이다(칸 수가 아니다).
            print('      %-5s 폭 %3dpx(%2d칸)  "%s" = %dpx%s'
                  % (b[0], avail(b[0]), avail(b[0]) // 8, b[5],
                     wid(b[5], BODY_SZ),
                     '  ⚠️초과' if wid(b[5], BODY_SZ) > avail(b[0]) else ''))
        elif not b[5]:
            print('      %-5s (비움 — 원본 지움)' % b[0])

    plan = []
    for name, x0, y0, x1, y1, text, px_, bold in boxes:
        is_body = name.startswith('본문')
        W, H = (x1 - x0) * 8, (y1 - y0) * 8
        if is_body:
            bg, ramp = BG, BODY_RAMP
        else:
            h = collections.Counter()
            for cy in range(y0, y1):
                for cx in range(x0, x1):
                    for row in pix(cx, cy):
                        for v in row:
                            h[v] += 1
            bg = h.most_common(1)[0][0]
            ramp = sorted([v for v, n in h.most_common() if v != bg][:RAMP_N],
                          key=lum, reverse=True)
            if DARK_ONLY and len(ramp) > 3:
                ramp = ramp[len(ramp) // 2:]
        if name not in FIX_EXCEPT:
            # ★그 박스의 팔레트에서 FIX_RGB 에 가장 가까운 인덱스 = 전 글자 같은 색
            ramp = [ink_for(cofs_of(x0, y0, x1, y1))]
        elif not GRADIENT and len(ramp) > 1:
            ramp = [ramp[len(ramp) // 2]]      # 예외(녹색 등)도 단색으로
        print('   %-6s 잉크 0x%02x' % (name, ramp[-1]))

        keep = set()          # 원본 픽셀을 그대로 둘 자리(밑줄 등 장식)
        im = Image.new('L', (W, H), 0)
        if text:
            d = ImageDraw.Draw(im)
            if is_body:
                size, sp = BODY_SZ, span[name]
                if not sp:
                    print('   %-6s 두 행 공통 칸 없음 — 건너뜀' % name)
                    continue
                fnt = _font(size)
                bb = d.textbbox((0, 0), text, font=fnt)
                tx = (BODY_X - x0 * 8) - bb[0]      # ★캔버스는 박스 **로컬** 좌표계
                ty = (H - BODY_SZ) / 2 - bb[1] + BODY_DY     # 줄마다 같은 높이
            else:
                # ★★제목·라벨은 **원본 글자가 실제 차지한 상자**에 맞춘다.
                #   🐞span(모든 행이 쓸 수 있는 연속 칸)으로 재면 제목 윗줄(cy1)이
                #     공유 타일 투성이라 7칸=56px 로 잡혀, **가장 큰 제목이 가장 작게**
                #     그려졌다(사용자 지적). 원본 제목은 실제로 232x19px 이다.
                #     공유 셀은 어차피 기록 단계에서 빠지므로 크기를 그것에 묶을 이유가 없다.
                g2 = [[pix(x0 + x // 8, y0 + y // 8)[y % 8][x % 8]
                       for x in range(W)] for y in range(H)]
                ink = [(x, y) for y in range(H) for x in range(W) if g2[y][x] != bg]
                if not ink:
                    continue
                ax0, ax1 = min(p[0] for p in ink), max(p[0] for p in ink)
                ay0, ay1 = min(p[1] for p in ink), max(p[1] for p in ink)
                # ★★세로 배치 — **공유 타일이 많은 셀행**과 **밑줄 행**은 피한다.
                #   🐞원본 글자는 y4 부터인데 y4~7 은 cy1 이고, cy1 은 29칸 중 11칸이
                #     공유 타일이라 그 자리 글자 윗부분이 통째로 사라졌다
                #     (「듀」·「맵의」가 반토막 난 진짜 원인).
                #   ⇒ writable 비율이 낮은 셀행을 제외하고, 남은 구간에 글자를 넣는다.
                #     그래서 16px + 밑줄보존 + 잘림0 은 동시에 성립하지 않는다(13px 가 한계).
                rowok = []
                for cy in range(y0, y1):
                    n = sum(1 for cx in range(x0, x1) if writable(cx, cy))
                    if n >= (x1 - x0) * 0.8:
                        rowok += [(cy - y0) * 8 + k for k in range(8)]
                under = set(yy for yy in range(H)
                            if sum(1 for xx in range(W) if g2[yy][xx] != bg) > W * 0.7)
                # ⚠️밑줄 회피는 **제목에만**. 흰 박스 라벨은 격자선이 가로로 길어
                #   under 에 대거 걸리고, 그러면 상자가 3~6px 로 쪼그라든다.
                usable = ([yy for yy in rowok if yy not in under] if name == '제목'
                          else list(range(ay0, ay1 + 1))) or list(range(ay0, ay1 + 1))
                # ★min/max 로 잡으면 **불연속 구간 사이의 밑줄을 도로 삼킨다**.
                #   반드시 **최장 연속** 구간을 쓴다.
                runs, cur = [], []
                for yy in sorted(usable):
                    cur = cur + [yy] if (cur and yy == cur[-1] + 1) else [yy]
                    if not runs or len(cur) > len(runs[0]):
                        runs = [cur[:]]
                by0, by1 = runs[0][0], runs[0][-1]
                aw, ah = ax1 - ax0 + 1, by1 - by0 + 1
                # ★세로는 폰트 크기가 아니라 **실제 bbox 높이**로 판정하고 1px 여유를 준다
                #   (사용자 요구: 한 포인트만 키우기).
                size = px_
                while size > 8:
                    bt = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
                        (0, 0), text, font=_font(size))
                    if (bt[2] - bt[0]) <= aw and (bt[3] - bt[1]) <= ah + 1:
                        break
                    size -= 1
                fnt = _font(size)
                bb = d.textbbox((0, 0), text, font=fnt)
                # ★★가로 위치는 **공유 칸을 피해서** 고른다.
                #   🐞중앙정렬로 고정했더니 「공」자가 공유 칸(cx18)에 얹혀 획이 잘렸다.
                #     공유 칸에 떨어진 획은 기록 단계에서 버려지므로 그 글자만 반토막 난다.
                #   ⇒ 원본 폭 안에서 후보 위치를 훑어 **버려질 획이 가장 적은** 곳을 쓴다.
                ty = by0 + (ah - (bb[3] - bb[1])) / 2 - bb[1]
                gw = bb[2] - bb[0]
                base = ax0 + (aw - gw) / 2 - bb[0]
                cand, best = base, None
                # ★사용자 확정: **중앙정렬**. 획이 좀 깨져도 위치가 더 중요하다.
                #   공유 칸 회피 탐색(loss 최소)은 오른쪽 끝으로 쏠려 보기 나빴다.
                if not CENTER_ALIGN:
                    for dx in range(int(-(aw - gw) / 2), int((aw - gw) / 2) + 1):
                        probe = Image.new('L', (W, H), 0)
                        ImageDraw.Draw(probe).text((base + dx, ty), text, font=fnt, fill=255)
                        loss = sum(1 for yy in range(H) for xx in range(W)
                                   if probe.getpixel((xx, yy)) >= 128
                                   and not writable(x0 + xx // 8, y0 + yy // 8))
                        if best is None or loss < best:
                            best, cand = loss, base + dx
                        if loss == 0:
                            break
                tx = cand
                # ★★밑줄 보존 — 제목 아래 가로줄은 글자가 아니라 **장식**이다.
                #   🐞박스를 통째로 덮어써서 원본 밑줄이 사라졌다(사용자 지적).
                #   ⇒ 「가로로 70% 이상 채워진 행」은 원본 픽셀을 그대로 둔다.
                if name == '제목':          # ★라벨(흰 박스)의 격자선을 밑줄로 오판하지 않게
                    for yy in under:
                        keep.update((xx, yy) for xx in range(W))
                print('   %-6s 쓸수있는상자 %dx%d(y%d~%d) → %dpx  "%s"'
                      % (name, aw, ah, by0, by1, size, text))
            d.text((tx, ty), text, font=fnt, fill=255)

        skipped = 0
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                addr, w = cells[(cx, cy)]
                ko = addr + DELTA
                if ko < 0 or ko + 64 > len(K):
                    continue
                if use[addr] > 1:
                    skipped += 1
                    continue
                buf = bytearray(K[ko:ko + 64])
                for y in range(8):
                    for x in range(8):
                        px_x, px_y = (cx - x0) * 8 + x, (cy - y0) * 8 + y
                        if (px_x, px_y) in keep:
                            continue                      # ★원본 그대로(밑줄 등)
                        c = im.getpixel((px_x, px_y)) / 255.0
                        if c < LO:
                            buf[y * 8 + x] = bg
                            continue
                        # ★★그라데이션 — 원본과 같은 「내부는 진하게, 가장자리는 옅게」.
                        #   🐞직접 렌더는 힌팅 때문에 커버리지가 0/255 로 몰려서,
                        #     커버리지만 램프에 매핑하면 **중간톤이 안 나와 그라데이션이 사라진다.**
                        #   ⇒ 획 **안쪽인지 가장자리인지**로 계조를 나눈다.
                        solid = c >= 0.5
                        if not GRADIENT:
                            # ★단색 — 계조 없이 획이면 잉크, 아니면 배경
                            buf[y * 8 + x] = ramp[-1] if solid else bg
                        elif not solid:
                            buf[y * 8 + x] = ramp[0]              # 옅은 외곽
                        else:
                            nb = [(px_x - 1, px_y), (px_x + 1, px_y),
                                  (px_x, px_y - 1), (px_x, px_y + 1)]
                            inner = all(0 <= a < im.width and 0 <= b < im.height
                                        and im.getpixel((a, b)) / 255.0 >= 0.5
                                        for a, b in nb)
                            buf[y * 8 + x] = ramp[-1] if inner else ramp[len(ramp) // 2]
                plan.append((ko, bytes(buf)))
    return plan


def derive_delta(K, v2, cells, use):
    """★★VRAM→파일 보정은 **화면마다 다르다.** 세션20 이 확정한 `-0x58F90` 은
    화면1 전용이었다(실측: state1 -0x58F90 / state2 -0x4FAE0 / state12 +0x9B80 /
    state20 +0x58300 / state26 +0x8ED60).

    🐞상수를 그대로 쓰면 엉뚱한 파일 위치의 데이터로 셀을 채워 **화면 전체가 노이즈로
      덮이고**, 그대로 ISO 에 쓰면 다른 강의 화면을 망가뜨린다(세션21 에 실제로 겪음).
    ⇒ 잉크가 풍부한 **고유 타일**을 파일에서 역검색해 자동 도출하고, 후보가 하나로
      모이는지 + 24개가 전원 일치하는지 검증한다.
    """
    hits = collections.Counter()
    for (cx, cy), (a, w) in sorted(cells.items()):
        if use[a] != 1 or len(set(v2[a:a + 64])) < 6:
            continue
        blk = bytes(v2[a:a + 64])
        if K.count(blk) != 1:
            continue
        hits[K.find(blk) - a] += 1
        if sum(hits.values()) >= 24:
            break
    if not hits:
        raise SystemExit('보정 도출 실패 — 고유 타일을 못 찾았다')
    d, n = hits.most_common(1)[0]
    if len(hits) != 1 or n < 8:
        raise SystemExit('보정 도출 실패 — 후보 %s' % hits.most_common(3))
    return d


def load_kougi():
    """ISO 원본에서 /KOUGI 를 통째로 읽어 (엔트리, 바이트) 를 준다."""
    with open(TRACK1, 'rb') as f:
        pvd = read_sector(f, 16)
        rl = struct.unpack_from('<I', pvd[156:190], 2)[0]
        rs = struct.unpack_from('<I', pvd[156:190], 10)[0]
        ent = {e['path']: e for e in walk(f, rl, rs) if not e['dir']}
        KE = ent['/KOUGI']
        return KE, read_range(f, KE['lba'], KE['size'])


def write_plan(plan, K, lba, size, revert=False, resync=False):
    """[(파일오프셋, 64B)] 를 F: ISO 에 기록하고 EDC/ECC 재계산 + 독립 되읽기 검증.

    ⚠️`--revert` 는 「패치된 값」에서 출발하므로 대조를 걸지 않는다(걸면 되돌리기가 막힌다).
    """
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    touched = set()
    with open(dst, 'r+b') as w:
        for ko, buf in plan:
            src = K[ko:ko + 64] if revert else buf     # 이번에 써 넣을 값
            for k in range(64):
                off = ko + k
                sec = lba + off // USER
                pos = sec * RAW + HDR + off % USER
                w.seek(pos)
                cur = w.read(1)[0]
                # 허용 상태 = 원본값(K) 또는 이번 목표값(src). 그 외는 예상 밖.
                # ⚠️--revert 는 「패치된 값」에서 출발하므로 대조를 걸지 않는다
                #    (걸면 되돌리기 자체가 막힌다).
                if not resync and not revert and cur != K[off] and cur != src[k]:
                    raise SystemExit('@0x%x 대조 실패(현재 %02x, 원본 %02x) — 예상 밖 상태'
                                     % (off, cur, K[off]))
                if cur != src[k]:
                    w.seek(pos)
                    w.write(bytes([src[k]]))
                touched.add(sec)          # ★ECC 는 건드린 섹터 전부 재계산
        print('쓴 섹터 %d개 — EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    # 독립 되읽기 검증
    with open(dst, 'rb') as r:
        cur = read_range(r, lba, size)
    bad = sum(1 for ko, buf in plan
              if cur[ko:ko + 64] != (K[ko:ko + 64] if revert else buf))
    print('완료 ->', dst)
    if bad:
        raise SystemExit('독립검증 실패 %d셀' % bad)
    print('독립검증 통과 — 되읽기 일치 (%d셀), 파일크기 %d 유지' % (len(plan), len(cur)))


def dedup(plan):
    """★★같은 캐릭터 타일을 **여러 셀이 공유**한다(강의1 기준 7종).
    🐞중복을 안 걷어내면 두 번째 차례에 「방금 내가 쓴 값」을 예상 밖 상태로 오판해
      기록이 중간에 멈춘다(ECC 재계산 전이라 ISO 가 깨진 채로 남는다).
    """
    seen, dup = {}, 0
    for o, b in plan:
        if o in seen:
            dup += 1
            continue
        seen[o] = b
    if dup:
        print('공유 타일 %d건 — 첫 배치만 남김' % dup)
    return sorted(seen.items())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync

    KE, K = load_kougi()
    lba, size = KE['lba'], KE['size']
    print('/KOUGI lba=%d size=%d (무압축·제자리)' % (lba, size))

    plan = []
    for n, boxes in sorted(SCREENS.items()):
        print(' 화면 state%d:' % n)
        S = load_state(n)
        plan += plan_screen(K, S['vdp2'], S['cram'], boxes)
    plan = dedup(plan)

    diff = [(o, b) for o, b in plan if K[o:o + 64] != b]
    nb = sum(sum(1 for k in range(64) if K[o + k] != b[k]) for o, b in diff)
    print('\n대상 셀 %d개, 내용이 바뀌는 셀 %d개, 바뀌는 바이트 %d개'
          % (len(plan), len(diff), nb))

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return
    write_plan(plan, K, lba, size, revert, resync)


if __name__ == '__main__':
    main()
