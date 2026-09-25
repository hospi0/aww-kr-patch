"""ASC16CG(판독 확정)의 글리프 비트맵과 128바이트 완전일치로 다른 폰트의 매핑을 유도."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXD = os.path.join(ROOT, "work", "extract")


def glyphs(name):
    d = open(os.path.join(EXD, name), "rb").read()
    return [d[i * 128:(i + 1) * 128] for i in range(len(d) // 128)]


def main():
    base = glyphs("ASC16CG")
    lookup = {}
    for i, g in enumerate(base):
        ch = charmap.CHARS.get(i)
        if ch is None:
            continue
        lookup.setdefault(g, ch)     # 첫 등장 우선
    out = {}
    for name in ["ASCMSCG", "ASCGSCG", "ASCIMCG", "ASC16CG2", "SAKUCG"]:
        gs = glyphs(name)
        tbl, miss = {}, []
        for i, g in enumerate(gs):
            ch = lookup.get(g)
            if ch is None:
                miss.append(i)
            else:
                tbl[i] = ch
        out[name] = tbl
        print("%-10s %d글리프  유도 %d  미판독 %d" % (name, len(gs), len(tbl), len(miss)))
        if miss:
            print("   미판독 인덱스: %s%s" % (
                ", ".join(str(m) for m in miss[:40]), " ..." if len(miss) > 40 else ""))
    result = {k: {str(i): c for i, c in v.items()} for k, v in out.items()}
    # ★수동 육안 판독분 병합 (세션2: ASCIMCG 149·ASCGSCG 97). 자동유도가 못 잡는
    #   폰트 고유 한자라 이걸 안 병합하면 재실행 시 INTERM·GMSELDT 디코드가 깨진다.
    manp = os.path.join(ROOT, "work", "manual_glyphs.json")
    if os.path.exists(manp):
        man = json.load(open(manp, encoding="utf-8"))
        for fn, tbl in man.items():
            result.setdefault(fn, {}).update(tbl)
        print("수동 판독 병합: " + ", ".join("%s+%d" % (k, len(v)) for k, v in man.items()))
    json.dump(result, open(os.path.join(ROOT, "work", "fontmaps.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
