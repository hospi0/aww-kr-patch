"""한글 폰트 후보를 게임 글리프 포맷(16x16 4bpp)으로 렌더해 원본 일본어와 나란히 비교."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from hangul import to_glyph, glyph_to_img

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "work", "extract", "ASCGSCG")
TEXT = "캠페인 모드 병기도감 이어하기"

# (라벨, 파일, ttc index, px, dy, gamma)
CANDS = [
    ("Gulim 16 (현재)",     r"C:\Windows\Fonts\gulim.ttc",   0, 16,  0, 1.0),
    ("GulimChe 16",         r"C:\Windows\Fonts\gulim.ttc",   1, 16,  0, 1.0),
    ("Dotum 16",            r"C:\Windows\Fonts\gulim.ttc",   2, 16,  0, 1.0),
    ("Batang 16",           r"C:\Windows\Fonts\batang.ttc",  0, 16,  0, 1.0),
    ("Malgun 14 AA",        r"C:\Windows\Fonts\malgun.ttf",  0, 14,  0, 1.0),
    ("Malgun 15 AA",        r"C:\Windows\Fonts\malgun.ttf",  0, 15,  0, 1.0),
    ("MalgunBold 14 AA",    r"C:\Windows\Fonts\malgunbd.ttf",0, 14,  0, 1.0),
    ("MalgunBold 15 AA",    r"C:\Windows\Fonts\malgunbd.ttf",0, 15,  0, 1.0),
    ("MalgunBold 15 γ0.7",  r"C:\Windows\Fonts\malgunbd.ttf",0, 15,  0, 0.7),
    ("NotoSansKR 15 AA",    r"C:\Windows\Fonts\NotoSansKR-VF.ttf", 0, 15, 0, 1.0),
    ("NotoSansKR 15 γ0.7",  r"C:\Windows\Fonts\NotoSansKR-VF.ttf", 0, 15, 0, 0.7),
]


def render_ch(ch, path, idx, px, dy, gamma):
    font = ImageFont.truetype(path, px, index=idx)
    img = Image.new("L", (16, 16), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((16 - w) / 2 - bb[0], (16 - h) / 2 - bb[1] + dy), ch, font=font, fill=255)
    return to_glyph(img, gamma)


def game_row(indices):
    d = open(GAME, "rb").read()
    return [d[i * 128:(i + 1) * 128] for i in indices]


def main():
    scale = 4
    # 원본 참조: キャンペーンモード (149,220,188,207,228,188,177,228,203)
    ref = game_row([149, 220, 188, 207, 228, 188, 177, 228, 203])
    rows = [("원본 일본어 (게임 폰트)", ref)]
    for label, path, idx, px, dy, gamma in CANDS:
        try:
            gs = [render_ch(c, path, idx, px, dy, gamma) if c != " "
                  else bytes(128) for c in TEXT]
        except Exception as e:
            print("skip %s: %s" % (label, e))
            continue
        rows.append((label, gs))

    lw = 210
    cw = 17 * scale
    W = lw + max(len(g) for _, g in rows) * cw + 10
    H = len(rows) * (17 * scale + 6) + 10
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    try:
        lab = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 15)
    except Exception:
        lab = None
    y = 6
    for label, gs in rows:
        dr.text((6, y + 14), label, font=lab, fill=(210, 210, 215))
        for k, g in enumerate(gs):
            im = glyph_to_img(g, scale)
            sheet.paste(im.convert("RGB"), (lw + k * cw, y))
        y += 17 * scale + 6
    out = os.path.join(ROOT, "work", "font_compare.png")
    sheet.save(out)
    print("->", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
