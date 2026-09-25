"""MODE1/2352 섹터의 EDC + P/Q ECC 계산.

섹터 배치:
  0..11    sync  00 FF*10 00
  12..15   header (min, sec, frame, mode=01)  ← BCD
  16..2063 user data (2048)
  2064..2067 EDC (LE u32, 0..2063 대상)
  2068..2075 0 (intermediate)
  2076..2247 P parity (172)
  2248..2351 Q parity (104)

★ 이 모듈은 원본 섹터를 그대로 재계산해 바이트 일치하는지 자체검증한 뒤에만 쓴다
  (tools/ecc.py --selftest). 변환 경계는 수정 전에 검증한다.
"""
import struct

# ---- EDC : CRC-32, poly 0x8001801B (reflected) ----
_EDC = []
for i in range(256):
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    _EDC.append(e)


def edc(data):
    c = 0
    for b in data:
        c = (c >> 8) ^ _EDC[(c ^ b) & 0xFF]
    return c & 0xFFFFFFFF


# ---- ECC LUT (Neill Corlett ECM 표준) ----
_F = [0] * 256      # ecc_f_lut
_B = [0] * 256      # ecc_b_lut
for i in range(256):
    j = ((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF
    _F[i] = j
    _B[i ^ j] = i


def _ecc_block(src, major_count, minor_count, major_mult, minor_inc, dest, doff):
    """src 는 sector[12:] 기준. dest[doff..] 에 패리티 기록."""
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = _F[a]
        a = _B[_F[a] ^ b]
        dest[doff + major] = a
        dest[doff + major + major_count] = a ^ b


def fix_sector(raw):
    """raw 2352 B 를 받아 EDC/ECC 재계산해 반환 (MODE1 전용)."""
    s = bytearray(raw)
    assert s[15] == 1, "MODE1 아님: mode=%d" % s[15]
    struct.pack_into("<I", s, 2064, edc(s[0:2064]))
    for i in range(2068, 2076):
        s[i] = 0
    src = memoryview(s)[12:]
    _ecc_block(src, 86, 24, 2, 86, s, 0x81C)     # P parity
    _ecc_block(src, 52, 43, 86, 88, s, 0x8C8)    # Q parity
    return bytes(s)


def selftest(path, samples=200):
    """원본 섹터를 재계산해 바이트 일치하는지 확인."""
    import os, random
    n = os.path.getsize(path) // 2352
    random.seed(1)
    idx = [0, 1, 16, 17, 20] + [random.randrange(n) for _ in range(samples)]
    ok = bad = skip = 0
    with open(path, "rb") as f:
        for i in idx:
            f.seek(i * 2352)
            raw = f.read(2352)
            if len(raw) < 2352 or raw[15] != 1:
                skip += 1
                continue
            if fix_sector(raw) == raw:
                ok += 1
            else:
                bad += 1
                if bad <= 3:
                    r = fix_sector(raw)
                    d = [k for k in range(2064, 2352) if r[k] != raw[k]]
                    print("  섹터 %d 불일치 %d바이트, 첫 위치 %s" % (i, len(d), d[:6]))
    print("selftest: 일치 %d / 불일치 %d / 건너뜀 %d" % (ok, bad, skip))
    return bad == 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, __file__.rsplit("\\", 1)[0])
    from isoread import TRACK1
    selftest(TRACK1)
