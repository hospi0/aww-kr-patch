"""불확실한 글리프를 「게임 글리프 vs 후보 글자」 나란히 렌더해 눈으로 고르게 한다.

문맥으로 후보가 2~5개로 좁혀졌을 때만 쓴다(개방형 OCR 은 정확도 20%라 못 씀).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
from PIL import Image, ImageDraw, ImageFont
import kanji_ocr as K

SCHOOL_FONT = 0x1C574
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 8


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # 인자: "830:評獲合採満" 형태를 여러 개
    specs = [a.split(":") for a in sys.argv[1:]]
    school = get("/SCHOOL")
    font = school[SCHOOL_FONT:]
    ttf = ImageFont.truetype(r"C:\Windows\Fonts\msgothic.ttc", 16)

    maxc = max(len(c) for _, c in specs)
    cw = (16 + 2) * S
    img = Image.new("RGB", (cw * (maxc + 2), len(specs) * (cw + 14)), (25, 25, 25))
    d = ImageDraw.Draw(img)
    for r, (idx, cands) in enumerate(specs):
        i = int(idx)
        y = r * (cw + 14)
        g = K.glyph_img(font, i).resize((16 * S, 16 * S), Image.NEAREST)
        img.paste(g.convert("RGB"), (0, y))
        d.text((2, y + 16 * S + 1), "게임 %s" % idx, fill=(255, 210, 60))
        for c, ch in enumerate(cands):
            im = Image.new("L", (16, 16), 0)
            ImageDraw.Draw(im).text((0, 0), ch, fill=255, font=ttf)
            img.paste(im.resize((16 * S, 16 * S), Image.NEAREST).convert("RGB"),
                      ((c + 2) * cw, y))
            d.text(((c + 2) * cw + 2, y + 16 * S + 1), ch, fill=(120, 220, 255))
    out = os.path.join(ROOT, "work", "school_pick.png")
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
