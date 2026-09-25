# -*- coding: utf-8 -*-
"""주입 스텁 종단 검증 — 패치된 모듈 이미지를 그대로 적재해 SH-2 인터프리터로 돌린다.

세션7에서 확립한 방법(실기 왕복이 비싸서 도입). 검증 항목:
  1) 종단 경로 — 리터럴 @0x06017778 이 가리키는 주소에서 시작해 트램폴린→스텁을 실제로 실행
  2) 버튼 42장이 파이썬 기준(btn_data.apply_ref)과 바이트 일치
  3) 설정 타이틀이 파이썬 기준과 일치하고, **덧칠 영역 밖은 1바이트도 안 바뀌는가**
  4) 음성 테스트 — 통과해야 할 호출에서는 메모리가 1바이트도 안 바뀌는가
  5) 멱등 — 두 번 칠해도 같은가
  6) 인자(r4/r5/r6)와 스택 보존

메모리는 F: ISO가 아니라 **원본 Track01 + 빌드 계획**으로 구성한다(빌드 전에 돌리는 검증).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btn_data as bd
import btn_stub as bs
import build_buttons as bb
import title_data as td
from isoread import TRACK1, read_range
from sh2sim import CPU, Mem
from state_analyze import find_sections, swap16

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "work", "dbg11", "setmenu.bin")   # 설정 화면 = 타이틀 텍스처가 살아있는 상태

POOL_LO = bd.POOL_BASE                                   # 0x002AD780
POOL_HI = td.TEX_SRC + td.TEX_SIZE                       # 타이틀까지 포함한 끝
STACK_LO, STACK_HI = 0x0603F000, 0x06040000


def patched_modules():
    """원본 모듈에 빌드 계획을 얹은 이미지."""
    out = {}
    with open(TRACK1, "rb") as f:
        for name, lba, size, pl in bb.patches():
            buf = bytearray(read_range(f, lba, size))
            for off, expect, new in pl:
                if bytes(buf[off:off + len(expect)]) != expect:
                    raise SystemExit("원본 불일치 %s 0x%05X" % (name, off))
                buf[off:off + len(new)] = new
            out[name] = bytes(buf)
    return out


def lwram_pool():
    """세이브스테이트에서 실제 텍스처 풀(버튼 42장 + 타이틀)을 가져온다."""
    raw = open(STATE, "rb").read()
    o, s = find_sections(raw, "WorkRAML")[0]
    lw = swap16(raw[o:o + s])
    return bytearray(lw[POOL_LO - 0x00200000:POOL_HI - 0x00200000])


def make_mem(mods, pool):
    m = Mem()
    m.map(bb.MOD0_BASE, mods["/0"])
    m.map(bb.GMDT_BASE, mods["/GMDT"])
    m.map(POOL_LO, pool)
    m.map(STACK_LO, bytes(STACK_HI - STACK_LO))
    return m


def entry_from_literal(mods):
    """리터럴이 가리키는 곳 = 실제로 CPU가 뛰어드는 주소."""
    off = bs.LITERAL_ADDR - bb.MOD0_BASE
    return struct.unpack_from(">I", mods["/0"], off)[0]


def call(mem, entry, dst, src, size):
    cpu = CPU(mem, entry, regs={4: dst, 5: src, 6: size})
    steps = cpu.run(bs.MEMMOVE)
    assert cpu.r[4] == dst and cpu.r[5] == src and cpu.r[6] == size, "인자 파괴"
    assert cpu.r[15] == 0x06040000, "스택 불균형 0x%08X" % cpu.r[15]
    return steps


SENTINEL = 0x06030000        # 보정 경로가 rts로 돌아왔는지 감지할 가짜 복귀주소


def call_fix(mem, entry, dst, src, size):
    """보정 경로(jsr memmove → 목적지 마스킹 → rts) 종단 실행."""
    cpu = CPU(mem, entry, regs={4: dst, 5: src, 6: size})
    cpu.pr = SENTINEL
    cpu.run(bs.MEMMOVE)                      # 스텁이 원본 memmove를 호출한 지점
    for i in range(cpu.r[6]):                # memmove 흉내: src→dst 복사, 반환값 = dst
        mem.w8(cpu.r[4] + i, mem.r8(cpu.r[5] + i))
    cpu.r[0] = cpu.r[4]
    cpu.pc = cpu.pr
    cpu.run(SENTINEL)                        # 보정 끝나고 rts 로 복귀할 때까지
    assert cpu.r[4] == dst and cpu.r[5] == src and cpu.r[6] == size, "보정 경로 인자 파괴"
    assert cpu.r[15] == 0x06040000, "보정 경로 스택 불균형 0x%08X" % cpu.r[15]
    assert cpu.r[0] == dst, "memmove 반환값 파괴 0x%08X" % cpu.r[0]
    return cpu


def region(mem, base, size):
    buf, o = mem._find(base)
    return bytes(buf[o:o + size])


def main():
    mods = patched_modules()
    entry = entry_from_literal(mods)
    print("리터럴 @0x%08X → 0x%08X (트램폴린 0x%08X)" % (bs.LITERAL_ADDR, entry, bb.TRAMP_ADDR))
    assert entry == bb.TRAMP_ADDR, "리터럴이 트램폴린을 안 가리킨다"

    jp_pool = lwram_pool()
    codes = bd.label_codes()
    tmask = td.mask_bytes()

    # --- 1) 버튼 42장 ---
    mem = make_mem(mods, bytearray(jp_pool))
    for slot in range(bd.COUNT):
        src = bd.POOL_BASE + slot * bd.STRIDE
        call(mem, entry, 0x25C00000, src, bd.STRIDE)
    bad = 0
    for slot in range(bd.COUNT):
        o = slot * bd.STRIDE
        want = bd.apply_ref(bytes(jp_pool[o:o + bd.STRIDE]), slot, codes)
        got = region(mem, bd.POOL_BASE + o, bd.STRIDE)
        if want != got:
            bad += 1
            print("  ✗ 슬롯 %d 불일치" % slot)
    print("버튼 %d/%d 일치" % (bd.COUNT - bad, bd.COUNT))

    # --- 2) 설정 타이틀 ---
    jp_tex = bytes(jp_pool[td.TEX_SRC - POOL_LO:td.TEX_SRC - POOL_LO + td.TEX_SIZE])
    steps = call(mem, entry, 0x25C48480, td.TEX_SRC, td.TEX_SIZE)
    got = region(mem, td.TEX_SRC, td.TEX_SIZE)
    want_ref = td.apply_ref(jp_tex, tmask)
    outside = [i for i in range(td.TEX_SIZE)
               if got[i] != jp_tex[i]
               and not (0 <= (i % td.ROW) - td.X0 // 2 < td.ROW_BYTES
                        and td.Y0 <= i // td.ROW < td.Y0 + td.PH)]
    lv = sorted({td._px(got, x, y) for y in range(td.Y0, td.Y0 + td.PH)
                 for x in range(td.X0, td.X0 + td.PW)})
    print("타이틀: 스텁 %d 스텝 / 파이썬 기준 일치 %s / 덧칠영역 밖 변경 %d B / 계조 %d단계 %s"
          % (steps, got == want_ref, len(outside), len(lv), lv))
    if got != want_ref:
        diff = [i for i in range(td.TEX_SIZE) if got[i] != want_ref[i]]
        print("  ✗ 불일치 %d 바이트, 첫 오프셋 0x%X" % (len(diff), diff[0]))

    # --- 3) 멱등 ---
    snap = region(mem, POOL_LO, POOL_HI - POOL_LO)
    for slot in range(bd.COUNT):
        call(mem, entry, 0x25C00000, bd.POOL_BASE + slot * bd.STRIDE, bd.STRIDE)
    call(mem, entry, 0x25C48480, td.TEX_SRC, td.TEX_SIZE)
    print("멱등(두 번 칠해도 동일): %s" % (region(mem, POOL_LO, POOL_HI - POOL_LO) == snap))

    # --- 3.5) 세션13-g 노이즈 보정: 우리 데이터 영역이 목적지에서 0으로 가려지는가 ---
    print("[노이즈 보정]")
    for name, tex_off, tex_len in (("이동범위(520B 텍스처)", 0x26A9C, 0x420),
                                   ("상황판(run4 앞)", 0x0E100, 0x600),
                                   ("run1(코드가 있는 자리)", 0x27F00, 0x900)):
        m2 = make_mem(mods, bytearray(jp_pool))
        dst = 0x25C00000
        m2.map(dst, bytes(0x2000))
        src = bb.GMDT_BASE + tex_off
        call_fix(m2, entry, dst, src, tex_len)
        got = region(m2, dst, tex_len)
        want = bytearray(region(m2, src, tex_len))
        masked = 0
        for start, ln in bd.FIX_REGIONS:      # 우리 영역은 0이어야 한다
            lo = max(start, src); hi = min(start + ln, src + tex_len)
            for i in range(lo - src, hi - src):
                want[i] = 0
                masked += 1
        ok = got == bytes(want)
        nz = sum(1 for start, ln in bd.FIX_REGIONS
                 for i in range(max(start, src) - src, min(start + ln, src + tex_len) - src)
                 if got[i])
        print("  %-22s 마스킹 %4dB / 기준일치 %s / 우리영역에 남은 비영 %d"
              % (name, masked, ok, nz))
        if not ok:
            diff = [i for i in range(tex_len) if got[i] != want[i]]
            print("    ✗ 불일치 %d B, 첫 오프셋 0x%X" % (len(diff), diff[0]))

    # --- 4) 음성 테스트: 아무것도 안 바뀌어야 하는 호출들 ---
    neg = [
        ("크기가 0x100이 아님", 0x002AD780, 0x80),
        ("풀보다 앞", 0x002AD680, 0x100),
        ("타이틀보다 뒤", td.TEX_SRC + td.TEX_SIZE, 0x100),
        ("0x100 경계 아님", 0x002AD790, 0x100),
        ("마스크 없는 슬롯(LOAD)", 0x002AD780 + 0 * 0x100, 0x100),
        ("마스크 없는 슬롯(SAVE)", 0x002AD780 + 2 * 0x100, 0x100),
        ("타이틀 주소 근처(1바이트 어긋남)", td.TEX_SRC + 1, td.TEX_SIZE),
        ("전혀 다른 소스", 0x00260000, 0x100),
    ]
    mem2 = make_mem(mods, bytearray(jp_pool))
    ok = True
    for label, src, size in neg:
        base_snap = region(mem2, POOL_LO, POOL_HI - POOL_LO)   # ★건마다 새로 — 안 그러면 첫 실패가 전염된다
        try:
            call(mem2, entry, 0x25C00000, src, size)
        except KeyError as e:                       # 매핑 밖 소스는 읽지도 않아야 정상
            print("  ✗ %s — 매핑 밖 접근 %s" % (label, e))
            ok = False
            continue
        if region(mem2, POOL_LO, POOL_HI - POOL_LO) != base_snap:
            print("  ✗ %s — 메모리가 바뀌었다" % label)
            ok = False
    print("음성 테스트 %d종: %s" % (len(neg), "전부 무변화" if ok else "실패"))

    # --- 5) GMDT 미상주(매직 불일치) — 트램폴린이 그냥 통과시키는가 ---
    mem3 = make_mem(mods, bytearray(jp_pool))
    buf, o = mem3._find(bb.GMDT_BASE)
    hdr_off = None
    for name, lba, size, pl in bb.patches():
        pass
    # 헤더 위치는 layout()에서 직접 얻는다
    _, _, _, _, hdr_addr, _, _ = bb.layout()
    b2, o2 = mem3._find(hdr_addr)
    b2[o2:o2 + 4] = b"\x00\x00\x00\x00"             # 매직 파괴 = 다른 화면
    snap3 = region(mem3, POOL_LO, POOL_HI - POOL_LO)
    call(mem3, entry, 0x25C00000, bd.POOL_BASE + 4 * 0x100, 0x100)
    call(mem3, entry, 0x25C48480, td.TEX_SRC, td.TEX_SIZE)
    print("매직 불일치(GMDT 미상주) 시 무변화: %s"
          % (region(mem3, POOL_LO, POOL_HI - POOL_LO) == snap3))

    # --- 6) 미리보기 (실제 스프라이트 팔레트 = CRAM 색번호 0x180) ---
    td.preview([jp_tex, got], ["JP", "KR(stub)"],
               path=os.path.join(ROOT, "work", "title_sim.png"))
    print("미리보기 -> work/title_sim.png (위=원본, 아래=스텁 결과)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
