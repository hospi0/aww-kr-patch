"""Track01 user data 전역 바이트열 검색 (섹터 경계 넘어가며 스캔)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER

CHUNK = 4096  # 섹터 단위


def iter_userdata():
    """(start_lba, bytes) 청크를 순차 반환 (섹터 헤더 제거)."""
    size = os.path.getsize(TRACK1)
    nsec = size // RAW
    with open(TRACK1, "rb") as f:
        lba = 0
        while lba < nsec:
            n = min(CHUNK, nsec - lba)
            raw = f.read(RAW * n)
            buf = bytearray()
            for i in range(n):
                buf += raw[i * RAW + HDR: i * RAW + HDR + USER]
            yield lba, bytes(buf)
            lba += n


def scan(patterns):
    hits = {p: [] for p in patterns}
    maxlen = max(len(p) for p in patterns)
    tail = b""
    tail_lba = 0
    for lba, buf in iter_userdata():
        data = tail + buf
        base = tail_lba
        for p in patterns:
            start = 0
            while True:
                i = data.find(p, start)
                if i < 0:
                    break
                abs_off = base * USER + i
                hits[p].append((abs_off, abs_off // USER, abs_off % USER))
                start = i + 1
        keep = maxlen - 1
        tail = data[-keep:] if keep else b""
        tail_lba = (base * USER + len(data) - len(tail)) // USER
    return hits


if __name__ == "__main__":
    pats = [bytes.fromhex(a) for a in sys.argv[1:]]
    hits = scan(pats)
    for p, hs in hits.items():
        print("=== %s : %d hits ===" % (p.hex(" "), len(hs)))
        for off, lba, so in hs[:40]:
            print("   off=0x%08x  lba=%d  +0x%x" % (off, lba, so))
