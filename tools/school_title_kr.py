# -*- coding: utf-8 -*-
"""사관학교 제목 그래픽(VDP2 NBG0 8bpp 타일) 한글 렌더 — 세션19.

★구조 (실측, /SCHOOL)
  · 그래픽 블록 base = 0x0678C4, 타일주소 = base + 타일번호*64 (8bpp 8x8 = 64B)
  · 배치 테이블 0x066A14~0x0678C0, 4B/셀 `0040 <charnum>`, 주소 = charnum*0x20
  · 제목은 **20타일 x 3행 = 160x24px**.
    ⇒ 첫 글자 3타일(x0~23) + **공유부 17타일(x24~159)**
    初/中/上 만 첫 글자가 다르고 `級戦闘講義` 는 세 제목이 **같은 타일을 공유**한다.
        初 : 타일 1,2,3 / 21,22,23 / 41,42,43
        中 : 타일 110,111,112 / 113,114,115 / 116,117,116
        上 : 타일 116,190,116 / 116,191,192 / 193,194,195   (116=빈타일 재사용)
        공유: 타일 4~20 / 24~40 / 44~60
  · 卒業試験 = 타일 252~292, **14타일 x 3행 = 112x24px**

★한글 대응이 글자수까지 정확히 맞는다
    初/中/上 + 級戦闘講義(5자)  →  초/중/상 + 급전투강의(5자)
    卒業試験(4자)              →  졸업시험(4자)
  ⇒ 원본의 「첫 글자만 교체」 구조를 그대로 유지한 채 한글화된다.

★렌더 (사용자 확정 2026-07-27): 맑은고딕 **Bold 20px**, 4배 슈퍼샘플링 후 LANCZOS 축소.
★★계조는 **원본이 실제로 쓰는 인덱스로만** 양자화한다(RAMP).
  🐞처음엔 커버리지를 0~127 로 **선형 매핑**했다가 실기에서 「글자 주변이 지저분」했다.
    8bpp 인덱스는 계조가 아니라 **팔레트 번호**라, 원본이 안 쓰는 값은 엉뚱한 색이 된다.
    원본 스샷 역산: idx0=RGB(105,99,92) 배경 / idx102=(105,98,90) 배경에 가까운 AA /
    idx127=(96,90,84) 획. 이 셋이 원본 제목 픽셀의 90%다.
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT = r'C:\Windows\Fonts\malgunbd.ttf'
PX = 20                 # 사용자 확정
SS = 4                  # 슈퍼샘플링 배수
PEAK = 127              # 원본 획 팔레트 인덱스
CELL = 8                # 타일 한 변
ROWS = 3                # 제목은 3행 고정 (24px)

BASE = 0x0678C4         # /SCHOOL 그래픽 블록 시작 (= 타일 0)

# 제목 = (첫글자, 공유부) — 첫글자는 3타일, 공유부는 17타일
TITLES = {
    '初': '초', '中': '중', '上': '상',
}
SHARED = '급전투강의'        # 級戦闘講義
SOTSU = '졸업시험'           # 卒業試験 (14타일 x 3행)

# 첫 글자 타일 배치 (행별).
#   ★원본은 中/上 의 모서리에 **공용 빈 타일 116**을 재사용한다(45곳이 참조).
#     한글 `중`(받침 ㅇ)·`상`(ㅅ)은 그 자리에 획이 오므로 그대로 두면 116 을 덮어
#     빈칸을 쓰는 45곳이 전부 깨진다. ⇒ **새 타일 837~841 로 돌린다.**
#   🐞세션19 는 이걸 **타일 329~333(파일 0x06CB04~)** 에 뒀다가 사고를 냈다.
#     그 자리가 「VRAM 에서 비어 있다」는 것만 보고 골랐는데, **졸업시험 화면이
#     같은 파일 영역을 다른 VRAM 주소로 로드해서** 화면 맨 위에 한글 조각이 떴다.
#     ★★/SCHOOL 은 **화면마다 로드 보정이 다르다**(제목 0x138C4 / 졸업시험 0x13B74).
#       그래서 VRAM 기준으로 비었는지 보면 안 되고 **파일 오프셋 기준**으로 봐야 한다.
#   ✅세션21 재선정: /SCHOOL 0x067000 이후 256B 이상 제로런은 4곳뿐이고, 그중
#     **파일 0x074A04~0x074B43(타일 837~841)** 은 제목·졸업시험 양쪽 참조 0 으로 실측됐다.
#   ⇒ 배치 테이블 4셀을 같이 고쳐야 한다(RETARGET 참조).
#   ✅세션21: 「상」을 **1px 오른쪽으로** 옮겨 좌상단 칸 침범을 0 으로 만들었다
#     (5픽셀뿐이었다). 그래서 새 타일이 5개→**4개**로 줄어 B0 안전구간에 딱 맞는다.
#     ★새 타일은 **B0 뱅크(VRAM 0x40000~0x5FFFF)** 안이어야 한다 — 원본 타일 0~328 이
#       전부 B0 다. B1(0x60000~)에 두면 NBG0 가 못 읽을 수 있다(세션21 에 하마터면 그럴 뻔).
FIRST_TILES = {
    '初': [[1, 2, 3], [21, 22, 23], [41, 42, 43]],
    '中': [[110, 111, 112], [113, 114, 115], [382, 117, 383]],
    '上': [[116, 190, 384], [385, 191, 192], [193, 194, 195]],
}

# 배치 테이블(0x066A14, 4B/셀) 에서 116 → 새 타일로 돌릴 셀. {셀번호: 새 타일번호}
#   셀160(上 좌상단)은 침범 0 이 되어 **원본 빈 타일 116 을 그대로 둔다.**
RETARGET = {120: 382, 122: 383, 162: 384, 180: 385}
# 세션19 가 잘못 쓴 옛 자리 — 원본(전부 0)으로 되돌려야 졸업시험 화면이 깨끗해진다
LEGACY_TILES = [329, 330, 331, 332, 333]
TABLE = 0x066A14
SHARED_TILES = [list(range(4, 21)), list(range(24, 41)), list(range(44, 61))]

# 卒業試験 = 20타일 폭 화면의 일부만 쓴다. **행마다 시작 열·폭이 다르다**(실측 배치표).
#   r0 c3~c16 = 타일253~266 / r1 c3~c15 = 267~279 / r2 c4~c16 = 280~292
#   나머지 칸은 전부 공용 빈 타일 116 ⇒ 그 자리에 획이 오면 안 된다.
SOTSU_LAYOUT = [
    (3, list(range(253, 267))),
    (3, list(range(267, 280))),
    (4, list(range(280, 293))),
]
SOTSU_W = 20            # 캔버스 폭(타일)

# ── 부제 4종 (16px 글자 2행). (원문, 한글, 폭타일, [행별 시작타일]) ──────────
#   ⚠️D(最終能力審査)는 3행이지만 **아래 8px 은 밑줄**이다 — r2(317~328)는 건드리지 않는다.
PX_SUB = 14             # 16px 셀 기준 (hangul.render_kr 기본과 같은 크기감)
SUBS = [
    ('兵器の移動と戦闘について',            '병기 이동과 전투에 대해',        24, [62, 86]),
    ('「兵器の補充」と「都市の占領」について', '「병기 보충」과「도시 점령」에 대해', 36, [118, 154]),
    ('「索敵効果」と「天候」について',        '「색적효과」와「날씨」에 대해',     28, [197, 225]),
    ('最終能力審査',                       '최종능력심사',                  12, [293, 305]),
]


# 원본이 실제로 쓰는 팔레트 인덱스만, **원본이 쓰는 계조 순서대로** 쓴다.
#   🐞1차: 0~127 선형 매핑 → 원본에 없는 인덱스가 엉뚱한 색 = 「지저분」(실기 지적).
#   🐞2차: 0/102/127 3단계 → AA 가 한 값뿐이라 대비가 급해 「너무 진함」(실기 지적).
#   ★원본 실측: 획(127) 24.4% / AA 32% / 배경 43.6% 이고, AA 는 **획 바로 옆 1px 에만**
#     102·55·80·88·119·116 등 **여러 값으로 흩어져** 깔린다(거리별 분포로 확인).
#     순서는 「127 이웃률」로 역산했다(낮을수록 배경 쪽 = 연함).
RAMP = [(0.00, 0), (0.20, 44), (0.35, 55), (0.50, 102),
        (0.65, 88), (0.78, 116), (0.90, 127)]


def _quant(v):
    """커버리지 0~1 → 원본 팔레트 인덱스."""
    out = RAMP[0][1]
    for thr, idx in RAMP:
        if v >= thr:
            out = idx
    return out


def _draw(text, w, h, gap=None, x0=0):
    """text 를 w x h 캔버스에 균등 배치해 0~PEAK 계조로 렌더."""
    img = Image.new('L', (w * SS, h * SS), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, PX * SS)
    n = len(text)
    step = gap if gap else (w - x0) / n
    for i, ch in enumerate(text):
        bb = d.textbbox((0, 0), ch, font=f)
        cw, chh = bb[2] - bb[0], bb[3] - bb[1]
        cx = (x0 + step * i + step / 2) * SS
        cy = (h / 2) * SS
        d.text((cx - cw / 2 - bb[0], cy - chh / 2 - bb[1]), ch, font=f, fill=255)
    im = img.resize((w, h), Image.LANCZOS)
    p = im.load()
    for y in range(h):
        for x in range(w):
            p[x, y] = _quant(p[x, y] / 255.0)
    return im


# 「상」만 1px 오른쪽으로 — 좌상단 칸(원본 빈 타일 116)을 침범하지 않게 한다.
FIRST_DX = {'상': 2}          # _draw 의 x0 (중심이 x0/2 만큼 이동한다)


def render_first(ch):
    """첫 글자 24x24 (3타일 x 3행)."""
    return _draw(ch, 24, 24, x0=FIRST_DX.get(ch, 0))


def render_shared():
    """공유부 `급전투강의` 136x24 (17타일 x 3행)."""
    return _draw(SHARED, 136, 24)


def render_sotsu():
    """`졸업시험` 을 20타일(160px) 캔버스에 그린다.

    ⚠️글자 영역을 **x32~127 로 좁힌다**. 배치표가 빈 타일 116 으로 두는 칸
      (r1 c16 = x128~, r2 c3 = x24~31) 에 획이 새면 116 을 덮게 되고,
      그 빈 타일을 참조하는 45곳이 전부 깨진다(sotsu_spill 로 관문).
    """
    return _draw(SOTSU, SOTSU_W * CELL, 24, gap=95 / len(SOTSU), x0=32)


def sotsu_tiles(im):
    """배치표대로 지정 열만 타일로 잘라낸다. {타일번호: 64B}"""
    out = {}
    for r, (c0, tiles) in enumerate(SOTSU_LAYOUT):
        for k, t in enumerate(tiles):
            b = bytearray(64)
            for y in range(CELL):
                for x in range(CELL):
                    b[y * CELL + x] = im.getpixel(((c0 + k) * CELL + x, r * CELL + y))
            out[t] = bytes(b)
    return out


def sotsu_spill(im):
    """배치표가 **빈 타일 116** 으로 두는 칸에 획이 새는지 검사 → [(r,c,잉크)]"""
    bad = []
    for r, (c0, tiles) in enumerate(SOTSU_LAYOUT):
        used = set(range(c0, c0 + len(tiles)))
        for c in range(SOTSU_W):
            if c in used:
                continue
            ink = sum(1 for y in range(CELL) for x in range(CELL)
                      if im.getpixel((c * CELL + x, r * CELL + y)) > 8)
            if ink:
                bad.append((r, c, ink))
    return bad


def to_tiles(im, tiles):
    """이미지 → {타일번호: 64B}. tiles 는 행별 타일번호 리스트."""
    out = {}
    for r, row in enumerate(tiles):
        for c, t in enumerate(row):
            if t in out:            # 같은 타일이 두 번 쓰이면(上의 116) 건너뛴다
                continue
            b = bytearray(64)
            for y in range(CELL):
                for x in range(CELL):
                    px_ = c * CELL + x
                    py = r * CELL + y
                    b[y * CELL + x] = im.getpixel((px_, py)) if (
                        px_ < im.width and py < im.height) else 0
            out[t] = bytes(b)
    return out


def render_sub(kr, wtiles):
    """부제 1줄 → (wtiles*8) x 16 이미지. 칸 수에 맞춰 균등 배치."""
    w = wtiles * CELL
    img = Image.new('L', (w * SS * 3, 16 * SS), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, PX_SUB * SS)
    # ★글자를 칸에 균등 배치하면 공백·괄호가 한 칸을 다 먹어 성기게 벌어지고
    #   「 가 왼쪽으로 밀려 잘린다. ⇒ **폰트 자연 자간으로 한 번에 그린 뒤 폭만 맞춘다.**
    #   원본 일본어도 가나·괄호는 좁고 한자는 넓은 비례 배치다.
    bb = d.textbbox((0, 0), kr, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((-bb[0], 8 * SS - th / 2 - bb[1]), kr, font=f, fill=255)
    img = img.crop((0, 0, max(1, tw), 16 * SS))
    im = img.resize((w, 16), Image.LANCZOS)
    p = im.load()
    for y in range(16):
        for x in range(w):
            p[x, y] = _quant(p[x, y] / 255.0)
    return im


def build_subs():
    """부제 4종 → {타일번호: 64B}."""
    out = {}
    for jp, kr, wt, starts in SUBS:
        # 관문: 글자당 폭. 원본도 14.9~16px/자 다(원문 `「索敵効果」と「天候」について`
        #       15자 / 224px = 14.9). 16px 고정으로 재면 멀쩡한 번역이 걸린다.
        per = wt * CELL / len(kr)
        if per < 14:
            raise SystemExit('★부제 %r %d자 → 글자당 %.1fpx (<14) — 줄여라' % (kr, len(kr), per))
        im = render_sub(kr, wt)
        for r, t0 in enumerate(starts):          # r0 = 위 8px, r1 = 아래 8px
            for c in range(wt):
                b = bytearray(64)
                for y in range(CELL):
                    for x in range(CELL):
                        b[y * CELL + x] = im.getpixel((c * CELL + x, r * CELL + y))
                out[t0 + c] = bytes(b)
    return out


def build():
    """{타일번호: 64B} 전체 계획. 관문 통과 못 하면 중단한다."""
    plan = {}
    for jp, kr in TITLES.items():
        im = render_first(kr)
        for r, row in enumerate(FIRST_TILES[jp]):        # 관문 ①: 공용 빈타일 침범 금지
            for c, t in enumerate(row):
                if t != 116:
                    continue
                ink = sum(1 for y in range(CELL) for x in range(CELL)
                          if im.getpixel((c * CELL + x, r * CELL + y)) > 8)
                if ink:
                    raise SystemExit('★%s r%dc%d 이 공용 빈타일 116 을 %dpx 침범' % (kr, r, c, ink))
        plan.update(to_tiles(im, FIRST_TILES[jp]))
    plan.update(to_tiles(render_shared(), SHARED_TILES))
    # ★上 만 3행째 c3 이 타일44 가 아니라 **196** 이다(원본 `上` 아래 가로획이 x24 까지
    #   넘어와 `級` 왼쪽과 섞인 전용 타일). 한글 `상` 은 3타일 안에 들어가므로
    #   196 은 공유부 첫 칸(44)과 같은 내용이면 된다. 안 채우면 상급에만 원본 잔재가
    #   노이즈로 남는다(사용자 실기 지적 2026-07-27). 196 은 셀203 한 곳만 참조 = 안전.
    plan[196] = plan[44]
    plan.update(build_subs())
    ims = render_sotsu()
    bad = sotsu_spill(ims)                               # 관문 ②
    if bad:
        raise SystemExit('★졸업시험이 빈타일 칸을 침범: %s' % bad)
    plan.update(sotsu_tiles(ims))
    # 관문 ③: 새 타일은 329~333 만 쓴다(그 밖은 원본 그래픽을 덮는다)
    for t in plan:
        if t > 328 and t not in RETARGET.values():
            raise SystemExit('★계획에 미승인 새 타일 %d' % t)
    return plan


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    p = build()
    print('타일 %d개' % len(p))
    print('  첫글자 초/중/상 + 공유 %r + %r' % (SHARED, SOTSU))
