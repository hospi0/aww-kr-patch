"""전투 커맨드 버튼(32x16 4bpp)의 글자 영역에 얹을 한글 마스크 생성.

버튼 텍스처 구조(원본 실측):
  y=0        전부 투명(0)
  y=1        상단 하이라이트 테두리
  x=0        투명 / x=1 좌측 테두리 / x=31 우측 테두리
  y=15       하단 테두리
  글자 영역  x=2..30 (29px) * y=2..14 (13행) — 판 배경 0xb, 잉크 0x6

한 버튼 = 2음절이므로 음절 폭 14px(첫 음절 x2..15, 둘째 x16..29, x30은 여백).
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

GW, GH = 28, 13                   # 글자 영역 크기(두 배치 공통)
ORIGIN_A = (3, 2)                 # 테두리가 x1/y1에서 시작하는 배치(6개)
ORIGIN_B = (2, 1)                 # 1px 밀린 배치(休息·性能 — 첫 바이트가 0이 아니다)
SYL_W = 14                        # 음절 폭
PLATE = 0xB                       # 판 배경 색인
INK = 0x6                         # 잉크 색인

BUTTONS = [
    ("kougeki", 0x4E800, "공격"),
    ("kyusoku", 0x4E700, "휴식"),
    ("hengata", 0x4DE00, "변형"),
    ("hojuu", 0x4DA00, "보충"),
    ("kakyou", 0x4FE00, "가교"),      # LWRAM 소스 기준으로 build 쪽에서 재확인
    ("seinou", 0x4F500, "성능"),
    ("busou", 0x4E400, "무장"),
    ("chakuriku", 0x4E000, "착륙"),
]


def render_syllable(ch, fontpath, px, dx=0, dy=0, w=SYL_W, h=GH, bolden=0.0):
    """음절 하나를 w*h 그레이스케일로.

    작은 캔버스에 직접 그리면 글자가 잘린다(13행에 14px 글리프를 그려 「무」의
    ㅁ 윗획이 날아가 「부」로 읽혔다). 넉넉한 캔버스에 그린 뒤 실제 잉크 bbox로
    잘라 중앙에 놓는다.
    """
    ss = 4                                          # 슈퍼샘플 배율
    font = ImageFont.truetype(fontpath, px * ss)
    pad = px * ss * 2
    big = Image.new("L", (px * ss * 3, px * ss * 3), 0)
    ImageDraw.Draw(big).text((pad // 2, pad // 2), ch, font=font, fill=255)
    if bolden:
        # 4배 해상도에서 부풀린 뒤 축소 = 소수점 단위로 획 굵히기
        for _ in range(int(round(bolden * ss))):
            big = big.filter(ImageFilter.MaxFilter(3))
    bb = big.getbbox()
    if bb is None:
        return Image.new("L", (w, h), 0)
    ink = big.crop(bb)
    ink = ink.resize((max(1, round(ink.width / ss)), max(1, round(ink.height / ss))), Image.LANCZOS)
    if ink.width > w or ink.height > h:            # 그래도 넘치면 줄인다
        ink.thumbnail((w, h), Image.LANCZOS)
    img = Image.new("L", (w, h), 0)
    img.paste(ink, (round((w - ink.width) / 2 + dx), round((h - ink.height) / 2 + dy)))
    return img


def word_gray(word, fontpath, px, dx=0, dy=0, bolden=0.0):
    """2음절 단어를 글자 영역(28x13) 그레이스케일로."""
    out = Image.new("L", (GW, GH), 0)
    for i, ch in enumerate(word):
        out.paste(render_syllable(ch, fontpath, px, dx, dy, bolden=bolden), (i * SYL_W, 0))
    return out


def origin_of(jp_tex):
    """텍스처의 배치를 첫 바이트로 판별해 글자 영역 원점을 돌려준다."""
    return ORIGIN_A if jp_tex[0] == 0 else ORIGIN_B


def gray_to_indices(gray, threshold=None):
    """그레이스케일 -> 팔레트 색인(판 0xb ~ 잉크 0x6). threshold를 주면 2치화."""
    px = gray.load()
    rows = []
    for y in range(gray.height):
        row = []
        for x in range(gray.width):
            v = px[x, y] / 255.0
            if threshold is not None:
                v = 1.0 if v >= threshold else 0.0
            row.append(int(round(PLATE - v * (PLATE - INK))))
        rows.append(row)
    return rows


def apply_to_texture(jp_tex, rows):
    """원본 32x16 4bpp 텍스처의 글자 영역만 교체한 새 텍스처를 만든다."""
    out = bytearray(jp_tex)
    gx0, gy0 = origin_of(jp_tex)

    def setpx(x, y, val):
        i = y * 16 + x // 2
        out[i] = (out[i] & 0x0F) | (val << 4) if x % 2 == 0 else (out[i] & 0xF0) | val

    for y in range(GH):
        for x in range(GW):
            setpx(gx0 + x, gy0 + y, rows[y][x])
    return bytes(out)


def mask_bits(rows):
    """잉크 여부 1bpp 마스크 (행당 GW비트, 4바이트 정렬)."""
    out = bytearray()
    for row in rows:
        v = 0
        for x, c in enumerate(row):
            if c < PLATE:
                v |= 1 << (31 - x)
        out += v.to_bytes(4, "big")
    return bytes(out)
