"""풀↔폰트 대응 판정.

각 모듈의 텍스트 레코드(0xFFFF 종결 워드런)를 후보 폰트 5종으로 디코드하고,
①범위검사(풀 최대 워드인덱스 <= 폰트 글리프수) ②고인덱스(>=240, 폰트마다 다른 한자영역)
매핑 커버리지 로 실제 사용 폰트를 판정한다.

근거: 가나·ASCII(0~239)는 모든 폰트가 같은 순서를 공유하므로 판별력이 없다.
     240+ 한자영역이 폰트마다 달라, 그 영역이 자연스러운 일본어로 풀리는 폰트가 정답.
"""
import os, sys, io, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap
from findtext2 import records

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 폰트 실제 글리프 수(범위검사용) — budget.py/메모리 실측
GLYPHS = {"ASC16CG": 825, "ASCMSCG": 830, "ASCGSCG": 594,
          "ASCIMCG": 697, "ASC16CG2": 320}


def load_maps():
    fm = json.load(io.open(os.path.join(ROOT, "work", "fontmaps.json"), encoding="utf-8"))
    maps = {"ASC16CG": {int(k): v for k, v in charmap.CHARS.items()}}
    for name in ("ASCMSCG", "ASCGSCG", "ASCIMCG", "ASC16CG2"):
        if name in fm:
            maps[name] = {int(k): v for k, v in fm[name].items()}
    return maps


def words_of(data, recs):
    out = []
    for off, ln, _ in recs:
        base = off // 2
        for j in range(ln):
            v = (data[(base + j) * 2] << 8) | data[(base + j) * 2 + 1]
            out.append(v)
    return out


def score(ws, cmap, glyphs):
    """(범위OK, 고인덱스 커버리지, 고인덱스 총수, 최대idx)."""
    hi = [w for w in ws if 240 <= w <= 0xFFEF]      # 한자영역 (제어/가나 제외)
    maxidx = max((w for w in ws if w <= 0xFFEF), default=0)
    in_range = maxidx < glyphs
    if not hi:
        return in_range, 1.0, 0, maxidx     # 한자 없으면 커버리지 무의미(가나풀)
    cov = sum(1 for w in hi if w in cmap) / len(hi)
    return in_range, cov, len(hi), maxidx


def decode_sample(ws, cmap, n=40):
    out = []
    for w in ws[:n]:
        if 0xFFF0 <= w <= 0xFFFE:
            out.append("/" if w == 0xFFFD else "·")
        elif w in cmap:
            out.append(cmap[w])
        else:
            out.append("〈%d〉" % w)
    return "".join(out)


def main():
    maps = load_maps()
    fonts = list(maps.keys())
    print("후보 폰트:", ", ".join("%s(%d)" % (f, GLYPHS[f]) for f in fonts))
    print()
    lst = files()
    # 중복 내용 제거 위해 md5로
    seen = {}
    results = []
    with open(TRACK1, "rb") as f:
        for p, lba, size in lst:
            if size < 64:
                continue
            data = read_range(f, lba, size)
            recs = records(data)
            if len(recs) < 3:
                continue
            ws = words_of(data, recs)
            nch = sum(1 for w in ws if 1 <= w <= 0xFFEF)
            if nch < 100:
                continue
            import hashlib
            h = hashlib.md5(data).hexdigest()
            if h in seen:
                continue
            seen[h] = p
            row = {"path": p, "recs": len(recs), "chars": nch}
            best, bestcov = None, -1
            for fn in fonts:
                inr, cov, nhi, mx = score(ws, maps[fn], GLYPHS[fn])
                row[fn] = (inr, cov, mx)
                if inr and cov > bestcov:
                    best, bestcov = fn, cov
            row["best"] = best
            row["bestcov"] = bestcov
            row["ws"] = ws
            results.append(row)

    results.sort(key=lambda r: -r["chars"])
    print("%-26s %6s %6s | %-9s %5s | %s" % ("path", "recs", "chars", "best", "cov", "폰트별 (범위,커버리지,max)"))
    print("-" * 120)
    for r in results[:40]:
        cells = []
        for fn in fonts:
            inr, cov, mx = r[fn]
            flag = " " if inr else "✗"
            cells.append("%s%.2f" % (flag, cov))
        print("%-26s %6d %6d | %-9s %5.2f | %s" % (
            r["path"], r["recs"], r["chars"], r["best"] or "?", r["bestcov"],
            " ".join("%s:%s" % (f[:4], c) for f, c in zip(fonts, cells))))

    # best 폰트별 집계
    print("\n=== best 폰트별 모듈 집계 ===")
    agg = collections.Counter()
    chagg = collections.Counter()
    for r in results:
        agg[r["best"]] += 1
        chagg[r["best"]] += r["chars"]
    for fn, n in agg.most_common():
        print("  %-9s 모듈 %3d개  문자 %d" % (fn or "?", n, chagg[fn]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
