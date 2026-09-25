"""1bpp 폰트 후보를 PNG 시트로 렌더."""
import sys, os
from PIL import Image

def render(path, w, h, cols=64, start=0, count=None, out=None):
    data = open(path, "rb").read()
    stride = (w + 7) // 8
    gsz = stride * h
    total = len(data) // gsz
    if count is None:
        count = total - start
    count = min(count, total - start)
    rows = (count + cols - 1) // cols
    img = Image.new("L", (cols * w, rows * h), 0)
    px = img.load()
    for i in range(count):
        g = data[(start + i) * gsz:(start + i + 1) * gsz]
        gx = (i % cols) * w
        gy = (i // cols) * h
        for y in range(h):
            for x in range(w):
                b = g[y * stride + x // 8]
                if b >> (7 - (x & 7)) & 1:
                    px[gx + x, gy + y] = 255
    out = out or (os.path.splitext(path)[0] + "_%dx%d.png" % (w, h))
    img.save(out)
    print("%s -> %s  glyphs=%d/%d (%dx%d, %dB/glyph)" % (
        os.path.basename(path), os.path.basename(out), count, total, w, h, gsz))

if __name__ == "__main__":
    p = sys.argv[1]
    w = int(sys.argv[2]); h = int(sys.argv[3])
    cnt = int(sys.argv[4]) if len(sys.argv) > 4 else 512
    st = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    render(p, w, h, count=cnt, start=st)
