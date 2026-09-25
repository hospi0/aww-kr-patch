"""새턴 8x8 셀 조립 가설로 폰트 렌더."""
import sys, os
from PIL import Image

def build(data, gw, gh, bpp, order, count, start, cols, scale, out):
    tw = th = 8
    tx = gw // tw; ty = gh // th
    tsz = tw * th * bpp // 8
    gsz = tsz * tx * ty
    total = len(data) // gsz
    count = min(count, max(0, total - start))
    rows = max(1, (count + cols - 1) // cols)
    img = Image.new("L", (cols * (gw + 1), rows * (gh + 1)), 48)
    px = img.load()
    for i in range(count):
        g = data[(start + i) * gsz:(start + i + 1) * gsz]
        ox = (i % cols) * (gw + 1); oy = (i // cols) * (gh + 1)
        for t in range(tx * ty):
            if order == "row":      # 좌->우, 위->아래
                cx, cy = t % tx, t // tx
            else:                    # "col": 위->아래, 좌->우
                cx, cy = t // ty, t % ty
            tile = g[t * tsz:(t + 1) * tsz]
            for y in range(th):
                for x in range(tw):
                    if bpp == 4:
                        b = tile[y * (tw // 2) + x // 2]
                        v = ((b >> 4) if x % 2 == 0 else (b & 15)) * 17
                    else:
                        v = 255 * (tile[y * (tw // 8) + x // 8] >> (7 - (x & 7)) & 1)
                    px[ox + cx * tw + x, oy + cy * th + y] = v
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(out)
    print("%s  glyph %dx%d bpp%d order=%s  %dB/glyph total=%d" % (
        os.path.basename(out), gw, gh, bpp, order, gsz, total))

if __name__ == "__main__":
    path = sys.argv[1]
    data = open(path, "rb").read()
    for spec in sys.argv[2:]:
        gw, gh, bpp, order, count, start, cols, scale = spec.split(",")
        out = "%s_tile%sx%s_b%s_%s_s%s.png" % (os.path.splitext(path)[0], gw, gh, bpp, order, start)
        build(data, int(gw), int(gh), int(bpp), order, int(count), int(start), int(cols), int(scale), out)
