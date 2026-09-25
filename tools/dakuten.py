"""탁점(゛)/반탁점(゜) 판별: 우상단 마크에 '닫힌 구멍'이 있으면 반탁점(원).

기준군 = 논쟁 구간(204~213) 밖의 탁점 확정 글리프.
  ダ(199) ヂ(200) ヅ(201) デ(202) ド(203) ヴ(223) が(109) ぎ(110) ゲ(192) ゴ(193)
이들은 대량 디코드로 문자 정체가 검증됐다.
"""
import sys, os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "work", "extract", "ASC16CG")


def bmp(d, i):
    g = d[i * 128:(i + 1) * 128]
    out = [[0] * 16 for _ in range(16)]
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        tl = g[t * 32:(t + 1) * 32]
        for y in range(8):
            for x in range(8):
                b = tl[y * 4 + x // 2]
                out[cy + y][cx + x] = (b >> 4) if x % 2 == 0 else (b & 15)
    return out


def mark_hole(b, thr=7):
    """우상단 8x8에서 잉크 이진화 후, 배경 flood-fill로 닫힌 구멍 개수."""
    R = [[1 if b[y][x] >= thr else 0 for x in range(8, 16)] for y in range(0, 8)]
    seen = [[False] * 8 for _ in range(8)]
    st = []
    for k in range(8):
        for (y, x) in ((0, k), (7, k), (k, 0), (k, 7)):
            if not R[y][x] and not seen[y][x]:
                seen[y][x] = True; st.append((y, x))
    while st:
        y, x = st.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < 8 and 0 <= nx < 8 and not R[ny][nx] and not seen[ny][nx]:
                seen[ny][nx] = True; st.append((ny, nx))
    holes = sum(1 for y in range(8) for x in range(8) if not R[y][x] and not seen[y][x])
    ink = sum(sum(r) for r in R)
    return holes, ink


def main():
    d = open(PATH, "rb").read()
    ref = [(199, "ダ"), (200, "ヂ"), (201, "ヅ"), (202, "デ"), (203, "ド"),
           (223, "ヴ"), (109, "が"), (110, "ぎ"), (192, "ゲ"), (193, "ゴ")]
    print("=== 기준군: 탁点 확정 (구간 밖) ===")
    hs = []
    for i, nm in ref:
        h, ink = mark_hole(bmp(d, i))
        hs.append(h)
        print("  %3d %s  구멍=%d 잉크=%d" % (i, nm, h, ink))
    print("  -> 탁점 구멍 평균 %.2f, 최대 %d" % (sum(hs) / len(hs), max(hs)))
    print("\n=== 논쟁 구간 ===")
    for grp, rng in (("A(204~208)", range(204, 209)), ("B(209~213)", range(209, 214))):
        tot = []
        for i in rng:
            h, ink = mark_hole(bmp(d, i))
            tot.append(h)
            print("  %s %3d  구멍=%d 잉크=%d" % (grp, i, h, ink))
        print("  -> %s 구멍 평균 %.2f" % (grp, sum(tot) / len(tot)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
