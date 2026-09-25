"""SCHOOL 텍스트가 실제로 쓰는 글리프 인덱스를 집계하고, 판독 안 된 것들을 시트로 렌더."""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap
from PIL import Image, ImageDraw

GSZ = 128
SCHOOL_FONT = 0x1C574
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def render_indices(font, idxs, out, cols=16, scale=3, labels=True):
    w = h = 16
    cell_h = h + (10 if labels else 1)
    rows = (len(idxs) + cols - 1) // cols
    img = Image.new("RGB", (cols * (w + 2), rows * cell_h), (30, 30, 30))
    px = img.load()
    for k, gi in enumerate(idxs):
        g = font[gi * GSZ:(gi + 1) * GSZ]
        gx = (k % cols) * (w + 2)
        gy = (k // cols) * cell_h
        for y in range(h):
            for x in range(w):
                b = g[y * 8 + x // 2]
                v = ((b >> 4) if x % 2 == 0 else (b & 15)) * 17
                px[gx + x, gy + y] = (v, v, v)
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    if labels:
        d = ImageDraw.Draw(img)
        for k, gi in enumerate(idxs):
            gx = (k % cols) * (w + 2) * scale
            gy = ((k // cols) * cell_h + h) * scale
            d.text((gx + 2, gy), str(gi), fill=(255, 220, 80))
    img.save(out)
    print("wrote", out, len(idxs), "glyphs")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    school = get("/SCHOOL")
    font = school[SCHOOL_FONT:]
    mode = sys.argv[1] if len(sys.argv) > 1 else "census"

    if mode == "census":
        # 텍스트 영역 전체를 훑어 쓰이는 인덱스 집계
        lo, hi = 0x38000, 0x50000
        cnt = collections.Counter()
        for i in range(lo, hi, 2):
            v = int.from_bytes(school[i:i + 2], "big")
            if v <= 900:
                cnt[v] += 1
        used = sorted(cnt)
        print("used indices: %d distinct, max=%d" % (len(used), max(used)))
        unread = [i for i in used if i not in charmap.CHARS]
        print("unread (%d): %s" % (len(unread), unread))
        render_indices(font, list(range(800, 880)), os.path.join(ROOT, "work", "school_glyphs_800_880.png"))
    else:
        a = int(sys.argv[2], 0)
        b = int(sys.argv[3], 0)
        cols = int(sys.argv[4]) if len(sys.argv) > 4 else 8
        scale = int(sys.argv[5]) if len(sys.argv) > 5 else 8
        render_indices(font, list(range(a, b)), os.path.join(ROOT, "work", "school_glyphs_%d_%d.png" % (a, b)),
                       cols=cols, scale=scale)


if __name__ == "__main__":
    main()
