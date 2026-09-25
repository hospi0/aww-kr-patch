# -*- coding: utf-8 -*-
"""전투 커맨드 버튼(攻撃/休息/…) 한글화 — 코드주입 패처 (세션7).

버튼은 텍스트가 아니라 VDP1 스프라이트 텍스처이고(세션6-b 이분실험으로 확정),
원본 그래픽은 압축돼 있어 디스크에서 못 찾았다(세션6-c/d). 그래서 압축을 건드리지
않고 **로더 경로에 코드를 주입**해 우회한다.

파이프라인(세션6-d 규명):
    디스크(압축) → 디컴프 → LWRAM 텍스처 풀 → 모듈0 업로더가 VDP1 VRAM으로 복사

풀은 0x002AD780부터 0x100 간격 42개(21라벨 x 2벌). 업로더(0x060175c4)는 복사에
범용 memmove를 쓰는데, 그 주소를 **리터럴 @0x06017778 하나**로 읽는다. 모듈0 안에
memmove를 가리키는 리터럴이 13개 있지만 업로더가 쓰는 건 이것뿐이라, 여기만 바꾸면
텍스처 업로드 경로만 정확히 가로챈다.

주입 자리 — 전부 디스크와 실행 중 RAM 양쪽에서 0임을 세이브스테이트로 확인했다:
    트램폴린 /0    0x2080C (RAM 0x0602C80C)   제로런 230B
    본체+데이터 /GMDT 0x2810C(1560B) · 0x26AD4(464B) · 0x288EC(440B)
모듈0은 항상 상주하고, GMDT가 안 올라온 화면에서는 매직이 안 맞아 트램폴린이 원본
memmove로 그대로 넘긴다.

⚠️드라이런(기본)은 원본 Track01로 메모리 검증만. --write 로 F: ISO 제자리 기록.
  --revert 로 주입 자리를 원본 바이트(전부 0 + 원래 리터럴)로 되돌린다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btn_data as bd
import btn_stub as bs
import title_data as td
from isoread import TRACK1, RAW, HDR, USER, read_range

OUT_ISO_DIR = r"F:\hospi\roms\ss roms\aww"

MOD0_LBA, MOD0_SIZE = 300, 135956
GMDT_LBA, GMDT_SIZE = 824, 175008

MOD0_BASE = 0x0600C000          # 모듈0 적재 주소
GMDT_BASE = 0x00208000          # GMDT 적재 주소(LWRAM)

TRAMP_OFF = 0x2080C             # /0 안의 제로런(0x2080B, 230B)
LIT_OFF = 0xB778                # 업로더가 읽는 memmove 리터럴

# /GMDT 제로런 — (파일오프셋, 용량). 앞에서부터 채운다. 첫 영역에 코드와 헤더가 들어간다.
# ★세션12에서 run4를 추가했다: 타이틀 마스크 240B가 들어가면서 기존 3곳(2,464B)으로는
#   조각남까지 감안하면 모자란다(필요 2,453B). 판정 기준은 세션7과 같다 —
#   **디스크에서 0 + GMDT가 상주하는 세이브스테이트 21개 전부에서 0**.
GMDT_RUNS = [(0x2810C, 1560), (0x26AD4, 464), (0x288EC, 440), (0x0E2D0, 400),
             (0x0EB3C, 405)]     # ★run5 = 세션13-g 추가(보정 기능이 가려준다)

# 되돌릴 때 원본으로 복원할 범위(A안·B안 어느 배치든 덮도록 넉넉히)
REVERT = [
    ("/0", MOD0_LBA, MOD0_SIZE, [(0x2080B, 230), (LIT_OFF, 4)]),
    ("/GMDT", GMDT_LBA, GMDT_SIZE,
     [(0x2810A, 1562), (0x26AD4, 464), (0x288EC, 440), (0x0E2CE, 402), (0x0EB3A, 407)]),
]

TRAMP_ADDR = MOD0_BASE + TRAMP_OFF


def _check_fix_sync():
    """★btn_data.FIX_REGIONS(스텁이 목적지에서 가릴 범위)와 GMDT_RUNS가 같은 집합인가."""
    want = {(GMDT_BASE + o, c) for o, c in GMDT_RUNS}
    if set(bd.FIX_REGIONS) != want:
        raise SystemExit('★FIX_REGIONS ≠ GMDT_RUNS — 보정 안 되는 자리에 데이터를 쓰게 된다: %s'
                         % sorted(want ^ set(bd.FIX_REGIONS)))


def layout():
    _check_fix_sync()
    """코드 크기와 헤더 주소가 서로 물려 있어 안정될 때까지 두 번 돌린다."""
    stub_addr = GMDT_BASE + GMDT_RUNS[0][0]
    hdr_addr = stub_addr                                   # 첫 추정
    for _ in range(4):
        stub, _ = bs.build_stub(stub_addr, hdr_addr)
        new_hdr = (stub_addr + len(stub) + 3) & ~3
        if new_hdr == hdr_addr:
            break
        hdr_addr = new_hdr
    else:
        raise SystemExit("배치가 안정되지 않는다")

    used = hdr_addr - stub_addr
    regions = [("run1", hdr_addr, GMDT_RUNS[0][1] - used)]
    for i, (off, cap) in enumerate(GMDT_RUNS[1:], start=2):
        regions.append(("run%d" % i, GMDT_BASE + off, cap))

    blobs, hdr, ptr, tptr = bd.build(regions)
    if hdr != hdr_addr:
        raise SystemExit("헤더 주소 불일치")
    tramp, _ = bs.build_tramp(TRAMP_ADDR, hdr_addr, stub_addr)
    return stub, stub_addr, tramp, blobs, hdr_addr, ptr, tptr


def patches():
    """(파일명, lba, 파일크기, [(오프셋, 기대원본, 새바이트)]) 목록."""
    stub, stub_addr, tramp, blobs, hdr_addr, ptr, tptr = layout()
    if len(tramp) > 230:
        raise SystemExit("트램폴린이 제로런을 넘는다: %d B" % len(tramp))

    gmdt_plans = []
    parts = []
    for (name, addr, buf) in blobs:
        off = addr - GMDT_BASE
        gmdt_plans.append((off, bytes(len(buf)), buf))
        parts.append("%s 0x%05X %dB" % (name, off, len(buf)))
    # 스텁 코드는 첫 영역 선두에
    gmdt_plans.insert(0, (stub_addr - GMDT_BASE, bytes(len(stub)), stub))

    for off, expect, new in gmdt_plans:
        end = off + len(new)
        if not any(o <= off and end <= o + cap for o, cap in GMDT_RUNS):
            raise SystemExit("GMDT 0x%05X..0x%05X 가 제로런을 벗어난다" % (off, end))

    print("트램폴린 %d B @ /0 0x%05X → RAM 0x%08X (제로런 230 B)"
          % (len(tramp), TRAMP_OFF, TRAMP_ADDR))
    print("본체 스텁 %d B @ /GMDT 0x%05X → RAM 0x%08X" % (len(stub), stub_addr - GMDT_BASE, stub_addr))
    print("데이터 (헤더 RAM 0x%08X, 버튼 마스크 %d종 + 타이틀 마스크 @0x%08X %dB): %s"
          % (hdr_addr, len(ptr), tptr, td.MASK_SIZE, " / ".join(parts)))
    free = sum(cap for _, cap in GMDT_RUNS) - sum(len(b) for _, _, b in gmdt_plans)
    print("GMDT 제로런 잔여 %d B" % free)

    return [
        ("/0", MOD0_LBA, MOD0_SIZE, [
            (TRAMP_OFF, bytes(len(tramp)), tramp),
            (LIT_OFF, struct.pack(">I", bs.MEMMOVE), struct.pack(">I", TRAMP_ADDR)),
        ]),
        ("/GMDT", GMDT_LBA, GMDT_SIZE, gmdt_plans),
    ]


def revert_plans():
    """원본 바이트로 되돌리는 계획(원본 ISO에서 그대로 읽어온다)."""
    out = []
    with open(TRACK1, "rb") as f:
        for name, lba, size, ranges in REVERT:
            buf = read_range(f, lba, size)
            pl = [(off, None, buf[off:off + ln]) for off, ln in ranges]
            out.append((name, lba, size, pl))
    return out


def write_iso(plans, verify_expect=True):
    import ecc
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit("대상 ISO 없음: %s" % dst)
    print("\nF: ISO 제자리 패치: %s" % dst)

    touched = set()
    with open(dst, "r+b") as w:
        for name, lba, size, pl in plans:
            for off, expect, new in pl:
                for k in range(len(new)):
                    lo = off + k
                    sec = lba + lo // USER
                    pos = sec * RAW + HDR + (lo % USER)
                    w.seek(pos)
                    if verify_expect and expect is not None and w.read(1) != expect[k:k + 1]:
                        raise SystemExit("%s 0x%05X 원문 불일치(F:) — 이미 패치됨?" % (name, lo))
                    w.seek(pos)
                    w.write(new[k:k + 1])
                    touched.add(sec)
        print("쓴 섹터 %d개, EDC/ECC 재계산..." % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    with open(dst, "rb") as f:                             # 독립 되읽기 검증
        for name, lba, size, pl in plans:
            buf = read_range(f, lba, size)
            for off, expect, new in pl:
                if buf[off:off + len(new)] != new:
                    raise SystemExit("되읽기 불일치: %s 0x%05X" % (name, off))
    print("되읽기 검증 통과 — 완료 ->", dst)


def build(write=False):
    plans = patches()
    with open(TRACK1, "rb") as f:
        for name, lba, size, pl in plans:
            buf = read_range(f, lba, size)
            for off, expect, new in pl:
                if buf[off:off + len(expect)] != expect:
                    raise SystemExit("원본 %s 0x%05X 불일치" % (name, off))
    print("\n원본 대조 통과 — 주입 자리가 전부 0이고 리터럴도 원본 그대로다.")
    if not write:
        print("드라이런 — ISO 미기록 (--write 로 F: 기록).")
        return
    write_iso(plans)


def revert():
    print("주입 자리를 원본 바이트로 되돌린다 (전부 0 + 원래 memmove 리터럴).")
    write_iso(revert_plans(), verify_expect=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--revert" in sys.argv:
        revert()
    else:
        build(write="--write" in sys.argv)
