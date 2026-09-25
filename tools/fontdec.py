"""모듈별 폰트에 맞는 글리프인덱스 디코더.

★배경(세션15 확정): 폰트들은 **하나의 마스터 순서를 공유하지 않는다.**
   ASCGSCG·ASCIMCG 는 240부터, MAPSCT·BKCK 는 0부터 ASCMSCG 와 다르다.
   ⇒ charmap(공용표)은 ASC16CG/ASCMSCG/SCHOOL 계열 전용이고,
     다른 모듈은 work/fontmaps.json (derive_map.py 산출) 을 써야 한다.

화면별 폰트(메모리 확정):
   GAME·KEKKA=ASC16CG / SAKUSEN=SAKUCG / INTERM=ASCIMCG
   MUSEUM=ASCMSCG / GMSELDT=ASCGSCG / SCHOOL=자체사본(school_charmap)
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAPS = json.load(open(os.path.join(ROOT, "work", "fontmaps.json"), encoding="utf-8"))

# 모듈 -> 폰트 이름
# ⚠️ work/fontmaps.json 의 "ASC16CG2" 는 매핑이 25개뿐이라 못 쓴다.
#    ASC16CG 는 0~819 가 ASCMSCG 와 바이트 동일이므로 공용 charmap(=None) 이 정답이다.
MODULE_FONT = {
    "/GAME": None, "/KEKKA": None, "/GMDT": None,
    "/SAKUSEN": "SAKUCG", "/INTERM": "ASCIMCG",
    "/MUSEUM": "ASCMSCG", "/GMSELDT": "ASCGSCG",
}


def table(font):
    """글리프인덱스 -> 문자 dict."""
    if font == "SCHOOL":
        from school_charmap import SCHOOL_CHARS
        t = dict(charmap.CHARS)
        t.update(SCHOOL_CHARS)
        return t
    if font in _MAPS:
        return {int(k): v for k, v in _MAPS[font].items()}
    return dict(charmap.CHARS)


def decode(data, off, count, tbl):
    out = []
    for i in range(count):
        v = int.from_bytes(data[off + i * 2: off + i * 2 + 2], "big")
        if v in charmap.CTRL:
            out.append(charmap.CTRL[v])
        elif v >= 0xFF00:
            out.append("{%04X}" % v)
        else:
            ch = tbl.get(v)
            out.append(ch if ch is not None else "〈%d〉" % v)
    return "".join(out)


def coverage():
    for name, m in _MAPS.items():
        n = len(m)
        unk = sum(1 for v in m.values() if not v or v.startswith("〈"))
        print("%-10s 매핑 %4d개 (미판독 %d)" % (name, n, unk))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    coverage()
