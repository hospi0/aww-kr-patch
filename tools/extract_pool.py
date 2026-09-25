"""모듈의 텍스트 풀을 레코드 단위로 추출해 TSV 로 떨군다 (번역 작업표).

사용: python tools/extract_pool.py            # POOLS 전부
      python tools/extract_pool.py interm_brief

★레코드 구분자 = 0xFFFF. 0x0000 은 공백이지 종료자가 아니다(세션13-d 실증).
★폰트는 모듈마다 다르다 — fontdec.MODULE_FONT 참조.
"""
import os, sys, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import fontdec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "work", "scenario")

# 이름: (모듈, 폰트, 시작, 끝, 설명)
# ★★범위는 **종료자(0xFFFF)로 확정**한다 — `tools/pool_bounds16.py` 로 재검출한 값이다.
#   세션15-g 에 `/SCHOOL` 이 눈대중 범위 탓에 양끝을 다 놓쳤고(버튼 라벨·브리핑 9줄),
#   세션16 재검출에서 **세 풀 다 틀렸음**이 확인됐다:
#     KEKKA   0x21000 → 0x20F8E  (앞 57칸 = 「海軍将軍」 등 장군화면 라벨)
#             0x22E00 → 0x22F34  (뒤 154칸 = 격파 50/100/150대 수여문 + 兵器授与)
#     SAKUSEN 0x49600 → 0x49494  (앞 165칸 = 작전정보·개발·생산 화면 설명문)
#             0x4EA00 → 0x4DFD4  (뒤는 부대명 고정폭 표라 텍스트 아님)
#     INTERM  0x6AE00 → 0x6AD70  (앞 = 「시나리오 분기」 UI)
#             풀이 하나가 아니라 **넷**이다(아래 4개로 분리).
POOLS = {
    "interm_brief":  ("/INTERM",  "ASCIMCG", 0x06AD70, 0x06EE60,
                      "작전 브리핑 본문·이벤트 내레이션 (한 줄 16칸)"),
    "interm_title":  ("/INTERM",  "ASCIMCG", 0x06EE60, 0x06F386,
                      "시나리오 제목 + 미션명 (INTERM 사본 — 다른 사본 번역표 재사용)"),
    "interm_chrono": ("/INTERM",  "ASCIMCG", 0x06F386, 0x06F4E0,
                      "연표 (INTERM 사본 — chrono_kr 재사용)"),
    "interm_doc":    ("/INTERM",  "ASCIMCG", 0x06F4E0, 0x06F790,
                      "사료 문서 (총통 훈령 제1호 등)"),
    "sakusen_msg":   ("/SAKUSEN", "SAKUCG",  0x049494, 0x04DFD4,
                      "작전·생산 화면 메시지 + 작전 목표문"),
    "kekka_medal":   ("/KEKKA",   None,      0x020F8E, 0x022F34,
                      "훈장·특수능력 설명 + 수여문 + 장군화면 라벨"),
    "kekka_result":  ("/KEKKA",   None,      0x0347CC, 0x03492A,
                      "결과·승리판정 화면 (세션16 전수 스캔에서 새로 발견)"),
    "school":        ("/SCHOOL",  "SCHOOL",  0x038FF4, 0x03BD6A,
                      "사관학교 강의·교관 대사 (세션15-g 확정 범위)"),
}
SEP = 0xFFFF

# 풀 안에 텍스트가 아닌 덩어리가 끼어 있는 경우의 실제 텍스트 구간
#   KEKKA 0x0220CC~0x02293C = 훈장 그래픽/테이블(글리프 인덱스 아님, 최대값 65536 초과).
#   0x02293C 부터 다시 텍스트(「Fは、士官学校で優秀成績を…」).
SPLIT = {
    "kekka_medal": [(0x020F8E, 0x0220CC), (0x02293C, 0x022F34)],
}


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def records(data, lo, hi, tbl):
    out = []
    start = lo
    buf = []
    i = lo
    while i < hi:
        v = int.from_bytes(data[i:i + 2], "big")
        if v == SEP:
            out.append((start, (i - start) // 2, "".join(buf)))
            buf = []
            start = i + 2
        else:
            buf.append(fontdec.decode(data, i, 1, tbl))
        i += 2
    if buf:
        out.append((start, (i - start) // 2, "".join(buf)))
    return out


def run(name):
    mod, font, lo, hi, desc = POOLS[name]
    data = get(mod)
    tbl = fontdec.table(font)
    # ★풀 가운데 그래픽 데이터가 끼어 있으면 구간을 나눠 잡는다(KEKKA 0x220CC~0x2293C).
    segs = SPLIT.get(name) or [(lo, hi)]
    recs = []
    for a, b in segs:
        recs += records(data, a, b, tbl)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".tsv")
    nonblank = 0
    chars = 0
    unread = set()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["idx", "offset", "cells", "jp", "kr"])
        for k, (off, nw, txt) in enumerate(recs):
            w.writerow([k, "0x%06x" % off, nw, txt, ""])
            if txt.strip():
                nonblank += 1
                chars += len(txt.strip())
            for seg in txt.split("〈")[1:]:
                if "〉" in seg:
                    unread.add(seg.split("〉")[0])
    print("%-16s %-10s 0x%06x~0x%06x  레코드 %4d(내용있음 %4d) 글자 %6d  -> %s"
          % (name, mod, lo, hi, len(recs), nonblank, chars, os.path.basename(path)))
    if unread:
        print("   ⚠️ 미판독 글리프: %s" % sorted(unread)[:20])
    return desc


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    names = sys.argv[1:] or list(POOLS)
    for n in names:
        desc = run(n)
        print("   = %s" % desc)


if __name__ == "__main__":
    main()
