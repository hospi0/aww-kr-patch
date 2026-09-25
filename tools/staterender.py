"""세이브스테이트에서 뽑은 VDP1 FB / VRAM 을 그림으로 뽑아본다.

용도: (1) 어느 화면의 스테이트인지 확인, (2) 작은 폰트(무기명) 글리프 시트 찾기.
⚠️ Mednafen은 u16 배열을 LE로 정규화해 저장하므로 새턴 메모리 순서로 보려면 swap16.
"""
import os, struct, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOB = os.path.join(ROOT, 'work', 'aww_state1.bin')
OUT = os.path.join(ROOT, 'work', 'state')


def read_named(data, name_off, namelen):
    p = name_off + namelen
    size = struct.unpack_from('<I', data, p)[0]
    return data[p + 4:p + 4 + size]


def swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def rgb555(b, w, h):
    im = Image.new('RGB', (w, h))
    px = im.load()
    for y in range(h):
        base = y * w * 2
        for x in range(w):
            v = (b[base + x * 2] << 8) | b[base + x * 2 + 1]
            px[x, y] = (((v >> 0) & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8)
    return im


def tiles4bpp(b, cell, cols, maxcells=None):
    """4bpp 셀(cell x cell)을 cols개씩 늘어놓은 시트. 상위/하위 니블 순서는 저니블=왼쪽."""
    bpc = cell * cell // 2
    n = len(b) // bpc
    if maxcells:
        n = min(n, maxcells)
    rows = (n + cols - 1) // cols
    im = Image.new('L', (cols * cell, rows * cell))
    px = im.load()
    for i in range(n):
        cx, cy = (i % cols) * cell, (i // cols) * cell
        o = i * bpc
        for y in range(cell):
            for x in range(0, cell, 2):
                v = b[o + y * (cell // 2) + x // 2]
                px[cx + x, cy + y] = (v & 15) * 17
                px[cx + x + 1, cy + y] = (v >> 4) * 17
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    data = open(BLOB, 'rb').read()
    what = sys.argv[1] if len(sys.argv) > 1 else 'fb'
    if what == 'fb':
        fb = read_named(data, 0xfb827 - 1, 9)   # name "&FB[0][0]"
        fb = swap16(fb)
        for w in (512, 1024):
            h = len(fb) // 2 // w
            rgb555(fb, w, h).save(os.path.join(OUT, f'fb_{w}.png'))
            print('fb', w, h)
    else:
        src = open(os.path.join(OUT, what + '.bin'), 'rb').read()
        src = swap16(src)
        cell = int(sys.argv[2]) if len(sys.argv) > 2 else 8
        cols = int(sys.argv[3]) if len(sys.argv) > 3 else 64
        tiles4bpp(src, cell, cols).save(os.path.join(OUT, f'{what}_{cell}px.png'))
        print('ok')


if __name__ == '__main__':
    main()
