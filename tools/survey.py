"""파일 목록 집계 + TSV 저장."""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_sector, walk, read_range
import struct

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work")
os.makedirs(OUT, exist_ok=True)

with open(TRACK1, "rb") as f:
    pvd = read_sector(f, 16)
    root = pvd[156:156 + 34]
    rlba = struct.unpack_from("<I", root, 2)[0]
    rsize = struct.unpack_from("<I", root, 10)[0]
    files = walk(f, rlba, rsize)

with open(os.path.join(OUT, "files.tsv"), "w", encoding="utf-8") as w:
    w.write("path\tlba\tsize\tis_dir\n")
    for e in files:
        w.write("%s\t%d\t%d\t%d\n" % (e["path"], e["lba"], e["size"], 1 if e["dir"] else 0))

dirs = collections.Counter()
dsize = collections.Counter()
exts = collections.Counter()
esize = collections.Counter()
for e in files:
    if e["dir"]:
        continue
    d = os.path.dirname(e["path"])
    dirs[d] += 1
    dsize[d] += e["size"]
    ext = os.path.splitext(e["path"])[1].upper()
    exts[ext] += 1
    esize[ext] += e["size"]

print("=== 디렉터리별 ===")
for d, n in dirs.most_common():
    print("%-24s %6d files  %12d B" % (d if d else "/", n, dsize[d]))
print()
print("=== 확장자별 ===")
for x, n in exts.most_common():
    print("%-10s %6d files  %12d B" % (x if x else "(none)", n, esize[x]))
