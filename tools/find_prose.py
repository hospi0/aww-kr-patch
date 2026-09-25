"""전 모듈에서 「진짜 산문(대사·내레이션)」 구간만 골라낸다.

★왜 필요한가: findtext.py 의 블록 판정은 글리프 리맵 테이블·유닛 스탯 같은
   비문장 데이터를 대량으로 잡는다(/KOUGI 가 최대 텍스트로 잡혔지만 전부 표였다).
   ⇒ 산문 판정은 「가나 비율 + 연속 길이 + 고유 문자 종수」 3중 제약으로 한다.
   ([[feedback_scan_coverage_and_detectors]] — 검출기엔 양성·음성·고유율 제약이 다 필요)

★폰트: 모듈마다 순서가 다르므로 fontdec.MODULE_FONT 를 따른다.
"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import fontdec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = 0x200
KANA_LO, KANA_HI = 63, 230


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    return None


def prose_runs(data, font_max, min_kb=1.0):
    """가나비율 높은 창을 이어붙여 산문 구간 후보를 만든다."""
    runs = []
    cur = None
    for base in range(0, len(data), WIN):
        ws = [int.from_bytes(data[i:i + 2], "big")
              for i in range(base, min(base + WIN, len(data)), 2)]
        if not ws:
            continue
        kana = sum(1 for w in ws if KANA_LO <= w <= KANA_HI)
        inrange = sum(1 for w in ws if w <= font_max or w >= 0xFFF0)
        ok = kana / len(ws) >= 0.28 and inrange / len(ws) >= 0.95
        if ok:
            if cur is None:
                cur = [base, base + WIN]
            else:
                cur[1] = base + WIN
        else:
            if cur:
                runs.append(tuple(cur))
            cur = None
    if cur:
        runs.append(tuple(cur))
    return [r for r in runs if (r[1] - r[0]) >= min_kb * 1024]


def stats(data, a, b, tbl):
    ws = [int.from_bytes(data[i:i + 2], "big") for i in range(a, b, 2)]
    chars = [tbl.get(w) for w in ws if w < 0xFF00]
    txt = "".join(c for c in chars if c)
    seps = sum(1 for w in ws if w == 0xFFFF)
    return len(txt), len(set(txt)), seps


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    targets = ["/INTERM", "/SAKUSEN", "/KEKKA", "/GMDT", "/GAME", "/BADEND",
               "/MUSEUM", "/GMSELDT", "/SCHOOL", "/KOUGI", "/MAPSCT", "/BKCK"]
    rows = []
    for name in targets:
        d = get(name)
        if d is None:
            print("(없음) " + name)
            continue
        font = "SCHOOL" if name == "/SCHOOL" else fontdec.MODULE_FONT.get(name)
        tbl = fontdec.table(font) if font else fontdec.table(None)
        fmax = max(tbl) if tbl else 824
        runs = prose_runs(d, fmax)
        tot = 0
        detail = []
        for a, b in runs:
            n, uniq, seps = stats(d, a, b, tbl)
            tot += n
            detail.append((a, b, n, uniq, seps))
        rows.append((name, font, tot, detail))

    print("%-10s %-9s %8s  %s" % ("모듈", "폰트", "산문글자", "구간"))
    for name, font, tot, detail in sorted(rows, key=lambda r: -r[2]):
        if tot == 0:
            continue
        print("%-10s %-9s %8d  %s" % (
            name, font or "공용", tot,
            ", ".join("0x%06x~0x%06x(%d자/고유%d/줄%d)" % (a, b, n, u, s)
                      for a, b, n, u, s in detail)))


if __name__ == "__main__":
    main()
