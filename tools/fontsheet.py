"""폰트 가설 대조 시트: 여러 (w,h,bpp) 조합을 확대 렌더."""
import sys, os
from PIL import Image

def render(data, w, h, bpp, cols, count, start, scale, out):
    if bpp == 1:
        gsz = ((w + 7) // 8) * h
    else:
        gsz = (w * h * bpp + 7) // 8
    total = len(data) // gsz
    count = min(count, max(0, total - start))
    rows = max(1, (count + cols - 1) // cols)
    img = Image.new("L", (cols * (w + 1), rows * (h + 1)), 40)
    px = img.load()
    for i in range(count):
        g = data[(start + i) * gsz:(start + i + 1) * gsz]
        gx = (i % cols) * (w + 1)
        gy = (i // cols) * (h + 1)
        for y in range(h):
            for x in range(w):
                if bpp == 1:
                    stride = (w + 7) // 8
                    bit = g[y * stride + x // 8] >> (7 - (x & 7)) & 1
                    v = 255 * bit
                elif bpp == 4:
                    stride = (w + 1) // 2
                    b = g[y * stride + x // 2]
                    v = ((b >> 4) if x % 2 == 0 else (b & 15)) * 17
                else:
                    v = g[y * w + x]
                px[gx + x, gy + y] = v
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(out)
    print("%s  %dx%d bpp%d  %dB/glyph  total=%d  shown=%d" % (
        os.path.basename(out), w, h, bpp, gsz, total, count))

if __name__ == "__main__":
    path = sys.argv[1]
    data = open(path, "rb").read()
    args = sys.argv[2:]
    for spec in args:
        w, h, bpp, cols, count, start, scale = [int(v) for v in spec.split(",")]
        out = "%s_%dx%d_b%d_s%d.png" % (os.path.splitext(path)[0], w, h, bpp, start)
        render(data, w, h, bpp, cols, count, start, scale, out)
