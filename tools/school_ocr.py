"""SCHOOL 폰트 미판독 글리프 판독 — 매처 검증 후 적용.

1) validate : charmap 으로 이미 아는 한자 글리프에 매처를 돌려 top-1/top-5 정확도 측정
2) read     : 미판독 인덱스에 대해 후보 top-5 출력
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
from PIL import ImageFont
import charmap, kanji_ocr as K

SCHOOL_FONT = 0x1C574
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "validate"
    fontfile = sys.argv[2] if len(sys.argv) > 2 else r"C:\Windows\Fonts\msgothic.ttc"

    school = get("/SCHOOL")
    font = school[SCHOOL_FONT:]
    ttf = ImageFont.truetype(fontfile, 64)

    print("후보 집합 렌더 중...", file=sys.stderr)
    cands = K.build_candidates(ttf, K.jis_chars())
    print("후보 %d자" % len(cands), file=sys.stderr)

    if mode == "validate":
        # 한자 구간(256~819)에서 charmap 이 아는 글리프 표본
        known = [(i, charmap.CHARS[i]) for i in range(256, 820) if i in charmap.CHARS]
        step = max(1, len(known) // 120)
        sample = known[::step]
        t1 = t5 = 0
        misses = []
        for i, ch in sample:
            b = K.glyph_vec(font, i)
            if b is None:
                continue
            res = K.topk(b, cands, 5)
            names = [c for _, c in res]
            if names and names[0] == ch:
                t1 += 1
            elif ch in names:
                t5 += 1
                misses.append((i, ch, names))
            else:
                misses.append((i, ch, names))
        n = len(sample)
        print("표본 %d자  top1=%d(%.0f%%)  top5=%d(%.0f%%)" % (
            n, t1, 100 * t1 / n, t1 + t5, 100 * (t1 + t5) / n))
        print("\n-- 빗나간 것(앞 25) --")
        for i, ch, names in misses[:25]:
            print("  %3d 정답=%s  후보=%s" % (i, ch, " ".join(names)))

    else:
        lo = int(sys.argv[3], 0) if len(sys.argv) > 3 else 820
        hi = int(sys.argv[4], 0) if len(sys.argv) > 4 else 860
        for i in range(lo, hi):
            b = K.glyph_vec(font, i)
            if b is None:
                print("%3d  (빈 글리프)" % i)
                continue
            res = K.topk(b, cands, 6)
            print("%3d  %s" % (i, "  ".join("%s:%.2f" % (c, s) for s, c in res)))


if __name__ == "__main__":
    main()
