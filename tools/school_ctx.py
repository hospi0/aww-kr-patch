"""미판독 글리프마다 등장 문맥을 전부 모아 출력 — 문맥으로 글자를 확정하기 위한 도구."""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap

SCHOOL_FONT = 0x1C574


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    lo = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x38E00
    hi = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x40000
    data = get("/SCHOOL")
    words = [int.from_bytes(data[i:i + 2], "big") for i in range(lo, hi, 2)]

    ctx = collections.defaultdict(list)
    for k, w in enumerate(words):
        if 820 <= w <= 1100 and w not in charmap.CHARS:
            s = charmap.decode(data, lo + max(0, k - 9) * 2, min(19, k + 10 - max(0, k - 9)))
            ctx[w].append(s.replace("\n", "/"))

    for w in sorted(ctx):
        seen = []
        for s in ctx[w]:
            if s not in seen:
                seen.append(s)
        print("=== %d (%d회) ===" % (w, len(ctx[w])))
        for s in seen[:6]:
            print("    " + s)


if __name__ == "__main__":
    main()
