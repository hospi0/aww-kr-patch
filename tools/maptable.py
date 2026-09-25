"""게임 폰트 글리프 <-> 문자 매핑을 시스템 일본어 폰트와의 이미지 매칭으로 추정.

주의: 이 결과는 '후보'다. 실제 텍스트 디코드 결과의 일본어 자연스러움으로 교차검증해야 한다.
"""
import os, sys, json
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GSZ = 128


def game_glyphs(path):
    data = open(path, "rb").read()
    n = len(data) // GSZ
    out = []
    for i in range(n):
        g = data[i * GSZ:(i + 1) * GSZ]
        bm = [[0] * 16 for _ in range(16)]
        for t in range(4):
            cx, cy = (t % 2) * 8, (t // 2) * 8
            tile = g[t * 32:(t + 1) * 32]
            for y in range(8):
                for x in range(8):
                    b = tile[y * 4 + x // 2]
                    v = (b >> 4) if x % 2 == 0 else (b & 15)
                    bm[cy + y][cx + x] = 1 if v >= 6 else 0
        out.append(bm)
    return out


def candidate_chars():
    chars = []
    # ASCII 반각/전각
    for c in range(0x20, 0x7F):
        chars.append(chr(c))
    # SJIS 2바이트 전 영역
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xF0)):
        for lo in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            try:
                ch = bytes([hi, lo]).decode("cp932")
            except Exception:
                continue
            if ch.isspace():
                continue
            chars.append(ch)
    return sorted(set(chars))


def render_char(ch, font, size=16):
    img = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(img)
    try:
        bb = d.textbbox((0, 0), ch, font=font)
    except Exception:
        return None
    w = bb[2] - bb[0]; h = bb[3] - bb[1]
    if w <= 0 or h <= 0:
        return None
    d.text(((size - w) / 2 - bb[0], (size - h) / 2 - bb[1]), ch, font=font, fill=255)
    px = img.load()
    return [[1 if px[x, y] >= 96 else 0 for x in range(size)] for y in range(size)]


def main(cgpath, fontpath, out):
    import numpy as np
    glyphs = np.array(game_glyphs(cgpath), dtype=np.float32).reshape(-1, 256)
    font = ImageFont.truetype(fontpath, 16)
    cands = candidate_chars()
    print("glyphs=%d candidates=%d" % (len(glyphs), len(cands)), file=sys.stderr)
    chars, mats = [], []
    for ch in cands:
        bm = render_char(ch, font)
        if bm is None:
            continue
        a = np.array(bm, dtype=np.float32).reshape(256)
        if a.sum() == 0:
            continue
        chars.append(ch); mats.append(a)
    R = np.stack(mats)                      # (M,256)
    print("usable refs=%d" % len(R), file=sys.stderr)
    rink = R.sum(1)                         # (M,)

    table = []
    for i in range(len(glyphs)):
        g = glyphs[i]
        gink = g.sum()
        if gink == 0:
            table.append({"idx": i, "char": " ", "score": 1.0, "alt": []})
            continue
        inter = R @ g                       # (M,)
        dice = 2.0 * inter / (rink + gink)
        same = 256.0 - (R.sum(1) + gink - 2 * inter)
        sc = dice * 0.8 + (same / 256.0) * 0.2
        order = np.argsort(-sc)[:5]
        table.append({"idx": i, "char": chars[order[0]],
                      "score": round(float(sc[order[0]]), 4),
                      "alt": [chars[j] for j in order[1:]]})
    json.dump(table, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
