"""raw 데이터를 선형 비트맵으로 렌더(폭 탐색용)."""
import sys, os
from PIL import Image

def render(data, width, bpp, off, rows, scale, out):
    if bpp == 4:
        stride = width // 2
    elif bpp == 8:
        stride = width
    else:
        stride = width // 8
    avail = (len(data) - off) // stride
    rows = min(rows, avail)
    img = Image.new("L", (width, rows), 0)
    px = img.load()
    for y in range(rows):
        base = off + y * stride
        for x in range(width):
            if bpp == 4:
                b = data[base + x // 2]
                v = ((b >> 4) if x % 2 == 0 else (b & 15)) * 17
            elif bpp == 8:
                v = data[base + x]
            else:
                v = 255 * (data[base + x // 8] >> (7 - (x & 7)) & 1)
            px[x, y] = v
    img = img.resize((width * scale, rows * scale), Image.NEAREST)
    img.save(out)
    print("%s w=%d bpp=%d off=%d rows=%d" % (os.path.basename(out), width, bpp, off, rows))

if __name__ == "__main__":
    path = sys.argv[1]
    data = open(path, "rb").read()
    for spec in sys.argv[2:]:
        w, bpp, off, rows, scale = [int(v, 0) for v in spec.split(",")]
        out = "%s_lin_w%d_b%d_o%d.png" % (os.path.splitext(path)[0], w, bpp, off)
        render(data, w, bpp, off, rows, scale, out)
