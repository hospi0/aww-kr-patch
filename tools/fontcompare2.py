"""2차 비교: 비트맵 자형 + 부드러움(4bpp 계조) 조합을 찾는다.

방법 A  비트맵 그대로 (하드 엣지)
방법 B  비트맵 + 약한 소프트닝 (게임 폰트의 AA 느낌 흉내)
방법 C  큰 크기 AA 렌더 후 축소(supersampling) — 작은 크기 직접 AA보다 자형이 산다
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from hangul import to_glyph, glyph_to_img

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "work", "extract", "ASCGSCG")
TEXT = "캠페인 모드 병기도감 이어하기"


def bmp(ch, path, idx, px, dy=0):
    font = ImageFont.truetype(path, px, index=idx)
    img = Image.new("L", (16, 16), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((16 - w) / 2 - bb[0], (16 - h) / 2 - bb[1] + dy), ch, font=font, fill=255)
    return img


def soften(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))


def supersample(ch, path, idx, px, ss=4, dy=0):
    S = 16 * ss
    font = ImageFont.truetype(path, px * ss, index=idx)
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S - w) / 2 - bb[0], (S - h) / 2 - bb[1] + dy * ss), ch, font=font, fill=255)
    return img.resize((16, 16), Image.LANCZOS)


GU = r"C:\Windows\Fonts\gulim.ttc"
BA = r"C:\Windows\Fonts\batang.ttc"
MG = r"C:\Windows\Fonts\malgun.ttf"
MB = r"C:\Windows\Fonts\malgunbd.ttf"

VARIANTS = [
    ("A 돋움16 (하드)",       lambda c: to_glyph(bmp(c, GU, 2, 16))),
    ("B 돋움16 +소프트0.4",   lambda c: to_glyph(soften(bmp(c, GU, 2, 16), 0.4))),
    ("B 돋움16 +소프트0.6",   lambda c: to_glyph(soften(bmp(c, GU, 2, 16), 0.6))),
    ("A 굴림16 (하드)",       lambda c: to_glyph(bmp(c, GU, 0, 16))),
    ("B 굴림16 +소프트0.5",   lambda c: to_glyph(soften(bmp(c, GU, 0, 16), 0.5))),
    ("A 바탕16 (하드)",       lambda c: to_glyph(bmp(c, BA, 0, 16))),
    ("B 바탕16 +소프트0.5",   lambda c: to_glyph(soften(bmp(c, BA, 0, 16), 0.5))),
    ("C 맑은고딕 SS16",       lambda c: to_glyph(supersample(c, MG, 0, 16))),
    ("C 맑은Bold SS16",       lambda c: to_glyph(supersample(c, MB, 0, 16))),
    ("C 맑은Bold SS16 γ0.75", lambda c: to_glyph(supersample(c, MB, 0, 16), 0.75)),
    ("C 맑은Bold SS15",       lambda c: to_glyph(supersample(c, MB, 0, 15))),
]


def main():
    scale = 4
    d = open(GAME, "rb").read()
    ref = [d[i * 128:(i + 1) * 128]
           for i in [149, 220, 188, 207, 228, 188, 177, 228, 203]]
    rows = [("원본 일본어 (게임 폰트)", ref)]
    for label, fn in VARIANTS:
        rows.append((label, [fn(c) if c != " " else bytes(128) for c in TEXT]))

    lw, cw = 200, 17 * scale
    W = lw + max(len(g) for _, g in rows) * cw + 10
    H = len(rows) * (17 * scale + 6) + 10
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    lab = ImageFont.truetype(MG, 15)
    y = 6
    for label, gs in rows:
        dr.text((6, y + 14), label, font=lab, fill=(210, 210, 215))
        for k, g in enumerate(gs):
            sheet.paste(glyph_to_img(g, scale).convert("RGB"), (lw + k * cw, y))
        y += 17 * scale + 6
    out = os.path.join(ROOT, "work", "font_compare2.png")
    sheet.save(out)
    print("->", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
