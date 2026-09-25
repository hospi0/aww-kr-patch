# -*- coding: utf-8 -*-
"""AWW 맵 분기 차트 — 한국어판 재구성 (세션8).

원본: 일본어 공략 플로차트 「AWW マップ分岐チャート」(로드리게스 학급 OB회 제작, 420×629 GIF).
이걸 ①한국어로 번역하고 ②맵 이름을 **우리 한글패치가 실제로 표시하는 표기**로
바꿔 고해상도로 다시 그린다.

★세션23 개정: 시나리오 제목 한글화(16×16 GMSELDT)가 끝났으므로 **한글 제목이 주(主)**다.
  노드는 「한글 제목(크게, 굵게) → 로마자(작게, 회색)」 순으로 그린다.
  한글은 하드코딩하지 않고 `kr_s15.TITLES`(게임 화면에 실제로 찍히는 문자열)를 그대로 쓴다 —
  차트와 게임 화면이 다른 이름으로 같은 맵을 부르면 안 된다.
  로마자는 소형 8×8 미션명 풀이 **라틴 유지 확정**(2026-07-26)이라 게임에도 그대로 남아 있어
  아래 줄에 보조로 남긴다(`game_pool_kr.MISSIONS[i][1]`).

★검증된 사실: 원본 차트의 **PLAN 번호 = 게임 미션명 테이블(GAME 0x944ED)의 레코드 인덱스**와
  1:1로 일치한다(PLAN01=白作戦=Fall Weiss … PLAN64=完全なる勝利へ=Perfect Win, 64개 전수 대조).
  따라서 `game_pool_kr.MISSIONS[i]` 를 그대로 얹으면 된다.

노드 종류(원본 표기법 유지):
  마름모 = 승리 결과에 따른 분기 / 초록 타원 = 시나리오 분기 / 사각 = 일반 맵 / 스타디움 = 엔딩
  주황 숫자 = 분기에 필요한 누적 GP  /  초록 박스 숫자 = 그 거점에서 보정되는 GP

⚠️맑은고딕에는 学·会 같은 한자 글리프가 없다 → 크레딧까지 전부 한글로 적을 것(첫 렌더에서 □로 떴다).

출력: work/aww_flowchart_kr.png (2배 슈퍼샘플링 후 축소 = 안티에일리어싱)
"""
import os, sys, math
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_pool_kr as G
import kr_s15 as K

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'aww_flowchart_kr.png')

W, H = 2860, 3500
SS = 2                                    # 슈퍼샘플링 배율

FONT = r'C:\Windows\Fonts\malgun.ttf'
FONTB = r'C:\Windows\Fonts\malgunbd.ttf'

BG        = (255, 255, 255)
INK       = (38, 38, 38)
NODE_FILL = (255, 255, 216)
NODE_EDGE = (170, 170, 44)
ELL_FILL  = (198, 226, 108)
END_FILL  = (254, 226, 196)
END_EDGE  = (152, 112, 72)
LINE      = (178, 178, 50)
GP_ORANGE = (238, 118, 18)
GP_GREEN  = (0, 130, 60)
SUB       = (125, 125, 125)
KOC       = (95, 95, 95)

# ★한글 제목 = 게임이 실제로 표시하는 문자열(kr_s15.TITLES, 16×16 시나리오 제목 테이블).
#   인덱스는 PLAN 번호와 1:1(TITLES[0]=사관학교는 차트에 없는 튜토리얼이라 제외).
KO = {i: K.TITLES[i] for i in range(1, 65)}

ENDINGS = {
    1: '패전', 2: '국가 소멸', 3: '새로운 대립', 4: '그리고 전설로',
    5: '천년제국의 탄생', 6: '세계 신질서 구축', 7: '유럽국가의 탄생',
}

BOX = (340, 118)
DIA = (500, 186)
DIA2 = (780, 250)

N = {}


def box(i, x, y):
    N[i] = dict(x=x, y=y, kind='box')


def dia(k, x, y, a):
    N[k] = dict(x=x, y=y, kind='dia', a=a)


# ── ACT1 서부전선
box(1, 170, 420); box(2, 440, 420)
N['E1'] = dict(x=650, y=420, kind='ell')
box(4, 890, 350); box(3, 890, 490)
N['D56'] = dict(x=1500, y=420, kind='dia2', a=6, b=5)
N['G80'] = dict(x=1500, y=600, kind='gp', v='80')
box(7, 2160, 400)
# ── ACT2 영국
dia('D8', 420, 790, 8); dia('D9', 1080, 790, 9); dia('D10', 1740, 790, 10)
N['G330'] = dict(x=2420, y=870, kind='gp', v='330')
# ── ACT3 전역 분기
N['G160'] = dict(x=1080, y=960, kind='gp', v='160')
N['E2'] = dict(x=1080, y=1035, kind='ell')
box(31, 470, 1035); box(11, 1660, 1035); box(54, 2420, 1035)
# ── 좌: 동부전선
N['E3'] = dict(x=470, y=1135, kind='ell')
box(39, 230, 1235); box(40, 230, 1360); box(41, 230, 1485)
box(32, 720, 1235)
dia('D33', 720, 1395, 33)
N['E4'] = dict(x=1075, y=1525, kind='ell')
box(37, 430, 1635); box(36, 790, 1635); box(34, 1140, 1635)
dia('D38', 400, 1790, 38); dia('D35', 1120, 1790, 35)
N['G300'] = dict(x=400, y=1927, kind='gp', v='300')
box(42, 400, 2010)
dia('D43', 400, 2150, 43)
box(44, 1060, 2150)
dia('D45', 830, 2295, 45)
box(46, 230, 2300); box(47, 230, 2425); box(48, 230, 2550); box(49, 230, 2675)
box(21, 950, 2440); box(22, 950, 2565); box(23, 950, 2690)
N['G450'] = dict(x=380, y=2810, kind='gp', v='450')
N['E5'] = dict(x=380, y=2890, kind='ell')
dia('D50', 380, 3020, 50)
box(53, 185, 3200); box(51, 590, 3200)
box(24, 900, 2830)
dia('D25', 900, 3000, 25)
box(52, 960, 3200); box(26, 1330, 3120)
# ── 우: 지중해 → 남부
dia('D12', 1660, 1190, 12); dia('D15', 1660, 1400, 15); dia('D13', 2450, 1250, 13)
box(14, 2450, 1420)
box(17, 1720, 1550); box(18, 1720, 1670)
dia('D16', 2010, 1810, 16)
box(27, 2500, 1610)
N['G250'] = dict(x=2500, y=1740, kind='gp', v='250')
box(28, 2500, 1840)
box(19, 1780, 1930)
dia('D20', 1880, 2100, 20); dia('D55', 2520, 2160, 55)
box(29, 1700, 2235); box(30, 1700, 2355)
N['G400'] = dict(x=1700, y=2450, kind='gp', v='400')
box(61, 1700, 2530)
N['E6'] = dict(x=2520, y=2290, kind='ell')
box(56, 2320, 2390); box(58, 2660, 2390); box(59, 2660, 2510)
dia('D62', 1700, 2680, 62)
N['D5760'] = dict(x=2450, y=2710, kind='dia2', a=57, b=60)
box(63, 2130, 2880); box(64, 2130, 2995)
# ── 엔딩
for k, x in zip([4, 2, 1, 3, 5, 6, 7], [190, 570, 950, 1330, 1710, 2130, 2560]):
    N['END%d' % k] = dict(x=x, y=3350, kind='end', a=k)


def gsize(nd):
    return {'box': BOX, 'dia': DIA, 'dia2': DIA2,
            'ell': (74, 34), 'gp': (108, 54), 'end': (330, 104)}[nd['kind']]


def anchor(nid, side):
    nd = N[nid]
    w, h = gsize(nd)
    x, y = nd['x'], nd['y']
    return {'t': (x, y - h // 2), 'b': (x, y + h // 2),
            'l': (x - w // 2, y), 'r': (x + w // 2, y)}[side]


E = [
    ((1, 'r'), (2, 'l'), [], None, None),
    ((2, 'r'), ('E1', 'l'), [], None, None),
    (('E1', 'r'), (4, 'l'), [], None, None),
    (('E1', 'r'), (3, 'l'), [], None, None),
    ((4, 'r'), ('D56', 'l'), [(1090, 350), (1090, 420)], None, None),
    ((3, 'r'), ('D56', 'l'), [(1090, 490), (1090, 420)], None, None),
    (('D56', 'r'), (7, 'l'), [], '75 ~', 'mid'),
    (('D56', 'b'), ('G80', 't'), [], None, None),
    ((7, 'b'), ('D8', 't'), [(2160, 680), (420, 680)], None, None),
    (('D8', 'r'), ('D9', 'l'), [], '100 ~', 'mid'),
    (('D9', 'r'), ('D10', 'l'), [], '120 ~', 'mid'),
    (('D10', 'r'), ('G330', 't'), [(2420, 790)], '160 ~', 'start'),
    (('G330', 'b'), (54, 't'), [], None, None),
    (('D8', 'b'), ('G160', 't'), [(420, 915), (1080, 915)], None, None),
    (('D9', 'b'), ('G160', 't'), [(1080, 915)], None, None),
    (('D10', 'b'), ('G160', 't'), [(1740, 915), (1080, 915)], None, None),
    (('G160', 'b'), ('E2', 't'), [], None, None),
    (('E2', 'l'), (31, 'r'), [], None, None),
    (('E2', 'r'), (11, 'l'), [], None, None),
    # 동부전선
    ((31, 'b'), ('E3', 't'), [], None, None),
    (('E3', 'l'), (39, 't'), [(230, 1135)], None, None),
    (('E3', 'r'), (32, 't'), [(720, 1135)], None, None),
    ((39, 'b'), (40, 't'), [], None, None),
    ((40, 'b'), (41, 't'), [], None, None),
    ((32, 'b'), ('D33', 't'), [], None, None),
    (('D33', 'r'), ('E4', 't'), [(1075, 1395)], '200 ~', 'mid'),
    (('E4', 'l'), (36, 't'), [(790, 1525)], None, None),
    (('E4', 'b'), (34, 't'), [(1140, 1560)], None, None),
    ((36, 'l'), (37, 'r'), [], None, None),
    ((37, 'b'), ('D38', 't'), [(430, 1710), (400, 1710)], None, None),
    ((41, 'b'), ('D38', 'l'), [(230, 1790)], None, None),
    ((34, 'b'), ('D35', 't'), [(1140, 1710), (1120, 1710)], None, None),
    (('D38', 'b'), ('G300', 't'), [], None, None),
    (('G300', 'b'), (42, 't'), [], None, None),
    ((42, 'b'), ('D43', 't'), [], None, None),
    (('D38', 'r'), (44, 'l'), [(700, 1790), (700, 2150)], '400 ~', 'start'),
    (('D35', 'b'), (44, 't'), [(1120, 2030), (1060, 2030)], '400 ~', 'start'),
    (('D43', 'r'), (44, 'l'), [], '340 ~', 'mid'),
    ((44, 'b'), ('D45', 't'), [(1060, 2210), (830, 2210)], None, None),
    (('D45', 'l'), (47, 'r'), [(520, 2295), (520, 2425)], None, None),
    (('D45', 'b'), (21, 't'), [(830, 2360), (950, 2360)], None, None),
    ((21, 'b'), (22, 't'), [], None, None),
    ((22, 'b'), (23, 't'), [], None, None),
    (('D43', 'b'), (46, 't'), [(400, 2250), (230, 2250)], None, None),
    ((46, 'b'), (47, 't'), [], None, None),
    ((47, 'b'), (48, 't'), [], None, None),
    ((48, 'b'), (49, 't'), [], None, None),
    ((49, 'b'), ('G450', 't'), [(230, 2783), (380, 2783)], None, None),
    ((23, 'l'), ('G450', 'r'), [(620, 2690), (620, 2810)], None, None),
    (('G450', 'b'), ('E5', 't'), [], None, None),
    (('E5', 'b'), ('D50', 't'), [], None, None),
    (('E5', 'r'), (24, 'l'), [(640, 2890), (640, 2830)], None, None),
    ((24, 'b'), ('D25', 't'), [], None, None),
    (('D50', 'l'), (53, 't'), [(60, 3020), (60, 3120), (185, 3120)], '490 ~', (95, 2988)),
    (('D50', 'b'), (51, 't'), [(380, 3130), (590, 3130)], '471 ~ 489', (470, 3128)),
    (('D50', 'r'), (52, 't'), [(755, 3020), (755, 3120), (960, 3120)], '~ 470', (700, 2995)),
    (('D25', 'b'), (52, 't'), [(900, 3140), (960, 3140)], None, None),
    (('D25', 'r'), (26, 't'), [(1330, 3000)], '500 ~', 'mid'),
    ((51, 'r'), (52, 'l'), [], None, None),
    ((53, 'b'), ('END4', 't'), [(185, 3290), (190, 3290)], None, None),
    # ★엔딩2는 PLAN51이 아니라 PLAN52에서 나간다(원본 확인).
    ((52, 'b'), ('END2', 't'), [(960, 3280), (570, 3280)], None, None),
    ((52, 'b'), ('END1', 't'), [(960, 3290)], '501 ~', (1065, 3285)),
    ((26, 'b'), ('END3', 't'), [(1330, 3300)], None, None),
    # 지중해
    ((11, 'b'), ('D12', 't'), [], None, None),
    (('D12', 'r'), ('D13', 'l'), [(2060, 1190), (2060, 1250)], '200 ~', 'start'),
    (('D12', 'b'), ('D15', 't'), [], None, None),
    (('D15', 'r'), ('D13', 'b'), [(2160, 1400), (2160, 1350), (2450, 1350)], '210 ~', 'start'),
    (('D13', 'b'), (14, 't'), [], '220 ~', 'start'),
    (('D15', 'b'), (17, 't'), [(1660, 1480), (1720, 1480)], None, None),
    ((17, 'b'), (18, 't'), [], None, None),
    ((18, 'b'), ('D16', 't'), [(1720, 1730), (2010, 1730)], None, None),
    ((14, 'b'), (27, 't'), [(2450, 1510), (2500, 1510)], None, None),
    ((27, 'b'), ('G250', 't'), [], None, None),
    (('D16', 'r'), ('G250', 'l'), [(2340, 1810), (2340, 1740)], '250 ~', 'start'),
    (('G250', 'b'), (28, 't'), [], None, None),
    (('D16', 'b'), (19, 't'), [(2010, 1880), (1780, 1880)], None, None),
    ((19, 'b'), ('D20', 't'), [], None, None),
    (('D20', 'r'), ('D55', 'l'), [(2210, 2100), (2210, 2160)], '280 ~', 'start'),
    ((28, 'b'), ('D55', 't'), [(2500, 1990), (2520, 1990)], None, None),
    (('D20', 'b'), (29, 't'), [(1880, 2170), (1700, 2170)], None, None),
    ((29, 'b'), (30, 't'), [], None, None),
    ((30, 'b'), ('G400', 't'), [], None, None),
    (('G400', 'b'), (61, 't'), [], None, None),
    ((61, 'b'), ('D62', 't'), [], None, None),
    (('D45', 'r'), (30, 'l'), [(1400, 2295), (1400, 2355)], '400 ~', 'start'),
    (('D55', 'b'), ('E6', 't'), [], '380 ~', 'start'),
    (('E6', 'l'), (56, 't'), [(2320, 2290)], None, None),
    (('E6', 'r'), (58, 't'), [(2660, 2290)], None, None),
    ((58, 'b'), (59, 't'), [], None, None),
    ((56, 'b'), ('D5760', 't'), [(2320, 2555), (2450, 2555)], None, None),
    ((59, 'b'), ('D5760', 't'), [(2660, 2555), (2450, 2555)], None, None),
    (('D62', 'b'), ('END5', 't'), [(1700, 3290), (1710, 3290)], None, None),
    (('D62', 'r'), (63, 't'), [(1980, 2680), (1980, 2810), (2130, 2810)], '450 ~', (1900, 2648)),
    (('D5760', 'l'), (63, 't'), [(2130, 2710)], '451 ~', (2090, 2678)),
    ((63, 'b'), (64, 't'), [], None, None),
    ((64, 'b'), ('END6', 't'), [], None, None),
    (('D5760', 'b'), ('END7', 't'), [(2450, 3290), (2560, 3290)], None, None),
]


def main():
    im = Image.new('RGB', (W * SS, H * SS), BG)
    d = ImageDraw.Draw(im)
    f_title = ImageFont.truetype(FONTB, 58 * SS)
    f_cred = ImageFont.truetype(FONT, 25 * SS)
    f_leg = ImageFont.truetype(FONT, 27 * SS)
    f_num = ImageFont.truetype(FONT, 19 * SS)
    f_ko = ImageFont.truetype(FONTB, 33 * SS)        # ★주(主) = 한글 제목
    f_ko2 = ImageFont.truetype(FONTB, 29 * SS)       #   dia2(마름모 2단)용
    f_rom = ImageFont.truetype(FONT, 22 * SS)        # ★종(從) = 로마자
    f_gp = ImageFont.truetype(FONTB, 27 * SS)

    _fcache = {}

    def S(v):
        return int(v * SS)

    def ctext(xy, s, font, fill, an='mm'):
        d.text((S(xy[0]), S(xy[1])), s, font=font, fill=fill, anchor=an)

    def fit(s, font, maxw, bold=True):
        """maxw(원본좌표 px)를 넘으면 들어갈 때까지 폰트를 줄인다."""
        if d.textlength(s, font=font) <= S(maxw):
            return font
        path = FONTB if bold else FONT
        size = font.size // SS
        while size > 13:
            size -= 1
            f = _fcache.setdefault((path, size), ImageFont.truetype(path, size * SS))
            if d.textlength(s, font=f) <= S(maxw):
                return f
        return f

    def dia_w(w, h, dy):
        """마름모 중심에서 dy만큼 떨어진 높이의 가로 폭."""
        return max(40.0, w * (1.0 - 2.0 * abs(dy) / h))

    def poly(pts, fill, outline, w=3):
        p = [(S(a), S(b)) for a, b in pts]
        d.polygon(p, fill=fill)
        d.line(p + [p[0]], fill=outline, width=S(w), joint='curve')

    def rrect(x, y, w, h, r, fill, outline, wd=3):
        d.rounded_rectangle([S(x - w / 2), S(y - h / 2), S(x + w / 2), S(y + h / 2)],
                            radius=S(r), fill=fill, outline=outline, width=S(wd))

    def arrow(p0, p1, col):
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        L, Wd = 21, 9
        b1 = (p1[0] - L * math.cos(ang) + Wd * math.sin(ang),
              p1[1] - L * math.sin(ang) - Wd * math.cos(ang))
        b2 = (p1[0] - L * math.cos(ang) - Wd * math.sin(ang),
              p1[1] - L * math.sin(ang) + Wd * math.cos(ang))
        d.polygon([(S(p1[0]), S(p1[1])), (S(b1[0]), S(b1[1])), (S(b2[0]), S(b2[1]))], fill=col)

    # ── 헤더
    ctext((W / 2, 82), 'AWW  맵 분기 차트', f_title, (55, 55, 55))
    ctext((W / 2, 142),
          '원본: AWW 맵 분기 차트 (로드리게스 학급 OB회 제작)   ·   한국어판 재구성 — 맵 이름은 한글패치가 실제로 표시하는 표기',
          f_cred, SUB)
    lx = W / 2 - 640
    poly([(lx, 205), (lx + 46, 184), (lx + 92, 205), (lx + 46, 226)], NODE_FILL, NODE_EDGE)
    ctext((lx + 112, 205), '승리 결과에 따른 분기', f_leg, INK, 'lm')
    lx2 = lx + 480
    d.ellipse([S(lx2), S(191), S(lx2 + 72), S(219)], fill=ELL_FILL, outline=NODE_EDGE, width=S(3))
    ctext((lx2 + 92, 205), '시나리오 분기', f_leg, INK, 'lm')
    lx3 = lx2 + 300
    rrect(lx3 + 40, 205, 84, 44, 6, (255, 255, 255), GP_GREEN, 4)
    ctext((lx3 + 102, 205), '거점 GP 보정값', f_leg, INK, 'lm')
    ctext((W / 2, 262), '주황 숫자 = 분기에 필요한 누적 GP값', f_leg, GP_ORANGE)

    # ── 엣지(노드 아래). 라벨은 노드에 가리지 않도록 맨 마지막에 따로 그린다.
    labels = []
    for (a, b, mid, lab, lpos) in E:
        p0 = anchor(a[0], a[1])
        p1 = anchor(b[0], b[1])
        pts = [p0] + list(mid) + [p1]
        d.line([(S(x), S(y)) for x, y in pts], fill=LINE, width=S(3), joint='curve')
        arrow(pts[-2], pts[-1], LINE)
        if lab:
            if isinstance(lpos, tuple):          # 명시 좌표
                labels.append((lpos, lab))
            elif lpos == 'mid':
                labels.append((((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 26), lab))
            else:
                nxt = pts[1]
                labels.append((((p0[0] + nxt[0]) / 2, (p0[1] + nxt[1]) / 2 - 26), lab))

    # ── 노드
    for nid, nd in N.items():
        x, y, k = nd['x'], nd['y'], nd['kind']
        w, h = gsize(nd)
        if k == 'ell':
            d.ellipse([S(x - w / 2), S(y - h / 2), S(x + w / 2), S(y + h / 2)],
                      fill=ELL_FILL, outline=NODE_EDGE, width=S(3))
        elif k == 'gp':
            rrect(x, y, w, h, 6, (255, 255, 255), GP_GREEN, 4)
            ctext((x, y), nd['v'], f_gp, GP_GREEN)
        elif k == 'end':
            rrect(x, y, w, h, h / 2, END_FILL, END_EDGE, 4)
            ctext((x, y - 23), 'ENDING %d' % nd['a'], f_num, (135, 92, 58))
            ctext((x, y + 16), ENDINGS[nd['a']],
                  fit(ENDINGS[nd['a']], f_ko2, w - 40), (88, 48, 18))
        elif k == 'dia':
            poly([(x, y - h / 2), (x + w / 2, y), (x, y + h / 2), (x - w / 2, y)],
                 NODE_FILL, NODE_EDGE)
            i = nd['a']
            ctext((x, y - 42), 'PLAN%02d' % i, f_num, SUB)
            ctext((x, y - 8), KO[i], fit(KO[i], f_ko, dia_w(w, h, 8) - 30), INK)
            ctext((x, y + 32), G.MISSIONS[i][1], f_rom, KOC)
        elif k == 'dia2':
            poly([(x, y - h / 2), (x + w / 2, y), (x, y + h / 2), (x - w / 2, y)],
                 NODE_FILL, NODE_EDGE)
            for j, i in enumerate((nd['a'], nd['b'])):
                yy = y - 62 + j * 104
                ctext((x, yy), KO[i], fit(KO[i], f_ko2, dia_w(w, h, yy - y) - 30), INK)
                ctext((x, yy + 30), 'PLAN%02d   %s' % (i, G.MISSIONS[i][1]), f_rom, KOC)
        else:
            i = nd.get('a', nid)
            rrect(x, y, w, h, 12, NODE_FILL, NODE_EDGE, 3)
            ctext((x, y - 38), 'PLAN%02d' % i, f_num, SUB)
            ctext((x, y - 4), KO[i], fit(KO[i], f_ko, w - 28), INK)
            ctext((x, y + 34), G.MISSIONS[i][1], f_rom, KOC)

    # ── GP 라벨(최상단): 흰 배경을 깔아 선·노드 위에서도 읽히게
    for (pos, lab) in labels:
        bb = d.textbbox((S(pos[0]), S(pos[1])), lab, font=f_gp, anchor='mm')
        d.rectangle([bb[0] - S(6), bb[1] - S(3), bb[2] + S(6), bb[3] + S(3)], fill=BG)
        ctext(pos, lab, f_gp, GP_ORANGE)

    im = im.resize((W, H), Image.LANCZOS)
    im.save(OUT)
    print('저장 ->', OUT, im.size)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
