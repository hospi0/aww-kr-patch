"""사관학교(/SCHOOL) 대사·강의 텍스트 추출 -> work/school/school.tsv

구조: 0x39000~0x3BC00 구간, 레코드 구분자 0xFFFF.
제어코드: {FB}=수치 치환, {F9}=이름 치환, {FC}/{FD}=페이지/줄 넘김, {FE}=여백
글리프 인덱스는 SCHOOL 내장 폰트(0x1C574) 기준 — charmap + school_charmap 병합으로 디코드한다.
"""
import os, sys, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap
try:
    from school_charmap import SCHOOL_CHARS
except ImportError:
    SCHOOL_CHARS = {}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_LO, TEXT_HI = 0x39000, 0x3BC00
SEP = 0xFFFF


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def decode_word(v):
    if v == SEP:
        return None
    if v in SCHOOL_CHARS:
        return SCHOOL_CHARS[v]
    if v >= 0xFF00:
        return charmap.CTRL.get(v, "{%04X}" % v)
    ch = charmap.CHARS.get(v)
    return ch if ch is not None else "〈%d〉" % v


def records(data, lo=TEXT_LO, hi=TEXT_HI):
    """(offset, nwords, text) 리스트. 구분자 0xFFFF 로 자른다."""
    out = []
    start = lo
    buf = []
    i = lo
    while i < hi:
        v = int.from_bytes(data[i:i + 2], "big")
        if v == SEP:
            if buf:
                out.append((start, (i - start) // 2, "".join(buf)))
            buf = []
            start = i + 2
        else:
            buf.append(decode_word(v))
        i += 2
    if buf:
        out.append((start, (i - start) // 2, "".join(buf)))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = get("/SCHOOL")
    recs = records(data)
    outdir = os.path.join(ROOT, "work", "school")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "school.tsv")
    unread = set()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["idx", "offset", "words", "jp", "kr"])
        for k, (off, nw, txt) in enumerate(recs):
            w.writerow([k, "0x%06x" % off, nw, txt, ""])
            for seg in txt.split("〈")[1:]:
                if "〉" in seg:
                    unread.add(int(seg.split("〉")[0]))
    print("레코드 %d개 -> %s" % (len(recs), path))
    print("총 글자수(제어코드 제외 근사) = %d" % sum(r[1] for r in recs))
    if unread:
        print("미판독 글리프 %d개: %s" % (len(unread), sorted(unread)))


if __name__ == "__main__":
    main()
