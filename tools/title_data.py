# -*- coding: utf-8 -*-
"""설정 메뉴 타이틀 `設定変更` 한글화 — 주입 데이터(4bpp 글자영역).

세션11에서 이 타이틀은 타일맵 텍스트가 아니라 **VDP1 스프라이트**로 확정됐다
(cmd#8 srca=0x9090 → VDP1 0x48480, size=0x0d20 = 104×32 4bpp = 1,664B).
디스크 모듈엔 압축 저장이라 무압축 검색이 안 되므로, 세션7 버튼과 **같은 우회**를 쓴다:
텍스처 업로더가 읽는 memmove 리터럴을 가로채 **LWRAM 소스를 제자리로 덧칠**한다.

★소스 주소 정정: 세션11 메모의 `0x002B01E8`은 틀렸다. 실제는 **`0x002B0180`** —
  버튼 풀(0x2AD780 + 42×0x100 = 0x2B0180) 바로 뒤에 붙어 있다. setmenu 세이브스테이트에서
  LWRAM 0x2B0180의 1,664B가 VDP1 0x48480과 **완전 일치**함을 확인했다.

덧칠 영역 = x18~81(64px, **짝수 시작**) × y8~22(15행). 원본 글자는 x19~80이지만 양옆
x18·x81은 원본이 전부 판 색이라 같이 칠해도 무변화이고, 짝수 폭이라 **마스크가 그대로
4bpp 픽셀 2개/바이트**로 떨어져 스텁이 행당 32바이트 단순 복사로 끝난다(480B).

★★색 = **팔레트가 16단계 그레이 램프**다(스프라이트 cmd8 CMDCOLR=0x6180 → CRAM 색번호
  0x180~0x18F). 1이 가장 밝고(E8E8E8) 15가 검정 — 즉 **색인 = 밝기 순서**.
  1차 빌드는 2bpp 4단계(1/13/14/15)로 했는데 **13·14는 명도 37·21로 사실상 검정**이라
  계조가 통째로 사라졌다(사용자 실기 지적). ⇒ 4bpp raw로 바꿔 원본과 같은 12~15단계를 쓴다.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KR_BIN = os.path.join(ROOT, "work", "title_kr_16px.bin")     # 세션11 확정 렌더(참고·비교용)

TEX_SRC = 0x002B0180            # LWRAM 텍스처 소스(관문 = 이 주소와 일치하는 복사만 가로챈다)
TEX_W, TEX_H = 104, 32
ROW = TEX_W // 2                # 52 바이트/행
TEX_SIZE = ROW * TEX_H          # 1664

X0, Y0 = 18, 8                  # 덧칠 원점(X0는 짝수)
PW, PH = 64, 15                 # 덧칠 폭/높이(픽셀)
ROW_BYTES = PW // 2             # 32 (4bpp)
MASK_SIZE = ROW_BYTES * PH      # 480
FIRST_OFF = Y0 * ROW + X0 // 2  # 425 = 첫 행의 텍스처 내 바이트 오프셋

GX0, GW, GH = 19, 14, 15        # 글자칸: x19부터 16px 피치, 각 14x15
PITCH = 16
TEXT = "설정변경"

FONT = "C:/Windows/Fonts/malgunbd.ttf"
FONT_PX = 16                    # 세션11 확정(사용자 승인). 옛 4단계 렌더와 대조해 재확인했다.
BOLDEN = 0.25                   # ss=4에서 MaxFilter 1회 — 옛 렌더(0.35 표기)와 결과 동일
# ★진하기는 굵기(BOLDEN)가 아니라 **감마**로 잡았다 — 세션7 교훈대로 MaxFilter를 한 단계 더
#   주면(=C안) 「설」·「경」의 속공간이 막힌다. 감마 0.75는 획을 안 굵히고 중간톤만 진하게 한다.
GAMMA = 0.75                    # 사용자 선택(B안)

# CRAM 색번호 0x180~0x18F 실측(setmenu 스테이트). 0번은 램프 밖(투명색).
PALETTE = [
    (0x58, 0x78, 0x40), (0xE8, 0xE8, 0xE8), (0xD8, 0xD8, 0xD8), (0xC8, 0xD0, 0xC8),
    (0xB8, 0xC0, 0xB8), (0xB0, 0xB8, 0xB8), (0x98, 0xA0, 0x98), (0x88, 0x90, 0x88),
    (0x78, 0x80, 0x70), (0x68, 0x70, 0x60), (0x50, 0x58, 0x50), (0x40, 0x48, 0x40),
    (0x30, 0x38, 0x30), (0x20, 0x28, 0x20), (0x10, 0x18, 0x10), (0x00, 0x00, 0x00),
]
RAMP = list(range(1, 16))       # 밝은 순 = 잉크(1) … 판(15)


def _lum(i):
    r, g, b = PALETTE[i]
    return 0.299 * r + 0.587 * g + 0.114 * b


def kr_texture():
    d = open(KR_BIN, "rb").read()
    if len(d) != TEX_SIZE:
        raise SystemExit("한글 텍스처 크기가 %d B가 아니다: %d" % (TEX_SIZE, len(d)))
    return d


def _px(buf, x, y):
    v = buf[y * ROW + x // 2]
    return (v >> 4) if x % 2 == 0 else (v & 0x0F)


def gray_to_index(g):
    """AA 그레이(0=판 … 255=잉크) -> 램프에서 가장 가까운 색인."""
    want = g / 255.0 * _lum(1)
    return min(RAMP, key=lambda i: abs(_lum(i) - want))


def indices(font=FONT, px=FONT_PX, bolden=BOLDEN, gamma=GAMMA):
    """덧칠 영역(64x15)의 팔레트 색인 배열. 글자칸 밖은 판 색(15)."""
    try:
        from . import btn_glyph as bg
    except ImportError:
        import btn_glyph as bg
    rows = [[15] * PW for _ in range(PH)]
    for i, ch in enumerate(TEXT):
        g = bg.render_syllable(ch, font, px, w=GW, h=GH, bolden=bolden).load()
        x0 = GX0 + i * PITCH - X0
        for y in range(GH):
            for x in range(GW):
                rows[y][x0 + x] = gray_to_index(255.0 * (g[x, y] / 255.0) ** gamma)
    return rows


def mask_bytes(font=FONT, px=FONT_PX, bolden=BOLDEN, gamma=GAMMA):
    """행당 32바이트 4bpp(상위 니블이 왼쪽 픽셀) — 스텁은 이걸 그대로 복사만 한다."""
    out = bytearray()
    for row in indices(font, px, bolden, gamma):
        for i in range(0, PW, 2):
            out.append((row[i] << 4) | row[i + 1])
    if len(out) != MASK_SIZE:
        raise SystemExit("마스크 크기 이상 %d" % len(out))
    return bytes(out)


def apply_ref(tex, mask):
    """스텁이 하는 일을 그대로 흉내낸다 — 텍스처 사본을 반환."""
    out = bytearray(tex)
    for r in range(PH):
        dst = FIRST_OFF + r * ROW
        out[dst:dst + ROW_BYTES] = mask[r * ROW_BYTES:(r + 1) * ROW_BYTES]
    return bytes(out)


def preview(texs, labels, scale=5, path=None):
    """팔레트 실색으로 여러 텍스처를 세로로 쌓아 미리보기."""
    from PIL import Image, ImageDraw
    gap = 3
    img = Image.new("RGB", (TEX_W, (TEX_H + gap) * len(texs)), (255, 0, 255))
    p = img.load()
    for k, tex in enumerate(texs):
        for y in range(TEX_H):
            for x in range(TEX_W):
                p[x, k * (TEX_H + gap) + y] = PALETTE[_px(tex, x, y)]
    img = img.resize((TEX_W * scale, img.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for k, lab in enumerate(labels):
        d.text((4, k * (TEX_H + gap) * scale + 2), lab, fill=(255, 255, 0))
    if path:
        img.save(path)
    return img
