"""SCHOOL 내장 폰트(0x1C574)와 ASCMSCG 폰트를 글리프 단위로 대조.

- 어디서부터 갈라지는지, 몇 글리프가 다른지 집계
- 다른 글리프만 모아 시트로 렌더(판독용)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files

GSZ = 128           # 16x16 4bpp
SCHOOL_FONT = 0x1C574
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def find_font(data, name_hint=""):
    """ASCMSCG 같은 폰트 파일은 통짜 글리프 배열."""
    return data


def glyphs(data, off, n):
    return [data[off + i * GSZ: off + (i + 1) * GSZ] for i in range(n)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    school = get("/SCHOOL")
    ms = get("/ASCMSCG")
    n_ms = len(ms) // GSZ
    n_sc = (len(school) - SCHOOL_FONT) // GSZ
    print("ASCMSCG %d bytes = %d glyphs" % (len(ms), n_ms))
    print("SCHOOL font region %d bytes max = %d glyphs" % (len(school) - SCHOOL_FONT, n_sc))

    n = min(n_ms, n_sc, 1000)
    diff = []
    for i in range(n):
        a = ms[i * GSZ:(i + 1) * GSZ]
        b = school[SCHOOL_FONT + i * GSZ: SCHOOL_FONT + (i + 1) * GSZ]
        if a != b:
            diff.append(i)
    print("compared %d glyphs, differing: %d" % (n, len(diff)))
    if diff:
        print("first diff idx = %d, last = %d" % (diff[0], diff[-1]))
        # 연속 구간으로 요약
        runs = []
        s = diff[0]
        prev = diff[0]
        for i in diff[1:]:
            if i != prev + 1:
                runs.append((s, prev))
                s = i
            prev = i
        runs.append((s, prev))
        print("runs:", ", ".join("%d-%d" % r for r in runs[:40]))


if __name__ == "__main__":
    main()
