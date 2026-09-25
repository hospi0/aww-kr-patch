"""파일별 바이트열 검색 (미디어 디렉터리 제외)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, "work", "files.tsv")
SKIP_DIRS = ("/BGM/", "/ADVERTIS/", "/SE/")


def files(skip_media=True):
    out = []
    with open(TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            p, lba, size, isdir = line.rstrip("\n").split("\t")
            if isdir == "1":
                continue
            if skip_media and any(p.startswith(d) for d in SKIP_DIRS):
                continue
            out.append((p, int(lba), int(size)))
    return out


def scan(patterns, skip_media=True, limit_per_pat=60):
    lst = files(skip_media)
    total = sum(s for _, _, s in lst)
    print("scanning %d files, %.1f MB" % (len(lst), total / 1e6), file=sys.stderr)
    hits = {p: [] for p in patterns}
    with open(TRACK1, "rb") as f:
        for p, lba, size in lst:
            if size == 0:
                continue
            data = read_range(f, lba, size)
            for pat in patterns:
                start = 0
                while True:
                    i = data.find(pat, start)
                    if i < 0:
                        break
                    hits[pat].append((p, i))
                    start = i + 1
    return hits


if __name__ == "__main__":
    pats = [bytes.fromhex(a) for a in sys.argv[1:]]
    hits = scan(pats)
    for pat, hs in hits.items():
        print("=== %s : %d hits ===" % (pat.hex(" "), len(hs)))
        seen = {}
        for p, i in hs:
            seen.setdefault(p, []).append(i)
        for p, offs in list(seen.items())[:40]:
            print("   %-30s x%-4d  first=0x%x" % (p, len(offs), offs[0]))
