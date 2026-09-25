"""3차: 채택안을 '조금 가늘고 작게' 미세조정."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from hangul import render_kr, glyph_to_img

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "work", "extract", "ASCGSCG")
TEXT = "캠페인 모드 병기도감 이어하기"
MG = r"C:\Windows\Fonts\malgun.ttf"
MB = r"C:\Windows\Fonts\malgunbd.ttf"

VARIANTS = [
    ("현재: Bold 16 γ0.75",  dict(px=16, gamma=0.75, fontpath=MB)),
    ("Bold 15 γ0.85",        dict(px=15, gamma=0.85, fontpath=MB)),
    ("Bold 15 γ1.0",         dict(px=15, gamma=1.0,  fontpath=MB)),
    ("Bold 14 γ0.9",         dict(px=14, gamma=0.9,  fontpath=MB)),
    ("Bold 14 γ1.0",         dict(px=14, gamma=1.0,  fontpath=MB)),
    ("일반 15 γ0.75",        dict(px=15, gamma=0.75, fontpath=MG)),
    ("일반 15 γ0.85",        dict(px=15, gamma=0.85, fontpath=MG)),
    ("일반 16 γ0.8",         dict(px=16, gamma=0.8,  fontpath=MG)),
]


def main():
    scale = 5
    d = open(GAME, "rb").read()
    ref = [d[i * 128:(i + 1) * 128]
           for i in [149, 220, 188, 207, 228, 188, 177, 228, 203]]
    rows = [("원본 일본어", ref)]
    for label, kw in VARIANTS:
        rows.append((label, [render_kr(c, **kw) if c != " " else bytes(128)
                             for c in TEXT]))
    lw, cw = 180, 17 * scale
    W = lw + max(len(g) for _, g in rows) * cw + 10
    H = len(rows) * (17 * scale + 6) + 10
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    lab = ImageFont.truetype(MG, 15)
    y = 6
    for label, gs in rows:
        dr.text((6, y + 18), label, font=lab, fill=(210, 210, 215))
        for k, g in enumerate(gs):
            sheet.paste(glyph_to_img(g, scale).convert("RGB"), (lw + k * cw, y))
        y += 17 * scale + 6
    out = os.path.join(ROOT, "work", "font_compare3.png")
    sheet.save(out)
    print("->", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
