# -*- coding: utf-8 -*-
"""사관학교 **실기시험 브리핑 3화면**(초급·중급·상급) 한글화 — 세션21.

대상: `/KOUGI` state12(초급 /10) · state20(중급 /20) · state26(상급 /30).
사용자 제공 VDP2Viewer 스샷대로 **NBG0 / 8bpp / 타일 / 패턴네임 2워드 /
PNT @0x24000** — 강의 화면과 같은 구조다.

★★세션21 에 새로 알아낸 두 가지 (강의 빌더와 결정적으로 다르다)

① **VRAM→파일 보정(DELTA)은 화면마다 다르다.** 세션20 의 `-0x58F90` 은 화면1 전용.
   실측 state1 -0x58F90 / state2 -0x4FAE0 / state12 +0x9B80 / state20 +0x58300 /
   state26 +0x8ED60. 상수를 쓰면 엉뚱한 파일 위치를 읽어 화면이 노이즈로 덮이고,
   그대로 기록하면 **다른 강의 화면을 망가뜨린다.** ⇒ `derive_delta()` 로 매번 역산.

② **공유 타일이라도 「모든 사용처의 목표 그림이 같으면」 쓸 수 있다.**
   이 화면들은 텍스트가 타일 재사용으로 압축돼 있다 — 본문 2줄과 3줄의
   `色ユニットを` 가 같은 글자라 타일을 공유한다. 한글도 두 줄의 **같은 x 위치에
   같은 글자**가 오면(「파란 유닛을 …」/「빨간 유닛을 …」) 그대로 성립한다.
   ⇒ 화면 전체를 목표 이미지로 만든 뒤 **셀별 목표를 비교**해 판정한다.
      (강의 빌더의 「1회만 쓰이는 타일만」 규칙보다 훨씬 덜 잃는다.)

⚠️숫자(제한턴 값 · `/10` 등)는 그래픽 그대로 두고 **라벨만** 바꾼다.

빌드: python tools/build_exam.py            드라이런(+미리보기 PNG)
      python tools/build_exam.py --write    F: ISO 기록
      python tools/build_exam.py --revert   원상복구
"""
import os
import sys
import struct
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont

from build_kougi import (load_kougi, load_state, cells_of, derive_delta,
                         write_plan, PNT, CW, CH, GULIM, FONT_IDX)
from kougi_view import render

OUTDIR = r'C:\claude\project\aww-kr-patch\work\maps'

# ── 줄 정의 (전부 실측) ────────────────────────────────────────────────────
#   clr = 지울 픽셀 상자 (x0,y0,x1,y1)  ·  dy/x = 그릴 위치  ·  px = 폰트 크기
#   x=None 이면 지울 상자 안에서 가운데
# ★★패널 글자색은 **인덱스가 아니라 RGB 로 지정**하고, 그 줄 팔레트에서 최근접을 고른다.
#   🐞「그 줄 원본에서 가장 밝은 인덱스」를 쓰면 rgb(144,136,112) 같은 밝은 색이 나오는데,
#     실기 패널 배경이 **밝은 회색**이라 글자가 통째로 묻혀 안 보였다.
#     (내 미리보기는 NBG0 만 그려 배경이 검정이라 잘 보여서 못 잡았다 — 사용자가 잡아냈다.)
#   원본 글자 실측 = rgb(24,24,16) / (32,32,32) / (40,40,32) / (56,56,48) 의 어두운 회색.
PANEL_INK_RGB = (32, 32, 32)


def L(text, x0, y0, x1, y1, px=12, x=None, dy=None):
    return dict(text=text, clr=(x0, y0, x1, y1), px=px, x=x,
                dy=y0 if dy is None else dy)


#   ⚠️숫자도 원본은 **일본어 폰트의 전각 숫자**라 한글 옆에서 겉돈다 ⇒ 같이 다시 그린다.
#     세로 칸이 10px 뿐이라 숫자·라벨 줄은 11px 를 쓴다(12px 는 칸을 넘어
#     화면 전역 빈 배경 타일에 걸린다).
SCREENS = {
    12: dict(title='초급 실기시험', lines=[
        # 제목 상자 안쪽 x200~294 (테두리 x196/x298 은 건드리지 않는다)
        L('초급 실기시험', 198, 32, 296, 46, px=14),
        L('제한 턴', 200, 55, 258, 64, px=11, dy=56),
        L('3', 284, 55, 292, 64, px=11, dy=56),
        L('득', 201, 69, 213, 78, px=11), L('점', 223, 69, 235, 78, px=11),
        L('/10', 268, 69, 292, 78, px=11),
        L('', 189, 96, 291, 107),          # ★비움 — 원본 일본어만 지운다
        # ★두 줄의 같은 x 에 같은 글자가 오면 공유 타일을 그대로 쓸 수 있다.
        #   원본이 「青色…」/「赤色…」로 2번째 글자가 같아서 공유였다 ⇒ 한글도
        #   「청색」/「적색」으로 맞춰 충돌을 줄인다(「파란/빨간」은 경계가 어긋난다).
        L('청색 유닛을     지휘해', 176, 112, 309, 123, x=180),
        L('적색 유닛을     격파하라', 176, 128, 316, 139, x=180),
    ],
    map=[
        dict(box=(82, 38, 125, 56), text='적군', x=95, y=41, px=12),
        dict(box=(53, 89, 94, 107), text='아군', x=66, y=92, px=12),
    ],
    ),
    20: dict(title='중급 실기시험', lines=[
        L('중급 실기시험', 198, 32, 296, 46, px=14),
        L('제한 턴', 200, 55, 258, 64, px=11, dy=56),
        L('5', 284, 55, 292, 64, px=11, dy=56),
        L('득', 201, 69, 213, 79, px=11), L('점', 223, 69, 235, 79, px=11),
        L('/20', 268, 69, 292, 79, px=11),
        L('적의 진군을 저지하고', 196, 96, 303, 107, x=196, px=11),
        L('적의 거점을 점령하라', 196, 112, 297, 123, x=196, px=11),
        L('적 전멸도 가능', 197, 128, 271, 140, x=197, px=11),
    ],
    map=[
        dict(box=(24, 26, 110, 46), text='FPW와 보충에', x=34, y=30, px=12),
        dict(box=(26, 43, 120, 62), text='유의해 적 거점을', x=34, y=47, px=12),
        dict(box=(26, 57, 81, 75), text='점령하라', x=34, y=61, px=12),
        dict(box=(108, 65, 152, 83), text='거점', x=121, y=68, px=12),
        dict(box=(35, 126, 78, 145), text='거점', x=48, y=130, px=12),
    ],
    ),
    27: dict(title='졸업시험', file='/SCHOOL',
             state=(r'D:\hospi\RetroArch\states\Beetle Saturn\Advanced World War'
                    r' - Sennen Teikoku no Koubou - Last of the Millennium'
                    r' (Japan) (Rev B) (22M).state27'), lines=[
        L('졸업시험', 198, 32, 296, 46, px=14),
        L('제한 턴', 200, 55, 258, 64, px=11, dy=56),
        L('10', 278, 55, 292, 64, px=11, dy=56),
        L('득', 201, 69, 213, 78, px=11), L('점', 223, 69, 235, 78, px=11),
        L('/40', 268, 69, 292, 78, px=11),
        L('목표 도시 2곳을 점령하라', 180, 97, 314, 108, px=11),
    ],
    map=[
        dict(box=(30, 89, 109, 104), text='신속한 도하가', x=32, y=92, px=12),
        dict(box=(30, 105, 120, 121), text='승부처가 된다', x=32, y=108, px=12),
        dict(box=(30, 121, 121, 137), text='전술을 고려하라', x=32, y=124, px=12),
    ],
    ),
    # ★졸업시험은 **두 종류**다 — /40 짜리(state27)와 /100 짜리(이 화면).
    #   같은 「卒業試験」 제목이지만 제한턴·득점·본문·지도 문구가 전부 다르고,
    #   /SCHOOL 로드 보정도 다르다(0x13B74 vs 0x1AD64).
    100: dict(title='졸업시험(100점)', file='/SCHOOL',
              state=(r'D:\hospi\RetroArch\states\Beetle Saturn\Advanced World War'
                     r' - Sennen Teikoku no Koubou - Last of the Millennium'
                     r' (Japan) (Rev B) (22M).state1'), lines=[
        L('졸업시험', 198, 32, 296, 46, px=14),
        L('제한 턴', 200, 55, 258, 64, px=11, dy=56),
        L('10', 276, 55, 294, 64, px=11, dy=56),
        L('득', 201, 69, 213, 78, px=11), L('점', 223, 69, 235, 78, px=11),
        L('/100', 260, 69, 295, 78, px=11),
        L('목표 도시 2곳을 점령하라', 180, 96, 314, 107, px=11),
    ],
    map=[
        dict(box=(31, 117, 84, 133), text='적 2부대를', x=37, y=120, px=12),
        dict(box=(32, 133, 129, 149), text='어떻게 맞설까', x=38, y=136, px=12),
    ],
    ),
    26: dict(title='상급 실기시험', lines=[
        L('상급 실기시험', 198, 32, 296, 46, px=14),
        L('제한 턴', 200, 55, 258, 64, px=11, dy=56),
        L('8', 284, 55, 292, 64, px=11, dy=56),
        L('득', 201, 69, 213, 79, px=11), L('점', 223, 69, 235, 79, px=11),
        L('/30', 268, 69, 292, 79, px=11),
        # ★네 줄 모두 x174 로 **한 칸 들여쓰기**(사용자 확정).
        #   「단, 날씨」를 2줄에 붙일 자리가 없어(그 y 에서 손실 0 은 x271~274 뿐)
        #   **3줄로 합쳐** 문구를 재배분했다 — 그 결과 2~4줄이 전부 손실 0 이 됐다.
        L('제한 턴 안에 적 거점을', 170, 86, 325, 97, x=174),
        L('점령하라', 170, 102, 325, 113, x=174),
        L('날씨 악화 예상', 170, 118, 325, 129, x=174),
        L('색적에 주의하라', 170, 134, 325, 145, x=174),
    ],
    map=[
        dict(box=(98, 28, 152, 44), text='주의사항', x=106, y=31, px=12),
        dict(box=(98, 44, 152, 60), text='날씨변화', x=106, y=47, px=12),
        dict(box=(98, 61, 127, 76), text='색적', x=106, y=64, px=12),
    ],
    ),
}


def load_file(path):
    """ISO 에서 파일 하나를 통째로 읽는다(/KOUGI · /SCHOOL 등)."""
    import struct as _st
    from isoread import TRACK1, read_sector, walk, read_range
    f = open(TRACK1, 'rb')
    pvd = read_sector(f, 16)
    rl = _st.unpack_from('<I', pvd[156:190], 2)[0]
    rs = _st.unpack_from('<I', pvd[156:190], 10)[0]
    ent = {e['path']: e for e in walk(f, rl, rs) if not e['dir']}
    e = ent[path]
    return e, read_range(f, e['lba'], e['size'])


def load_ext(path):
    from vdp1_dump import load
    return load(path)


def font(px):
    return ImageFont.truetype(GULIM, px, index=FONT_IDX)


def plan_screen(K, S, spec, name):
    v2 = S['vdp2']
    cram = S['cram']
    cells = cells_of(v2)
    use = collections.Counter(a for a, _ in cells.values())
    用 = collections.defaultdict(list)
    for k, (a, w) in cells.items():
        用[a].append(k)
    DELTA = derive_delta(K, v2, cells, use)
    print(' %s: 보정 %s' % (name, hex(DELTA)))

    # 화면 전체를 인덱스 이미지로 펼친다 (목표 이미지를 여기서 만든다)
    W, H = CW * 8, CH * 8
    img = bytearray(W * H)
    oob = set()
    for cy in range(CH):
        for cx in range(CW):
            a = cells[(cx, cy)][0]
            # ⚠️전환 도중 스테이트는 캐릭터 주소가 VRAM 밖을 가리키는 셀이 섞인다.
            #   가드 없이 슬라이스하면 짧게 잘려 **목표가 원본과 달라지고**, 건드리지도
            #   않은 화면 하단이 통째로 「비움」 대상이 됐다(졸업시험에서 실제 발생).
            if a < 0 or a + 64 > len(v2):
                oob.add((cx, cy))
                continue
            for y in range(8):
                img[(cy * 8 + y) * W + cx * 8:(cy * 8 + y) * W + cx * 8 + 8] = \
                    v2[a + y * 8:a + y * 8 + 8]
    if oob:
        print('    ⚠️VRAM 밖을 가리키는 셀 %d개 — 대상에서 제외' % len(oob))
    before = bytes(img)

    def pal_rgb(cofs, i):
        w = struct.unpack_from('<H', cram, ((cofs + i) % 2048) * 2)[0]
        return ((w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8)

    # ★★「쓸 수 있는 픽셀」 지도 — 그 픽셀이 속한 셀이 **이 화면에서 1회만 쓰이는가**.
    #   🐞원본이 글자를 안 두던 자리는 **화면 전역 빈 배경 타일**(수백 곳 공유)이라
    #     거기 떨어진 획은 통째로 사라진다. 「한/턴/득/점」의 받침, 상급 2줄의
    #     「라」·「날」이 이렇게 잘렸다. ⇒ 그릴 위치를 이 지도에 맞춰 **자동으로 고른다.**
    #   ⚠️「공유면 전부 금지」로 잡으면 안 된다 — 본문 두 줄이 서로 공유하는 타일까지
    #     막혀 손실이 116px 로 폭증했다(멀쩡하던 배치가 나빠졌다). 진짜 못 쓰는 것은
    #     **원본이 통째로 비어 있는 공유 타일**뿐이다(거기 그리면 화면 수백 곳이 같이 바뀐다).
    touched = set()          # ★우리가 실제로 손댄 셀 — 이 밖은 절대 기록 대상이 아니다
    blank = set(a for a, st in 用.items()
                if 0 <= a and a + 64 <= len(v2)
                and len(st) > 1 and not any(v2[a:a + 64]))
    safe = [[cells[(x // 8, y // 8)][0] not in blank for x in range(W)]
            for y in range(H)]

    # ── 지도 위 라벨 ────────────────────────────────────────────────────
    #   패널과 달리 **지형 위에 얹힌 흰 글자 + 오른쪽아래 1px 그림자**다.
    #   배경이 0(검정)이 아니므로 지우려면 **주변 지형에서 보간**해야 한다
    #   (`tools/mapkr.py` 의 CGMMPO 인페인팅과 같은 사상).
    #   ✅지도 영역은 팔레트 오프셋이 0x500 하나뿐이라 색 계산이 단순하다.
    MCOFS = 0x500
    mink = min(range(1, 256), key=lambda i: -sum(pal_rgb(MCOFS, i)))   # 가장 흰 색
    mshadow = min(range(1, 256), key=lambda i: sum(pal_rgb(MCOFS, i)))  # 가장 어두운 색
    def is_glyph(v):
        r, g, b = pal_rgb(MCOFS, v)
        return min(r, g, b) >= 136 or max(r, g, b) <= 56

    # ★★두 패스로 나눈다 — 🐞상자를 넓히면서 위아래 라벨이 겹쳤고, **뒷줄 인페인팅이
    #   앞줄에 이미 그려 둔 한글의 아랫부분을 지웠다**(「유의해」가 깨진 진짜 원인).
    #   ⇒ ①모든 라벨을 먼저 지우고 ②그 다음에 전부 그린다.
    for ml in spec.get('map', []):
        mx0, my0, mx1, my1 = ml['box']
        # ⚠️밝기·무채색 어떤 판정으로도 **밝은 지형(모래·눈)과 글자가 안 갈린다**
        #   (상급 화면에서 x24~155 전체가 글자로 오판됐다). ⇒ 마스크를 포기하고
        #   **상자 안을 통째로** 메우되, 상자를 원본 글자에 **딱 맞게** 잡아
        #   지형 손상을 최소화한다.
        holes = [(x, y) for y in range(my0, my1 + 1) for x in range(mx0, mx1 + 1)
                 if 0 <= x < W and 0 <= y < H]
        hset = set(holes)
        src = [(x, y, img[y * W + x])
               for y in range(max(0, my0 - 3), min(H, my1 + 4))
               for x in range(max(0, mx0 - 3), min(W, mx1 + 4))
               if (x, y) not in hset]
        cnd = sorted(set(v for _, _, v in src))
        for x, y in holes:
            near = sorted(src, key=lambda t: (t[0] - x) ** 2 + (t[1] - y) ** 2)[:12]
            num = [0.0, 0.0, 0.0]
            den = 0.0
            for rx, ry, v in near:
                wt = 1.0 / (((rx - x) ** 2 + (ry - y) ** 2) + 0.5)
                den += wt
                c = pal_rgb(MCOFS, v)
                for k in range(3):
                    num[k] += c[k] * wt
            tgt = [n / den for n in num]
            img[y * W + x] = min(cnd, key=lambda i: sum(
                (a - b) ** 2 for a, b in zip(pal_rgb(MCOFS, i), tgt)))
            touched.add((x // 8, y // 8))

    for ml in spec.get('map', []):        # ── 2패스: 한글 그리기 ──
        mx0, my0, mx1, my1 = ml['box']
        # 한글 — 흰색 + 오른쪽아래 1px 그림자(원본과 같은 스타일)
        px_ = ml.get('px', 12)
        f = font(px_)
        bb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
            (0, 0), ml['text'], font=f)
        gw = bb[2] - bb[0]
        tx = ml.get('x', mx0 + 3)
        ty = ml.get('y', my0 + 3)
        can = Image.new('L', (W, H), 0)
        ImageDraw.Draw(can).text((tx - bb[0], ty - bb[1]), ml['text'],
                                 font=f, fill=255)
        strokes = [(x, y) for y in range(max(0, ty - 2), min(H, ty + px_ + 3))
                   for x in range(max(0, tx - 2), min(W, tx + gw + 3))
                   if can.getpixel((x, y)) >= 128]
        for x, y in strokes:
            if x + 1 < W and y + 1 < H:
                img[(y + 1) * W + x + 1] = mshadow
                touched.add(((x + 1) // 8, (y + 1) // 8))
        for x, y in strokes:
            img[y * W + x] = mink
            touched.add((x // 8, y // 8))
        print('    [지도] %-12s 원본 x%3d~%3d y%3d~%3d → 한글 %3dpx @x%3d y%3d %dpx'
              % (ml['text'], mx0, mx1, my0, my1, gw, tx, ty, px_))

    for ln in spec['lines']:
        x0, y0, x1, y1 = ln['clr']
        # ★글자색 = 그 줄 원본에서 **가장 밝은** 인덱스(패널 배경은 0)
        cofs = ((cells[(x0 // 8, y0 // 8)][1] >> 16) & 0x70) << 4
        cand = collections.Counter()
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                v = img[y * W + x]
                if v:
                    cand[v] += 1
        ink = (min(cand, key=lambda i: sum((a - b) ** 2 for a, b in
                                           zip(pal_rgb(cofs, i), PANEL_INK_RGB)))
               if cand else 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                img[y * W + x] = 0                     # 패널 배경 = 0
                touched.add((x // 8, y // 8))
        if not ln['text']:
            print('    %-22s (비움 — 원본만 지움) x%d~%d y%d~%d'
                  % ('', x0, x1, y0, y1))
            continue
        f = font(ln['px'])
        bb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
            (0, 0), ln['text'], font=f)
        gw = bb[2] - bb[0]
        avail = x1 - x0 + 1
        tx = ln['x'] if ln['x'] is not None else x0 + (avail - gw) // 2
        ty = ln['dy'] + ((y1 - ln['dy'] + 1) - (bb[3] - bb[1])) // 2
        # ★★세로가 칸을 넘으면 **화면 전역 빈 배경 타일**(0x05A000, 수백 곳 공유)에
        #   획이 걸려 그 부분이 통째로 사라진다. 🐞「제한 턴」이 12px 이라 10px 칸을
        #   1px 넘겨 y54(제목상자 아래 테두리 셀행)를 침범했고, 「턴」이 잘렸다.
        ty = max(ln['dy'], min(ty, y1 - (bb[3] - bb[1]) + 1))

        # ★손실(= 못 쓰는 칸에 떨어지는 획 픽셀 수)이 최소인 위치·크기를 고른다.
        def loss_of(px_, tx_, ty_):
            ff = font(px_)
            b2 = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
                (0, 0), ln['text'], font=ff)
            probe = Image.new('L', (W, H), 0)
            ImageDraw.Draw(probe).text((tx_ - b2[0], ty_ - b2[1]), ln['text'],
                                       font=ff, fill=255)
            n = 0
            for yy in range(max(0, ty_ - 2), min(H, ty_ + px_ + 3)):
                for xx in range(max(0, tx_ - 2), min(W, tx_ + (b2[2] - b2[0]) + 3)):
                    if probe.getpixel((xx, yy)) >= 128 and not safe[yy][xx]:
                        n += 1
            return n, (b2[2] - b2[0])

        best = None
        for px_ in (ln['px'], ln['px'] - 1):
            if px_ < 9:
                continue
            ff = font(px_)
            b2 = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
                (0, 0), ln['text'], font=ff)
            w2, h2 = b2[2] - b2[0], b2[3] - b2[1]
            # ⚠️x 를 명시한 줄은 **옮기지 않는다** — 두 줄이 한 타일을 공유하므로
            #   한 줄만 움직이면 「잃는 획」은 0이 되는 대신 **공유 충돌이 늘어난다**
            #   (실제로 17개까지 늘었다). 의도한 정렬은 그대로 두고 세로·크기만 맞춘다.
            xs = ([ln['x']] if ln['x'] is not None
                  else range(x0, max(x0 + 1, x1 - w2 + 2)))
            # ⚠️세로도 마찬가지 — 🐞두 줄 중 하나만 1px 올라가(112/127) 공유 타일에서
            #   픽셀이 어긋나 충돌이 1개→17개로 폭증했다. x 를 고정한 줄은 y 도 고정한다.
            # ⚠️하한을 dy 보다 **위로 내리면 안 된다** — 🐞1px 위(dy-1)를 후보에 넣었더니
            #   제목이 상자 위 테두리 셀행(cy3)을, 제한턴 숫자가 cy6 을 침범해
            #   **위쪽이 통째로 잘렸다**(사용자 지적). 아래로만 밀 수 있다.
            ys = ([ln['dy']] if ln['x'] is not None
                  else range(ln['dy'], ln['dy'] + 3))
            for ty_ in ys:
                for tx_ in xs:
                    n, _ = loss_of(px_, tx_, ty_)
                    if best is None or n < best[0]:
                        best = (n, px_, tx_, ty_, w2)
                    if n == 0:
                        break
                if best and best[0] == 0:
                    break
            if best and best[0] == 0:
                break
        if best:
            lossn, px_, tx, ty, gw = best
            f = font(px_)
            bb = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox(
                (0, 0), ln['text'], font=f)
            ln = dict(ln, px=px_)
        else:
            lossn = 0
        print('    %-22s 칸 %3dpx(x%3d~%3d) 글자 %3dpx @x%3d y%3d %2dpx  잃는획 %d%s'
              % (ln['text'], avail, x0, x1, gw, tx, ty, ln['px'], lossn,
                 '  ⚠️' if lossn else ''))
        can = Image.new('L', (W, H), 0)
        ImageDraw.Draw(can).text((tx - bb[0], ty - bb[1]), ln['text'],
                                 font=f, fill=255)
        for y in range(max(0, ty - 2), min(H, ty + ln['px'] + 3)):
            for x in range(max(0, tx - 2), min(W, tx + gw + 3)):
                if can.getpixel((x, y)) >= 128:
                    img[y * W + x] = ink
                    touched.add((x // 8, y // 8))

    # ── 셀별 목표 → 공유 타일 판정 ──────────────────────────────────────
    want = {}
    conflict = 0
    for a, sites in 用.items():
        # ★★손댄 셀이 하나도 없으면 건너뛴다. 🐞이 가드가 없으면 VRAM 밖 셀 때문에
        #   목표가 원본과 어긋난 것까지 「비움」 대상이 되어 **화면 하단 전체**가
        #   지워질 뻔했다(졸업시험 addr 0x054000, 사용처 308칸).
        if not (set(sites) & touched) or a < 0 or a + 64 > len(v2):
            continue
        bufs = []
        for cx, cy in sites:
            bufs.append(b''.join(
                bytes(img[(cy * 8 + y) * W + cx * 8:(cy * 8 + y) * W + cx * 8 + 8])
                for y in range(8)))
        ko = a + DELTA
        if ko < 0 or ko + 64 > len(K):
            continue
        orig = K[ko:ko + 64]
        if len(set(bufs)) != 1:
            conflict += 1
            # ★어느 자리가 왜 충돌하는지 반드시 찍는다 — 안 찍으면 화면에
            #   원본 조각이 남는데 원인을 못 찾는다(실제로 한 번 겪었다).
            #   충돌은 두 종류다:
            #   ㉠ **구조물 침범** — 사용처 중 손대지 않은 셀이 섞여 있다(테두리·빈 배경).
            #      글자가 남의 칸을 밟은 것이므로 **위치/크기를 고쳐 피해야** 한다.
            #   ㉡ **글자끼리 충돌** — 두 줄이 한 타일을 공유하는데 우리 글자가 서로 다르다.
            #      원본을 두면 일본어 조각이 남으므로 **배경으로 비운다**(획 일부 손실).
            if any(b == orig for b in bufs):
                print('      ⚠️구조물침범 addr=0x%06x 사용처 %s'
                      % (a, sorted(sites)[:8]))
            else:
                print('      ·글자충돌 addr=0x%06x %s → 배경으로 비움'
                      % (a, sorted(sites)))
                want[ko] = bytes(64)
            continue
        if bufs[0] != orig:
            want[ko] = bufs[0]
    print('    바뀌는 셀 %d개, 공유 충돌로 포기한 타일 %d개' % (len(want), conflict))
    # 미리보기 — 충돌로 못 쓴 타일은 원본이 남으므로 그것까지 반영해 그린다
    shown = bytearray(before)
    for a, sites in 用.items():
        ko = a + DELTA
        if ko in want:
            for cx, cy in sites:
                for y in range(8):
                    o = (cy * 8 + y) * W + cx * 8
                    shown[o:o + 8] = want[ko][y * 8:y * 8 + 8]
    return DELTA, want, bytes(shown), cells, cram


def preview(shown, cells, cram, path):
    W = CW * 8
    v = bytearray(max(a for a, _ in cells.values()) + 64)
    for (cx, cy), (a, w) in cells.items():
        for y in range(8):
            v[a + y * 8:a + y * 8 + 8] = shown[(cy * 8 + y) * W + cx * 8:
                                               (cy * 8 + y) * W + cx * 8 + 8]
    im = render(bytes(v), cram, cells)
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(path)
    print('    미리보기:', path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    files = {}
    plans = collections.defaultdict(list)
    for n, spec in sorted(SCREENS.items()):
        path = spec.get('file', '/KOUGI')
        if path not in files:
            files[path] = load_file(path)
        KE, K = files[path]
        S = (load_ext(spec['state']) if spec.get('state') else load_state(n))
        d, want, shown, cells, cram = plan_screen(K, S, spec,
                                                  'state%d %s' % (n, path))
        preview(shown, cells, cram,
                os.path.join(OUTDIR, '_시험%d_한글.png' % n))
        plans[path] += sorted(want.items())
    # 같은 파일 안에서 화면끼리 같은 오프셋을 건드리는지 확인
    total = 0
    for path in list(plans):
        seen = {}
        for o, b in plans[path]:
            if o in seen and seen[o] != b:
                raise SystemExit('%s 화면 간 충돌 @0x%x' % (path, o))
            seen[o] = b
        plans[path] = sorted(seen.items())
        total += len(plans[path])
        print('%-9s 대상 셀 %d개' % (path, len(plans[path])))
    print('총 대상 셀 %d개' % total)
    if not write:
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    for path in list(plans):
        KE, K = files[path]
        print('── %s 기록' % path)
        write_plan(plans[path], K, KE['lba'], KE['size'], revert, resync)


if __name__ == '__main__':
    main()
