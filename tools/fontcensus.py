"""128의 배수인 파일을 폰트 후보로 보고, 서로 어떤 인덱스에서 갈라지는지 조사."""
import os, sys, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_font_like(data):
    """ASC16CG의 확정 글리프(가나 20자)를 몇 개나 128B 정렬 위치에 갖고 있는가."""
    if len(data) < 128 * 64 or len(data) % 128:
        return False
    ref = is_font_like.ref
    n = len(data) // 128
    have = sum(1 for i in range(n) if data[i * 128:(i + 1) * 128] in ref)
    return have >= 15


def main():
    cands = []
    with open(TRACK1, "rb") as f:
        for p, lba, size in files():
            if size % 128 or size < 4096 or size > 200000:
                continue
            data = read_range(f, lba, size)
            if is_font_like(data):
                cands.append((p, size // 128, data))
    print("폰트 후보 %d개" % len(cands))
    # 내용 해시로 그룹화
    groups = collections.OrderedDict()
    for p, n, d in cands:
        groups.setdefault(hashlib.md5(d).hexdigest(), []).append((p, n, d))
    print("고유 폰트 %d종\n" % len(groups))
    reps = []
    for h, v in groups.items():
        p, n, d = v[0]
        names = ", ".join(x[0] for x in v)
        print("%-6d글리프  %s" % (n, names))
        reps.append((p, n, d))
    # 204..213 구간 비교
    print("\n=== 인덱스 204~213 비트맵 그룹 ===")
    sig = collections.OrderedDict()
    for p, n, d in reps:
        if n <= 213:
            continue
        s = hashlib.md5(d[204 * 128:214 * 128]).hexdigest()[:8]
        sig.setdefault(s, []).append(p)
    for s, ps in sig.items():
        print("  %s : %s" % (s, ", ".join(ps)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
