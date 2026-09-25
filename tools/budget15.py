"""폰트별 예산 실측 — **전면 한글화 기준** ([[feedback_aww_full_kr_budget]]).

공급 = 그 폰트의 도달 가능 천장 **전체**(원본 칸 포함). 「천장 − 현재사용」이 아니다.
수요 = 그 폰트가 렌더하는 **전체 텍스트**의 고유 한글 음절 수.

이 스크립트는 정적으로 잴 수 있는 것만 낸다:
  · 폰트별 현재 글리프 수(파일 크기 / 128)
  · 폰트별 소비자 모듈의 전체 텍스트 분량·고유 일본문자 수 (수요 상한 근사)
천장(charnum·VRAM 배치)은 스테이트가 필요해 별도(budget_ceiling.py).
"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import fontdec
from find_prose import prose_runs

GSZ = 128

# 폰트 -> (폰트파일, 소비 모듈들)
FONTS = {
    "ASC16CG":  ("/ASC16CG",  ["/GAME", "/KEKKA", "/GMDT"]),
    "ASCGSCG":  ("/ASCGSCG",  ["/GMSELDT"]),
    "ASCIMCG":  ("/ASCIMCG",  ["/INTERM"]),
    "ASCMSCG":  ("/ASCMSCG",  ["/MUSEUM"]),
    "SAKUCG":   ("/SAKUCG",   ["/SAKUSEN"]),
    "SCHOOL내장": (None,       ["/SCHOOL"]),
}
SCHOOL_FONT_OFF = 0x1C574

# 메모리에 기록된 천장(확정된 것만). None = 미확정 → 스테이트로 역산해야 함
CEILING = {
    "ASC16CG": 900,    # 세션12 B안(맵 0x1E000 복귀). PNT charnum 하드상한은 964
    "ASCGSCG": 900,    # 세션13-c 확정 (텍스트맵 0x1E000)
    "ASCMSCG": 964,    # 세션13-b 실측 (MUSEUM 전용, VRAM 0x1C000~0x22000 여유)
    "ASCIMCG": None,
    "SAKUCG":  None,
    "SCHOOL내장": None,
}


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    return None


def font_glyphs(name):
    path, _ = FONTS[name]
    if path is None:
        d = get("/SCHOOL")
        region = d[SCHOOL_FONT_OFF:]
        # 뒤에서부터 비어있지 않은 글리프 = 폰트 끝 추정
        last = 0
        for i in range(0, 1400):
            g = region[i * GSZ:(i + 1) * GSZ]
            if len(g) < GSZ:
                break
            if any(g):
                last = i
        return last + 1, "내장(0x%X~), 끝 추정" % SCHOOL_FONT_OFF
    d = get(path)
    return len(d) // GSZ, "파일 %d B" % len(d)


def module_text(mod, tbl, fmax):
    """소비자 모듈의 산문 구간 전체를 모아 (글자수, 고유문자집합) 반환."""
    d = get(mod)
    if d is None:
        return 0, set(), []
    runs = prose_runs(d, fmax, min_kb=0.5)
    total = 0
    uniq = set()
    for a, b in runs:
        for i in range(a, b, 2):
            v = int.from_bytes(d[i:i + 2], "big")
            if v >= 0xFF00:
                continue
            ch = tbl.get(v)
            if ch and ch != " ":
                total += 1
                uniq.add(ch)
    return total, uniq, runs


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== 공급: 폰트 현황 (전면 한글화 기준 = 천장 전체가 가용) ===")
    print("%-10s %8s %8s %8s   %s" % ("폰트", "현재글리프", "천장", "가용칸", "비고"))
    supply = {}
    for name in FONTS:
        n, note = font_glyphs(name)
        c = CEILING[name]
        supply[name] = (n, c)
        print("%-10s %8d %8s %8s   %s" % (
            name, n, c if c else "미확정", c if c else "?", note))

    print()
    print("=== 수요: 소비자 모듈의 전체 텍스트 (일본어 기준) ===")
    print("%-10s %-28s %8s %8s" % ("폰트", "소비 모듈", "글자", "고유JP"))
    for name, (path, mods) in FONTS.items():
        font = None if name == "ASC16CG" else ("SCHOOL" if name == "SCHOOL내장" else name)
        tbl = fontdec.table(font)
        fmax = max(tbl)
        tot = 0
        uniq = set()
        parts = []
        for m in mods:
            n, u, runs = module_text(m, tbl, fmax)
            tot += n
            uniq |= u
            parts.append("%s(%d)" % (m.strip("/"), n))
        print("%-10s %-28s %8d %8d" % (name, " ".join(parts), tot, len(uniq)))


if __name__ == "__main__":
    main()
