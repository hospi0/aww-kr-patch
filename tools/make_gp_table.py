# -*- coding: utf-8 -*-
"""AWW 「분기 GP 보정치」 표 — 한국어판 (세션23).

원본: 일본어 공략 페이지의 GP 보정 표(経路 / 補正地点 / 補正値). 표 본문이 일본어로 남아 있어
번역해 다시 그린다. 숫자는 전부 **PLAN 번호**라 [[make_flowchart]]와 같은 규칙으로
`kr_s15.TITLES`(게임이 실제로 표시하는 한글 시나리오 제목)를 작은 글씨로 병기한다.

원문 대조:
    経路          補正地点            補正値
    5 & 6         8(7を通らない)      80に設定
    8 & 9 & 10    11 or 31            160に設定
    16            28                  250に設定
    23 & 49       24 or 50            450に設정
    35 & 38 & 41  42                  300に設定
    35 & 38       61                  400に設定
    10            54                  330に設定
    30            61                  400に設定

출력: work/aww_gp_table_kr.png (2배 슈퍼샘플링 후 축소)
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kr_s15 as K

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'aww_gp_table_kr.png')

SS = 2
FONT = r'C:\Windows\Fonts\malgun.ttf'
FONTB = r'C:\Windows\Fonts\malgunbd.ttf'

BG      = (255, 255, 255)
INK     = (38, 38, 38)
TITLE_C = (124, 42, 160)          # 원본 제목의 보라색
SUB     = (125, 125, 125)
HEAD_BG = (246, 244, 238)
EDGE    = (120, 120, 120)
GRID    = (196, 196, 196)
GP_C    = (0, 130, 60)

# (경로, 보정 지점, 보정값)  — 경로/지점의 숫자는 PLAN 번호
ROWS = [
    ([5, 6],        ('8', '7을 거치지 않을 것'), 80),
    ([8, 9, 10],    ('11 또는 31', None),        160),
    ([16],          ('28', None),                250),
    ([23, 49],      ('24 또는 50', None),        450),
    ([35, 38, 41],  ('42', None),                300),
    ([35, 38],      ('61', None),                400),
    ([10],          ('54', None),                330),
    ([30],          ('61', None),                400),
]

# 보정 지점 칸에 이름을 병기할 PLAN 번호(문자열에서 뽑기 번거로우니 명시)
SPOT_PLANS = [[8], [11, 31], [28], [24, 50], [42], [61], [54], [61]]

W, H = 1560, 1070
X0, X1, X2, X3 = 60, 640, 1160, 1500     # 열 경계
Y0 = 250                                  # 표 상단
RH = 88                                   # 행 높이
HH = 66                                   # 머리행 높이


def main():
    im = Image.new('RGB', (W * SS, H * SS), BG)
    d = ImageDraw.Draw(im)
    f_title = ImageFont.truetype(FONTB, 40 * SS)
    f_body = ImageFont.truetype(FONT, 25 * SS)
    f_head = ImageFont.truetype(FONTB, 27 * SS)
    f_num = ImageFont.truetype(FONTB, 30 * SS)
    f_ko = ImageFont.truetype(FONT, 19 * SS)
    f_gp = ImageFont.truetype(FONTB, 30 * SS)

    def S(v):
        return int(v * SS)

    def txt(xy, s, font, fill, an='lm'):
        d.text((S(xy[0]), S(xy[1])), s, font=font, fill=fill, anchor=an)

    def names(plans):
        return ' · '.join(K.TITLES[p] for p in plans)

    # ── 머리말
    txt((X0, 58), '분기 GP 보정치', f_title, TITLE_C)
    txt((X0, 118),
        '각 플랜의 큰 단위(40년 서부전선, 41·42년 동부전선 등)가 끝나는 지점에 체크포인트가 있다.',
        f_body, INK)
    txt((X0, 158),
        '그 시점에 일정 GP에 못 미치면 아래 표대로 GP가 보정된다.', f_body, INK)
    txt((X0, 200), '※ 숫자는 PLAN 번호 — 아래 작은 글씨는 한글패치가 표시하는 시나리오 제목',
        f_ko, SUB)

    # ── 표 격자
    ytop, ybot = Y0, Y0 + HH + RH * len(ROWS)
    d.rectangle([S(X0), S(ytop), S(X3), S(Y0 + HH)], fill=HEAD_BG)
    d.rectangle([S(X0), S(ytop), S(X3), S(ybot)], outline=EDGE, width=S(2))
    d.line([S(X0), S(Y0 + HH), S(X3), S(Y0 + HH)], fill=EDGE, width=S(2))
    for j in range(1, len(ROWS)):
        y = Y0 + HH + RH * j
        d.line([S(X0), S(y), S(X3), S(y)], fill=GRID, width=S(1))
    for x in (X1, X2):
        d.line([S(x), S(ytop), S(x), S(ybot)], fill=GRID, width=S(1))

    # ── 머리행
    for x, s in ((X0 + 24, '경로'), (X1 + 24, '보정 지점'), (X2 + 24, '보정값')):
        txt((x, Y0 + HH / 2), s, f_head, INK)

    # ── 본문
    for j, (route, (spot, note), val) in enumerate(ROWS):
        yc = Y0 + HH + RH * j + RH / 2
        # 경로
        txt((X0 + 24, yc - 15), ' & '.join(str(p) for p in route), f_num, INK)
        txt((X0 + 24, yc + 20), names(route), f_ko, SUB)
        # 보정 지점 — 숫자는 크게, 단서(「7을 거치지 않을 것」)는 작게 옆에
        txt((X1 + 24, yc - 15), spot, f_num, INK)
        if note:
            nx = X1 + 24 + d.textlength(spot, font=f_num) / SS + 14
            txt((nx, yc - 12), '(%s)' % note, f_body, SUB)
        txt((X1 + 24, yc + 20), names(SPOT_PLANS[j]), f_ko, SUB)
        # 보정값 — 값은 전부 10의 배수라 조사는 항상 「으로」
        txt((X2 + 24, yc - 2), '%d으로 설정' % val, f_gp, GP_C)

    im = im.resize((W, H), Image.LANCZOS)
    im.save(OUT)
    print('저장 ->', OUT, im.size)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
