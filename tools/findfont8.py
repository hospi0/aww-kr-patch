"""8x8 소형 폰트(무기명·HUD용) 후보 영역 탐색기.

배경: 유닛 상세 화면의 무기명(「7.92㎜MG」「ブソウナシ」)은 16x16 ASC16CG가 아니라
      하드엣지 8x8 글리프다(스크린샷 확대로 확정). 기존 검색은 전부 16x16 인덱스 기준이라 놓쳤다.

가설 두 개를 같은 창에서 채점한다:
  1bpp : 8 B/글리프 (행당 1바이트)
  4bpp : 32 B/글리프 (행당 4바이트, 저니블=왼쪽 — 기존 폰트와 같은 규약)

특징:
  blank  : 완전히 빈 행의 비율 (폰트는 위/아래 여백 때문에 0.1~0.4)
  ink    : 글리프당 잉크 픽셀 비율 평균 (0.10~0.45)
  uniq   : 서로 다른 글리프 비율 (0.6 이상)
  even   : 1bpp에서 마지막 열이 비는 폰트면 짝수 바이트 비율이 높다 (참고용)
⚠️ 검출기가 「빈 데이터」에 만점 주지 않도록 blank 상한과 uniq 하한을 둘 다 건다.
"""
import os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POPCNT = np.array([bin(i).count('1') for i in range(256)], dtype=np.uint8)


def score_1bpp(buf, win_glyphs=96):
    """(offset, score, feats) 리스트. 8바이트 정렬 창을 슬라이드."""
    n = len(buf) // 8
    if n < win_glyphs:
        return []
    a = np.frombuffer(buf[:n * 8], dtype=np.uint8).reshape(n, 8)
    ink = POPCNT[a].sum(axis=1).astype(np.float32) / 64.0      # 글리프별 잉크율
    blankrow = (a == 0).sum(axis=1).astype(np.float32) / 8.0    # 글리프별 빈 행 비율
    out = []
    step = win_glyphs // 2
    for s in range(0, n - win_glyphs, step):
        w = a[s:s + win_glyphs]
        i_m = float(ink[s:s + win_glyphs].mean())
        b_m = float(blankrow[s:s + win_glyphs].mean())
        uniq = len(set(map(bytes, w))) / win_glyphs
        # 완전 빈/포화 글리프가 많으면 폰트가 아니다
        dead = float(((ink[s:s + win_glyphs] < 0.01) | (ink[s:s + win_glyphs] > 0.75)).mean())
        if not (0.08 <= i_m <= 0.45 and 0.08 <= b_m <= 0.55 and uniq >= 0.6 and dead <= 0.15):
            continue
        even = float((w % 2 == 0).mean())
        sc = uniq * (1 - dead) * (1 - abs(i_m - 0.25) / 0.25 * 0.5)
        out.append((s * 8, sc, dict(ink=round(i_m, 3), blank=round(b_m, 3),
                                    uniq=round(uniq, 2), dead=round(dead, 2),
                                    even=round(even, 2))))
    return out


def main():
    targets = sys.argv[1:]
    if not targets:
        d = os.path.join(ROOT, 'work', 'extract')
        targets = [os.path.join(d, f) for f in os.listdir(d)
                   if not f.lower().endswith(('.png', '.txt'))]
    for path in targets:
        buf = open(path, 'rb').read()
        res = score_1bpp(buf)
        if not res:
            print(f'{os.path.basename(path):12s} -')
            continue
        res.sort(key=lambda r: -r[1])
        print(f'{os.path.basename(path):12s} {len(res):5d} hits')
        for off, sc, f in res[:6]:
            print(f'    0x{off:07x} {sc:.3f} {f}')


if __name__ == '__main__':
    main()
