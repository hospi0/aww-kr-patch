"""폰트 천장 역산 — 스테이트의 VDP2 VRAM 에서 폰트를 찾아 도달 가능 글리프 수를 계산한다.

★확정 공식 (세션15, 1.state 로 실측 검증)
  VDP2 패턴네임 **1워드** 모드(PNCN bit15=1) + 16×16(2×2셀) 문자:
      문자번호 CN = (SCN[4:2] << 12) | (패턴워드[9:0] << 2) | SCN[1:0]
      글리프 주소 = CN * 32,  16×16 4bpp 글리프 1개 = 128B = CN 4칸
  ⇒ **패턴워드의 문자번호 필드는 10비트**이므로 한 화면이 가리킬 수 있는 글리프는
     폰트 시작 VRAM 주소를 A 라 할 때  **idx_max = 1023 - A/128**.
       A=0x0000 → 1024글리프 (SCHOOL)
       A=0x1E00 → 1023-60 = 963 → **964글리프** (ASC16CG 하드상한, 세션8-a와 일치)
  ★즉 천장은 「빈 VRAM 이 얼마나 있나」가 아니라 **10비트 필드가 어디까지 닿나**로 정해진다.
    다만 폰트 뒤에 다른 데이터(텍스트 맵 등)가 있으면 그쪽이 먼저 막는다 —
    ASCGSCG 가 텍스트맵 0x1E000 때문에 900 에서 막힌 게 그 사례.
  ⇒ **천장 = min(charnum 상한, 다음 데이터까지의 VRAM 여유).**

사용: python tools/budget_ceiling.py <state> <폰트파일> [폰트내오프셋]
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
from state_analyze import rzip_decompress
from vdp1_dump import sections

GSZ = 128


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


def swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def vdp2_vram(blob, sec):
    """VDP2 VRAM(512KB, swap16 저장) 섹션을 고른다 — VDP1 것과 구분해야 한다."""
    out = []
    for name, lst in sec.items():
        for o, s in lst:
            if s == 512 * 1024:
                out.append((name, o, swap16(blob[o:o + s])))
    return out


def analyze(state, fontfile, foff=0, quiet=False):
    font = get(fontfile)[foff:]
    blob, _ = rzip_decompress(state)
    sec = sections(blob)
    ro, rs = sec["RawRegs"][0]
    regs = blob[ro:ro + rs]

    probe = font[GSZ * 64: GSZ * 70]          # 잉크 있는 글리프로 탐침
    for name, o, vram in vdp2_vram(blob, sec):
        i = vram.find(probe)
        if i < 0:
            continue
        A = i - 64 * GSZ
        if A < 0:
            continue
        # ⚠️스테이트는 **패치본**이라 원본 폰트와 바이트가 갈린다.
        #    「원본과 일치하는 개수」를 폰트 길이로 쓰면 안 된다(한글 글리프에서 끊긴다).
        #    ⇒ 내용이 있는 글리프가 어디까지 이어지는지로 잰다:
        #      빈 글리프 8개가 연속되면 폰트 끝으로 보고, 그 뒤 첫 비영 바이트가 다음 데이터.
        g = 0
        last_ink = -1
        blank = 0
        while A + (g + 1) * GSZ <= len(vram):
            gl = vram[A + g * GSZ: A + (g + 1) * GSZ]
            if any(gl):
                last_ink = g
                blank = 0
            else:
                blank += 1
                if blank >= 8:
                    break
            g += 1
        n = last_ink + 1
        end = A + n * GSZ
        z = end
        while z < len(vram) and vram[z] == 0:
            z += 1
        cn_cap = 1024 - A // GSZ                    # 10비트 필드 상한
        vram_cap = n + (z - end) // GSZ             # 다음 데이터까지
        ceil = min(cn_cap, vram_cap)
        if not quiet:
            print("  VRAM 0x%05X  올라간 글리프 %d개" % (A, n))
            print("    charnum 10비트 상한 = %d글리프   VRAM 여유까지 = %d글리프 (다음 데이터 0x%05X)"
                  % (cn_cap, vram_cap, z))
            print("    ⇒ **천장 = %d글리프**  (현재 %d → 전면한글화 기준 가용 %d칸)"
                  % (ceil, n, ceil))
        return dict(vram=A, loaded=n, cn_cap=cn_cap, vram_cap=vram_cap, ceiling=ceil)
    if not quiet:
        print("  ⚠️ 이 스테이트에 해당 폰트 없음")
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    state = sys.argv[1]
    fontfile = sys.argv[2]
    foff = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
    print("%s  <-  %s" % (fontfile, os.path.basename(state)))
    analyze(state, fontfile, foff)


if __name__ == "__main__":
    main()
