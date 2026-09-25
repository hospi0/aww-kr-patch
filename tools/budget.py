"""글리프 예산 — 공급 측 계산.

한국어판에서
  유지: ASCII(숫자·영문), 문장부호·기호, 로마숫자·단위 등
  폐기: 가나(히라가나·가타카나), 한자  -> 한글 음절로 재정의 가능
폰트마다 인덱스 공간이 다르므로 파일별로 따로 센다.
"""
import os, sys, json, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXD = os.path.join(ROOT, "work", "extract")


def kind(ch):
    if ch is None:
        return "미판독"
    if ch == " ":
        return "공백"
    o = ord(ch)
    if 0x30A0 <= o <= 0x30FF or 0x3040 <= o <= 0x309F:
        return "가나"
    if 0x4E00 <= o <= 0x9FFF:
        return "한자"
    if ch.isascii() and (ch.isalnum()):
        return "ASCII영숫자"
    return "기호"


def main():
    fm_path = os.path.join(ROOT, "work", "fontmaps.json")
    fm = json.load(open(fm_path, encoding="utf-8")) if os.path.exists(fm_path) else {}
    maps = {"ASC16CG": {i: charmap.CHARS.get(i) for i in range(825)}}
    for name, tbl in fm.items():
        if name == "ASCMSCG":
            continue
        maps.setdefault(name, {int(k): v for k, v in tbl.items()})
    # ASCMSCG는 ASC16CG 상위집합
    if "ASCMSCG" in fm:
        maps["ASCMSCG"] = {int(k): v for k, v in fm["ASCMSCG"].items()}

    print("%-10s %7s %8s %7s %7s %7s %7s %9s" %
          ("폰트", "글리프", "ASCII", "기호", "가나", "한자", "미판독", "한글가용"))
    total = {}
    for name in ["ASC16CG", "ASCMSCG", "ASCGSCG", "ASCIMCG", "SAKUCG"]:
        p = os.path.join(EXD, name)
        if not os.path.exists(p):
            continue
        n = os.path.getsize(p) // 128
        tbl = maps.get(name, {})
        c = {"ASCII영숫자": 0, "기호": 0, "가나": 0, "한자": 0, "미판독": 0, "공백": 0}
        for i in range(n):
            c[kind(tbl.get(i))] += 1
        # 한글로 돌릴 수 있는 것 = 가나 + 한자 + 미판독(대부분 한자)
        avail = c["가나"] + c["한자"] + c["미판독"]
        total[name] = (n, avail)
        print("%-10s %7d %8d %7d %7d %7d %7d %9d" %
              (name, n, c["ASCII영숫자"], c["기호"], c["가나"], c["한자"],
               c["미판독"], avail))
    print()
    print("★ 인덱스 공간이 폰트마다 다르므로 '합계'는 의미가 없다.")
    print("  화면별로 어느 폰트를 쓰는지에 따라 각 폰트가 독립적으로 예산을 갖는다.")
    return total


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
