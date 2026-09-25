"""문맥 후보 소수집합 안에서 글리프를 고르는 매처 + 그 사용법 그대로의 검증.

validate : 이미 아는 글리프에 「정답 1 + 무작위 오답 29」를 주고 top-1 정확도 측정
rank     : 지정 인덱스에 대해 주어진 후보들의 점수를 출력
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
from PIL import ImageFont
import charmap, kanji_ocr as K

SCHOOL_FONT = 0x1C574


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    school = get("/SCHOOL")
    font = school[SCHOOL_FONT:]
    ttf = ImageFont.truetype(r"C:\Windows\Fonts\msgothic.ttc", 64)
    r = K.Renderer(ttf)

    if mode == "validate":
        pool = [c for c in K.jis_chars() if 0x4E00 <= ord(c) <= 0x9FA5]
        known = [(i, charmap.CHARS[i]) for i in range(256, 820)
                 if i in charmap.CHARS and 0x4E00 <= ord(charmap.CHARS[i]) <= 0x9FA5]
        random.seed(7)
        nset = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        t1 = t3 = 0
        n = 0
        misses = []
        for i, ch in known:
            gv = K.glyph_vec(font, i)
            if gv is None:
                continue
            cands = {ch: r.vec(ch)}
            for d in random.sample(pool, nset - 1):
                v = r.vec(d)
                if v:
                    cands[d] = v
            res = K.topk(gv, cands, 3)
            names = [c for _, c in res]
            n += 1
            if names[0] == ch:
                t1 += 1
            elif ch in names:
                t3 += 1
                misses.append((i, ch, names))
            else:
                misses.append((i, ch, names))
        print("후보 %d개 중 고르기 — 표본 %d자  top1=%d(%.0f%%)  top3=%d(%.0f%%)" % (
            nset, n, t1, 100 * t1 / n, t1 + t3, 100 * (t1 + t3) / n))
        print("\n-- 빗나간 것(앞 20) --")
        for i, ch, names in misses[:20]:
            print("  %3d 정답=%s  후보=%s" % (i, ch, " ".join(names)))

    else:
        idx = int(sys.argv[2], 0)
        chars = sys.argv[3]
        gv = K.glyph_vec(font, idx)
        rows = []
        for ch in chars:
            v = r.vec(ch)
            if v:
                rows.append((K.score(gv, v), ch))
        rows.sort(reverse=True)
        print("glyph %d:  %s" % (idx, "  ".join("%s=%.3f" % (c, s) for s, c in rows)))


if __name__ == "__main__":
    main()
