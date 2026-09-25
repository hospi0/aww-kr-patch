"""화면별로 「텍스트를 그리는 NBG 레이어」를 찾아 그 레이어의 글리프 도달 범위를 잰다.

★확정 규칙 (세션15, 스테이트 실측)
  VDP2 1워드 패턴네임 + 16×16(2×2셀):
      CN = (SCN[4:2] << 12) | (패턴워드[9:0] << 2) | SCN[1:0]      ← **CN 은 12비트**
      글리프 주소 = CN * 32
    ⇒ 1워드 레이어는 **VRAM 앞 128KB(0x20000)까지만 도달**한다.
       폰트가 VRAM A 에 있으면 도달 글리프 = (0x20000 - A) / 128
          A = 0x1E00 → **964글리프** (세션8-a 「하드 상한 964」의 정체)
          A = 0x0000 → **1024글리프** (사관학교)
       SCN[4:2] 는 128KB 안에서 1024글리프짜리 창을 고르는 것일 뿐 상한을 못 넘긴다.
  2워드 패턴네임(PNCN bit15=0)은 **CN 15비트**라 VRAM 전체(1MB)를 찍는다 ⇒ 이 제한이 없다.
  ⇒ **천장은 「그 텍스트를 그리는 레이어가 1워드냐 2워드냐」로 갈린다.**
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_analyze import rzip_decompress
from vdp1_dump import sections
import charmap

GSZ = 128


def swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def load(state):
    blob, _ = rzip_decompress(state)
    sec = sections(blob)
    ro, rs = sec["RawRegs"][0]
    regs = blob[ro:ro + rs]
    vrams = [swap16(blob[o:o + s]) for name, lst in sec.items()
             for o, s in lst if s == 512 * 1024]
    return regs, vrams


def find_font(vram, probe):
    i = vram.find(probe)
    return (i - 64 * GSZ) if i >= 0 else None


def planes(regs):
    mpofn = struct.unpack_from("<H", regs, 0x3C)[0]
    out = []
    for n in range(4):
        mpab = struct.unpack_from("<H", regs, 0x40 + n * 4)[0]
        hi = (mpofn >> (n * 4)) & 7
        out.append((((hi << 6) | (mpab & 0x3F)) * 0x2000) & 0x7FFFF)
    return out


def analyze(state, probe, tbl):
    regs, vrams = load(state)
    g = lambda a: struct.unpack_from("<H", regs, a)[0]
    bgon = g(0x20)
    pl = planes(regs)
    rows = []
    for vram in vrams:
        A = find_font(vram, probe)
        if A is None:
            continue
        for n in range(4):
            if not (bgon >> n) & 1:
                continue
            v = g(0x30 + n * 2)
            oneword = bool(v & 0x8000)
            scn = v & 0x1F
            base_hi = (scn >> 2) & 7
            # 이 레이어가 실제로 글자를 찍고 있나 — 플레인을 디코드해 판독률을 본다
            plane = pl[n]
            hit = tot = 0
            for c in range(40 * 28):
                w = struct.unpack_from(">H", vram, plane + c * 2)[0]
                if w == 0:
                    continue
                if oneword:
                    cn = (base_hi << 12) | ((w & 0x3FF) << 2) | (scn & 3)
                else:
                    cn = w & 0x7FFF
                idx = (cn * 32 - A) // GSZ
                tot += 1
                if 0 <= idx and tbl.get(idx):
                    hit += 1
            if tot < 20:
                continue
            reach = (0x20000 - A) // GSZ if oneword else (len(vram) - A) // GSZ
            rows.append(dict(nbg=n, oneword=oneword, scn=scn, A=A,
                             judge=hit / tot, cells=tot, reach=reach))
        break
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    probe = None
    from isoread import TRACK1, read_range
    from scan_files import files
    for p, lba, size in files(skip_media=False):
        if p == "/ASC16CG":
            with open(TRACK1, "rb") as f:
                fnt = read_range(f, lba, size)
            probe = fnt[GSZ * 64:GSZ * 70]
    tbl = charmap.CHARS

    base = sys.argv[1] if len(sys.argv) > 1 else "my files"
    print("%-34s %4s %6s %5s %7s %6s %7s" %
          ("스테이트", "NBG", "패턴", "SCN", "판독률", "셀수", "도달글리프"))
    for root, d, fs in os.walk(base):
        for f in sorted(fs):
            if ".state" not in f:
                continue
            st = os.path.join(root, f)
            try:
                rows = analyze(st, probe, tbl)
            except Exception as e:
                continue
            for r in sorted(rows, key=lambda x: -x["judge"]):
                if r["judge"] < 0.25:
                    continue
                print("%-34s %4d %6s %5s %6.0f%% %6d %7d" % (
                    os.path.relpath(st, base)[:34], r["nbg"],
                    "1워드" if r["oneword"] else "2워드", "0x%02x" % r["scn"],
                    100 * r["judge"], r["cells"], r["reach"]))


if __name__ == "__main__":
    main()
