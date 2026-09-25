"""수요 측 추정 — 한국어 번역문의 고유 음절 수 곡선(Heaps' law)으로 외삽.

U(N) = K * N^b   (N=누적 음절 토큰, U=고유 음절 종수)
표본은 실제 원문을 번역한 것이라야 한다. 지어낸 문장으로 재면 측정이 아니다.
"""
import os, sys, math, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def syllables(text):
    return [c for c in text if "가" <= c <= "힣"]


def curve(toks, points=24, trials=8):
    """무작위 순서를 여러 번 섞어 평균 낸 type-token 곡선."""
    N = len(toks)
    xs = [max(1, int(N * (i + 1) / points)) for i in range(points)]
    ys = [0.0] * points
    for _ in range(trials):
        seq = toks[:]
        random.shuffle(seq)
        seen = set()
        out = []
        idx = 0
        for x in xs:
            while idx < x:
                seen.add(seq[idx])
                idx += 1
            out.append(len(seen))
        for i, v in enumerate(out):
            ys[i] += v / trials
    return xs, ys


def fit(xs, ys):
    """log U = log K + b log N 최소제곱."""
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(lx)
    mx, my = sum(lx) / n, sum(ly) / n
    b = sum((lx[i] - mx) * (ly[i] - my) for i in range(n)) / \
        sum((lx[i] - mx) ** 2 for i in range(n))
    K = math.exp(my - b * mx)
    return K, b


def main():
    random.seed(7)
    p = os.path.join(ROOT, "work", "ascgscg_kr_sample.txt")
    text = open(p, encoding="utf-8").read()
    toks = syllables(text)
    uniq = set(toks)
    print("표본: 음절 토큰 %d개, 고유 %d종" % (len(toks), len(uniq)))
    xs, ys = curve(toks)
    K, b = fit(xs, ys)
    print("Heaps' law 적합: U = %.2f * N^%.3f" % (K, b))
    print()
    print("%10s %10s" % ("코퍼스 음절", "예상 고유음절"))
    for N in (1000, 2000, 4000, 6000, 10000, 20000, 40000, 80000, 150000):
        print("%10d %10d" % (N, round(K * N ** b)))
    print()
    print("공급(폰트별 한글 가용 슬롯): ASC16CG 733 / ASCMSCG 737 / "
          "ASCGSCG 520 / ASCIMCG 615 / SAKUCG 1017")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
