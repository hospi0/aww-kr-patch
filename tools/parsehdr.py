"""모듈 헤더의 리소스 디렉터리 파싱.

관측 구조 (GMSELDT):
  0x00  폰트 파일명 ASCIIZ (없는 모듈도 있음)
  0x40~ 16바이트 레코드 반복:
          +0  u32 id
          +4  u32 ?
          +8  u16 w, u16 h      (16x16, 152x8 등 = 스프라이트 치수)
          +12 u32 0x0020_0000 | file_offset
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumptext import get

TAG = 0x00200000


def parse(data, start=0x40, limit=4096):
    recs = []
    o = start
    while o + 16 <= len(data) and len(recs) < limit:
        i, u, wh, p = struct.unpack_from(">IIII", data, o)
        if (p & 0xFFFF0000) != TAG:
            break
        recs.append({"off": o, "id": i, "u": u,
                     "w": wh >> 16, "h": wh & 0xFFFF,
                     "ptr": p & 0xFFFF})
        o += 16
    return recs, o


def main(paths):
    for p in paths:
        d = get(p)
        name = d[:8].split(b"\x00")[0].decode("ascii", "replace")
        recs, end = parse(d)
        print("=== %s  (%d B)  폰트필드=%r" % (p, len(d), name))
        print("    디렉터리 0x40 ~ 0x%x : 레코드 %d개" % (end, len(recs)))
        if not recs:
            print()
            continue
        ptrs = sorted(set(r["ptr"] for r in recs))
        print("    ptr 범위 0x%x ~ 0x%x" % (ptrs[0], ptrs[-1]))
        dims = {}
        for r in recs:
            dims[(r["w"], r["h"])] = dims.get((r["w"], r["h"]), 0) + 1
        print("    치수 분포:", ", ".join("%dx%d×%d" % (w, h, c)
                                       for (w, h), c in sorted(dims.items(), key=lambda x: -x[1])[:8]))
        for r in recs[:8]:
            print("      id=%-4d %3dx%-3d ptr=0x%04x" % (r["id"], r["w"], r["h"], r["ptr"]))
        print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
