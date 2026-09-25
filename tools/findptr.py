"""텍스트 레코드 오프셋을 가리키는 포인터 배열을 역탐색한다.

레코드 시작 오프셋 집합 S를 만들고, 파일 전체에서
  BE u32 / BE u16 / (오프셋-base) / (오프셋/2)
값이 S의 원소와 연속으로 여러 개 맞는 구간을 찾는다.
"연속 오름차순으로 뭉쳐 있어야 진짜 테이블" — 단발 일치는 노이즈다.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumptext import get
from findtext2 import records

MIN_HITS = 6          # 이만큼 연속으로 맞아야 테이블로 인정


def candidates(data, starts, width, base, scale):
    """width바이트 BE 정수를 훑어 S에 맞는 위치 목록."""
    n = len(data) - width + 1
    hit = []
    S = starts
    for i in range(0, n, width):     # width 정렬 가정
        v = int.from_bytes(data[i:i + width], "big")
        if v == 0:                   # 0 매칭은 base 때문에 생기는 자명한 오탐
            continue
        t = v * scale + base
        if t in S:
            hit.append((i, t))
    return hit


def runs(hits, width):
    """연속 + 순증가 + 서로 다른 대상 히트만 테이블로 인정."""
    out = []
    cur = []
    for i, t in hits:
        if cur and i == cur[-1][0] + width and t > cur[-1][1]:
            cur.append((i, t))
        else:
            if len(cur) >= MIN_HITS:
                out.append(cur)
            cur = [(i, t)]
    if len(cur) >= MIN_HITS:
        out.append(cur)
    return out


def analyze(path):
    data = get(path)
    rs = records(data)
    starts = set(r[0] for r in rs)
    print("== %s : %d B, 레코드 %d개" % (path, len(data), len(rs)))
    if not rs:
        return
    lo, hi = min(starts), max(starts)
    print("   레코드 오프셋 범위 0x%x ~ 0x%x" % (lo, hi))

    for width in (4, 2):
        for scale in (1, 2):
            for base in (0, lo, lo & ~0xFFF, 0x06000000, 0x00200000):
                hits = candidates(data, starts, width, base, scale)
                rr = runs(hits, width)
                if rr:
                    for r in rr:
                        print("   [u%d scale=%d base=0x%x] 표 0x%06x  길이 %d  "
                              "첫값->0x%x  끝값->0x%x"
                              % (width * 8, scale, base, r[0][0], len(r),
                                 r[0][1], r[-1][1]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for p in sys.argv[1:]:
        analyze(p)
        print()
