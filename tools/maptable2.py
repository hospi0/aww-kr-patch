"""글리프->문자 매핑 추정 v2: 회색조 정규화상관 + 오프셋 탐색.

결과는 후보다. 실제 텍스트 디코드의 일본어 자연스러움으로 교차검증한다.
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

GSZ = 128
S = 16


def game_glyphs(path):
    data = open(path, "rb").read()
    n = len(data) // GSZ
    out = np.zeros((n, S, S), dtype=np.float32)
    for i in range(n):
        g = data[i * GSZ:(i + 1) * GSZ]
        for t in range(4):
            cx, cy = (t % 2) * 8, (t // 2) * 8
            tile = g[t * 32:(t + 1) * 32]
            for y in range(8):
                for x in range(8):
                    b = tile[y * 4 + x // 2]
                    v = (b >> 4) if x % 2 == 0 else (b & 15)
                    out[i, cy + y, cx + x] = v / 15.0
    return out


def candidate_chars():
    chars = [chr(c) for c in range(0x21, 0x7F)]
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


def render_refs(chars, fontpath, px):
    """각 문자를 (2S x 2S) 캔버스 중앙에 그려 반환 -> 오프셋 탐색용."""
    font = ImageFont.truetype(fontpath, px)
    big = 2 * S
    out, keep = [], []
    for ch in chars:
        img = Image.new("L", (big, big), 0)
        d = ImageDraw.Draw(img)
        try:
            bb = d.textbbox((0, 0), ch, font=font)
        except Exception:
            continue
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if w <= 0 or h <= 0:
            continue
        d.text(((big - w) / 2 - bb[0], (big - h) / 2 - bb[1]), ch, font=font, fill=255)
        a = np.asarray(img, dtype=np.float32) / 255.0
        if a.sum() == 0:
            continue
        out.append(a); keep.append(ch)
    return keep, np.stack(out)


def zncc_batch(refs_win, g):
    """refs_win (M,256) vs g (256,) 정규화 상관."""
    r = refs_win - refs_win.mean(1, keepdims=True)
    gg = g - g.mean()
    num = r @ gg
    den = np.sqrt((r * r).sum(1) * (gg * gg).sum()) + 1e-9
    return num / den


def main(cgpath, fontpath, out, px=16, span=3):
    glyphs = game_glyphs(cgpath)
    chars = candidate_chars()
    keep, R = render_refs(chars, fontpath, px)
    print("glyphs=%d refs=%d" % (len(glyphs), len(keep)), file=sys.stderr)

    # 오프셋별 윈도우 스택
    offsets = [(dy, dx) for dy in range(-span, span + 1) for dx in range(-span, span + 1)]
    wins = []
    for dy, dx in offsets:
        y0 = S // 2 + dy; x0 = S // 2 + dx
        wins.append(R[:, y0:y0 + S, x0:x0 + S].reshape(len(keep), -1))

    table = []
    for i in range(len(glyphs)):
        g = glyphs[i].reshape(-1)
        if g.sum() == 0:
            table.append({"idx": i, "char": " ", "score": 1.0, "alt": []})
            continue
        best = None
        for w in wins:
            sc = zncc_batch(w, g)
            if best is None:
                best = sc
            else:
                np.maximum(best, sc, out=best)
        order = np.argsort(-best)[:6]
        table.append({"idx": i, "char": keep[order[0]],
                      "score": round(float(best[order[0]]), 4),
                      "alt": [keep[j] for j in order[1:]]})
        if i % 100 == 0:
            print("  %d" % i, file=sys.stderr)
    json.dump(table, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3],
         px=int(sys.argv[4]) if len(sys.argv) > 4 else 16)
