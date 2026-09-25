"""ISO에서 파일 추출."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, "work", "files.tsv")


def load_index():
    idx = {}
    with open(TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            p, lba, size, isdir = line.rstrip("\n").split("\t")
            if isdir == "1":
                continue
            idx.setdefault(p, (int(lba), int(size)))
    return idx


def extract(paths, outdir):
    idx = load_index()
    os.makedirs(outdir, exist_ok=True)
    with open(TRACK1, "rb") as f:
        for p in paths:
            if p not in idx:
                print("MISSING", p)
                continue
            lba, size = idx[p]
            data = read_range(f, lba, size)
            name = p.strip("/").replace("/", "_")
            with open(os.path.join(outdir, name), "wb") as w:
                w.write(data)
            print("%-30s %8d B  (lba %d)" % (name, len(data), lba))


if __name__ == "__main__":
    out = os.path.join(ROOT, "work", "extract")
    extract(sys.argv[1:], out)
