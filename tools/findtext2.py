"""텍스트 레코드 검출 v2.

레코드 = 0xFFFF로 끝나는 워드 런.
  - 런의 모든 워드가 유효 글리프(0..824) 또는 소프트 제어(0xFFF0..0xFFFE)
  - 길이 >= MIN_LEN
  - 가나(63..223) 워드가 MIN_KANA개 이상  <- 카운터 배열/그래픽 오탐 차단
  - 비공백 글리프 비율 >= MIN_DENS
"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap

MAXG = 824
MIN_LEN = 4
MIN_KANA = 2
MIN_DENS = 0.55
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def records(data):
    """[(start_byte, nwords, nchars)] — nwords는 0xFFFF 제외 길이."""
    n = len(data) // 2
    words = memoryview(data)[:n * 2]
    out = []
    run_start = None
    kana = dens = 0
    i = 0
    while i < n:
        v = (data[i * 2] << 8) | data[i * 2 + 1]
        if v == 0xFFFF:
            if run_start is not None:
                ln = i - run_start
                if ln >= MIN_LEN and kana >= MIN_KANA and dens >= MIN_DENS * ln:
                    out.append((run_start * 2, ln, dens))
            run_start, kana, dens = None, 0, 0
            i += 1
            continue
        ok = v <= MAXG or 0xFFF0 <= v <= 0xFFFE
        if not ok:
            run_start, kana, dens = None, 0, 0
            i += 1
            continue
        if run_start is None:
            run_start, kana, dens = i, 0, 0
        if 63 <= v <= 223:
            kana += 1
        if 1 <= v <= MAXG:
            dens += 1
        i += 1
    return out


def main():
    lst = files()
    rows = []
    seen_hash = {}
    with open(TRACK1, "rb") as f:
        for p, lba, size in lst:
            if size < 32:
                continue
            data = read_range(f, lba, size)
            rs = records(data)
            if not rs:
                continue
            chars = sum(r[2] for r in rs)
            # 파일 내용 해시로 중복 판정
            import hashlib
            h = hashlib.md5(data).hexdigest()
            rows.append((p, len(rs), chars, h))
    outp = os.path.join(ROOT, "work", "textmap2.tsv")
    uniq = {}
    for p, nr, ch, h in rows:
        uniq.setdefault(h, []).append((p, nr, ch))
    tot = sum(r[2] for r in rows)
    utot = sum(v[0][2] for v in uniq.values())
    with open(outp, "w", encoding="utf-8") as w:
        w.write("path\trecords\tchars\tmd5\n")
        for r in sorted(rows, key=lambda x: -x[2]):
            w.write("%s\t%d\t%d\t%s\n" % r)
    print("텍스트 보유 파일 %d개 / 고유 내용 %d종" % (len(rows), len(uniq)))
    print("총 문자수 %d  (중복 제거 후 %d)" % (tot, utot))
    print()
    print("%-28s %8s %9s" % ("path", "records", "chars"))
    for r in sorted(rows, key=lambda x: -x[2])[:30]:
        print("%-28s %8d %9d" % (r[0], r[1], r[2]))
    agg = collections.Counter()
    for h, v in uniq.items():
        agg[os.path.dirname(v[0][0]) or "/"] += v[0][2]
    print("\n=== 디렉터리별 (중복 제거) ===")
    for d, c in agg.most_common(20):
        print("%-14s %9d" % (d, c))


if __name__ == "__main__":
    main()
