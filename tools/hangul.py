"""한글 음절을 16x16 4bpp 게임 글리프(8x8 셀 4장, TL→TR→BL→BR)로 렌더."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

CELL = 16


def render_bitmap(ch, fontpath, px, dx=0, dy=0, index=0):
    font = ImageFont.truetype(fontpath, px, index=index)
    img = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    ox = (CELL - w) / 2 - bb[0] + dx
    oy = (CELL - h) / 2 - bb[1] + dy
    d.text((ox, oy), ch, font=font, fill=255)
    return img


def to_glyph(img, gamma=1.0):
    """16x16 L 이미지 -> 128바이트 게임 글리프."""
    px = img.load()
    out = bytearray(128)
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                v = px[cx + x, cy + y] / 255.0
                if gamma != 1.0:
                    v = v ** gamma
                n = min(15, int(round(v * 15)))
                i = t * 32 + y * 4 + x // 2
                if x % 2 == 0:
                    out[i] = (out[i] & 0x0F) | (n << 4)
                else:
                    out[i] = (out[i] & 0xF0) | n
    return bytes(out)


def to_glyph_dark(img, lo=0.12, hi=0.75, floor=4):
    """16x16 L 이미지 -> 128바이트 글리프. **어두운 계조만(floor~15) 사용.** (안 M3)

    ★세션13 근거: 게임 텍스트 팔레트는 **1=밝은회색(0x788078) … 15=검정** 내림 램프다
      (state1 CRAM pal0/pal7 실측). `to_glyph`처럼 커버리지를 0→15로 직매핑하면
      **AA 가장자리가 1~2 = 팔레트에서 가장 밝은 색**으로 나가서, 빨간 메시지 띠 위에서
      흰 후광처럼 지저분해진다(사용자 지적, 국가선택 화면 「계속할까요？」).
      원본 일본어 글리프는 이 램프를 「본체15 + 1px 밝은 외곽선1」로 쓰지만, 한글은 획이
      촘촘해 외곽선이 획 사이를 메워 무겁다 ⇒ **외곽선 없이 어두운 쪽 계조만** 쓴다.
      비교표 = tools/fontcompare4.py → work/font_compare4.png

    ⚠️**1차 파라미터(floor=8, lo=0.10, hi=0.55 = 안 H)는 실기에서 반려됐다** — 빨간 띠의
      후광은 사라졌지만 **메인메뉴 패널(회색 ≈0xB0)에서 글자가 뭉툭**해졌다. 이유 = 이 팔레트는
      **인덱스 1(0x78)조차 패널보다 어둡다** ⇒ 옅은 픽셀을 0x38로 눌러버리면 획이 사방으로
      두꺼워지고 속공간이 메워진다. ⇒ **안 M3 = floor 4(가장 옅은 값 0x60) + hi 0.75**
      (검정 문턱을 올려 굵기를 최초빌드 수준으로 되돌림).
      ★교훈: **한 배경(빨간 띠)만 보고 계조를 정하면 다른 배경(밝은 패널)이 망가진다.**
    """
    px = img.load()
    out = bytearray(128)
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                c = px[cx + x, cy + y] / 255.0
                if c < lo:
                    n = 0                            # 투명
                else:
                    v = (c - lo) / (hi - lo)
                    v = 0.0 if v < 0 else (1.0 if v > 1 else v)
                    n = min(15, floor + int(round(v * (15 - floor))))
                i = t * 32 + y * 4 + x // 2
                if x % 2 == 0:
                    out[i] = (out[i] & 0x0F) | (n << 4)
                else:
                    out[i] = (out[i] & 0xF0) | n
    return bytes(out)


def glyph_to_img(g, scale=1):
    img = Image.new("L", (CELL, CELL), 0)
    px = img.load()
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                b = g[t * 32 + y * 4 + x // 2]
                v = (b >> 4) if x % 2 == 0 else (b & 15)
                px[cx + x, cy + y] = v * 17
    if scale > 1:
        img = img.resize((CELL * scale, CELL * scale), Image.NEAREST)
    return img


# ── 채택된 한글 렌더 방식 ────────────────────────────────────────────────
# 맑은고딕 Bold를 4배 크기로 그린 뒤 LANCZOS로 16x16 축소(supersampling) + 감마 0.75.
#   · 16px에 직접 AA 렌더하면 「모드」가 「보느」로, 「도감」이 「노감」으로 뭉개진다
#     (ㅁ/ㅂ, ㄷ/ㄴ 구분 소실). 굵기가 얇은 Noto·일반 맑은고딕도 마찬가지.
#   · 굴림/돋움 비트맵은 자형은 정확하나 하드 엣지라 게임의 4bpp AA와 안 어울린다.
#   · 슈퍼샘플링은 자형을 살리면서 계조를 만들어 원본 일본어와 톤이 맞는다.
#   비교표: work/font_compare2.png (tools/fontcompare2.py로 재생성)
BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
REGULAR = r"C:\Windows\Fonts\malgun.ttf"


def render_kr(ch, px=14, ss=4, gamma=0.75, dy=0, fontpath=REGULAR, ramp='raw'):
    # 기본값 = 맑은고딕 **일반** 14px, 감마 0.75 (사용자 확정 2026-07-20).
    # 비교표 work/font_compare3.png 의 「일반 …」 계열.
    """한글 1자 -> 128바이트 게임 글리프.

    ramp='raw'  : 커버리지 0→15 직매핑(세션5~12 방식). 기존 빌드 재현용 = 기본값.
    ramp='dark' : 어두운 계조만(8~15) — 밝은 후광 제거(안 H, 세션13 사용자 확정).
                  ★새 폰트 빌드는 이걸 쓸 것. ASC16CG(build_ui16)는 아직 'raw'로
                  기록돼 있어(회귀 위험) 기본값을 안 바꿨다 — 재빌드할 때 함께 전환.
    """
    S = CELL * ss
    font = ImageFont.truetype(fontpath, px * ss)
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S - w) / 2 - bb[0], (S - h) / 2 - bb[1] + dy * ss), ch, font=font, fill=255)
    small = img.resize((CELL, CELL), Image.LANCZOS)
    if ramp == 'dark':
        return to_glyph_dark(small)
    return to_glyph(small, gamma)


def sheet(chars, fontpath, px, dx=0, dy=0, index=0, scale=6, out="preview.png"):
    cols = min(16, len(chars))
    rows = (len(chars) + cols - 1) // cols
    sh = Image.new("L", (cols * (CELL + 1), rows * (CELL + 1)), 40)
    for i, ch in enumerate(chars):
        g = to_glyph(render_bitmap(ch, fontpath, px, dx, dy, index))
        sh.paste(glyph_to_img(g), ((i % cols) * (CELL + 1), (i // cols) * (CELL + 1)))
    sh = sh.resize((sh.width * scale, sh.height * scale), Image.NEAREST)
    sh.save(out)
    print("%s  (%s %dpx dx=%d dy=%d idx=%d)" % (out, os.path.basename(fontpath), px, dx, dy, index))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    S = "저장로드아니오예본체카트리지게임을계속한다종료기록불러왔습시작합"
    for tag, fp, px, dy, idx in [
        ("gulim16", r"C:\Windows\Fonts\gulim.ttc", 16, 0, 0),
        ("gulim15", r"C:\Windows\Fonts\gulim.ttc", 15, 0, 0),
        ("malgun14", r"C:\Windows\Fonts\malgun.ttf", 14, 0, 0),
        ("batang16", r"C:\Windows\Fonts\batang.ttc", 16, 0, 0),
    ]:
        sheet(S, fp, px, dy=dy, index=idx, out="work/hg_%s.png" % tag)
