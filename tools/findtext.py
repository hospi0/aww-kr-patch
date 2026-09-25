"""전 파일에서 글리프인덱스 텍스트 블록을 찾아 분량을 측정한다.

판정 규칙(보수적):
  - BE u16 워드가 0x0000..MAXG(825) 또는 0xFF00.. 제어코드
  - 연속 런 안에 '가나 또는 한자'(idx>=63) 문자가 MIN_INK개 이상
  - 런 길이 MIN_RUN 워드 이상
그래픽 데이터의 우연 일치를 완전히 배제하지는 못한다 -> 디코드 결과를 눈으로 확인할 것.
"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap

MAXG = 824
MIN_RUN = 12
MIN_INK = 6
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blocks(data):
    """(start_byte, nwords, ink) 리스트."""
    n = len(data) // 2
    out = []
    i = 0
    while i < n:
        v = int.from_bytes(data[i * 2:i * 2 + 2], "big")
        if not (v <= MAXG or v >= 0xFFF0):
            i += 1
            continue
        j = i
        ink = 0
        while j < n:
            w = int.from_bytes(data[j * 2:j * 2 + 2], "big")
            if not (w <= MAXG or w >= 0xFFF0):
                break
            if 63 <= w <= MAXG:
                ink += 1
            j += 1
        if j - i >= MIN_RUN and ink >= MIN_INK:
            out.append((i * 2, j - i, ink))
        i = max(j, i + 1)
    return out


def main():
    lst = files()
    rows = []
    tot_ink = 0
    with open(TRACK1, "rb") as f:
        for p, lba, size in lst:
            if size < 32:
                continue
            data = read_range(f, lba, size)
            bs = blocks(data)
            if not bs:
                continue
            ink = sum(b[2] for b in bs)
            words = sum(b[1] for b in bs)
            rows.append((p, len(bs), words, ink, size))
            tot_ink += ink
    rows.sort(key=lambda r: -r[3])
    outp = os.path.join(ROOT, "work", "textmap.tsv")
    with open(outp, "w", encoding="utf-8") as w:
        w.write("path\tblocks\twords\tink_chars\tfile_size\n")
        for r in rows:
            w.write("%s\t%d\t%d\t%d\t%d\n" % r)
    print("파일 %d개에 텍스트 블록 존재, 총 가나/한자 %d자" % (len(rows), tot_ink))
    print()
    print("%-28s %7s %8s %9s" % ("path", "blocks", "words", "chars"))
    for r in rows[:35]:
        print("%-28s %7d %8d %9d" % (r[0], r[1], r[2], r[3]))
    # 디렉터리 집계
    agg = collections.Counter()
    for p, nb, wd, ink, sz in rows:
        agg[os.path.dirname(p) or "/"] += ink
    print("\n=== 디렉터리별 문자수 ===")
    for d, c in agg.most_common(25):
        print("%-14s %9d" % (d, c))


if __name__ == "__main__":
    main()
