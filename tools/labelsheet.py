"""미판독 글리프만 인덱스 라벨과 함께 크게 렌더 — 육안 판독용.

usage: python tools/labelsheet.py ASCIMCG out.png [--used /INTERM]
"""
import os, sys, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXD = os.path.join(ROOT, "work", "extract")
SCALE = 7
COLS = 12
CELL_W = 16 * SCALE + 8
CELL_H = 16 * SCALE + 22


def glyphs(name):
    d = open(os.path.join(EXD, name), "rb").read()
    return [d[i * 128:(i + 1) * 128] for i in range(len(d) // 128)]


def render_glyph(g):
    """16x16 = 8x8 셀 4장 TL->TR->BL->BR (row order), 4bpp."""
    im = Image.new("L", (16, 16), 0)
    px = im.load()
    for t in range(4):
        cx, cy = t % 2, t // 2          # row order: TL,TR,BL,BR
        tile = g[t * 32:(t + 1) * 32]
        for y in range(8):
            for x in range(8):
                b = tile[y * 4 + x // 2]
                v = ((b >> 4) if x % 2 == 0 else (b & 0xF)) * 17
                px[cx * 8 + x, cy * 8 + y] = v
    return im.resize((16 * SCALE, 16 * SCALE), Image.NEAREST)


def used_indices(module):
    from isoread import TRACK1, read_range
    from scan_files import files
    from findtext2 import records
    from poolfont import words_of
    lst = {p: (l, s) for p, l, s in files()}
    l, s = lst[module]
    with open(TRACK1, "rb") as f:
        d = read_range(f, l, s)
    ws = words_of(d, records(d))
    return set(w for w in ws if 1 <= w <= 0xFFEF)


def main():
    name = sys.argv[1]
    out = sys.argv[2]
    fm = json.load(io.open(os.path.join(ROOT, "work", "fontmaps.json"), encoding="utf-8"))
    gs = glyphs(name)
    mapped = set(int(k) for k in fm[name].keys())
    idxs = [i for i in range(len(gs)) if i not in mapped]
    if "--used" in sys.argv:
        mod = sys.argv[sys.argv.index("--used") + 1]
        u = used_indices(mod)
        idxs = [i for i in idxs if i in u]
    rows = (len(idxs) + COLS - 1) // COLS
    img = Image.new("RGB", (COLS * CELL_W, rows * CELL_H), (30, 30, 40))
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 16)
    except Exception:
        fnt = ImageFont.load_default()
    for k, gi in enumerate(idxs):
        r, c = divmod(k, COLS)
        x, y = c * CELL_W + 4, r * CELL_H + 2
        img.paste(render_glyph(gs[gi]).convert("RGB"), (x, y))
        d.text((x, y + 16 * SCALE + 2), str(gi), fill=(255, 230, 120), font=fnt)
    img.save(out)
    print("%s: 미판독%s %d개 -> %s (%dx%d)" % (
        name, "(used)" if "--used" in sys.argv else "", len(idxs), out, img.width, img.height))
    print("인덱스:", ", ".join(str(i) for i in idxs))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
