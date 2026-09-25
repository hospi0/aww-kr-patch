# -*- coding: utf-8 -*-
"""세션11 — RetroArch(Beetle Saturn) RZIP 세이브스테이트에서 화면 텍스트 레이어를 뽑는다.

목적: 저장/로드/설정/전투 화면이 **어느 NBG 레이어·어느 맵·어느 폰트 char base**를
읽는지 VDP2 레지스터(RawRegs, 512B LE)로 확정하고, VDP2 VRAM의 패턴네임을 디코드해
**화면에 실제로 뜬 문자열**을 복원한다. 그 문자열을 모듈에서 역검색하면 사본을 짚는다.

RZIP: '#RZIPv\\x01#'(8) + chunkSize(u32 LE) + total(u64 LE) + 반복[csz(u32 LE)][zlib].
Mednafen/Beetle 섹션 = <u8 namelen><name><u32le size><data>. VRAM/WorkRAM은 swap16 저장.
16×16 폰트: charnum = base + idx*4 (base=240 → glyph0=char960 아님; 실제 idx = (char-base)//4).
"""
import os, sys, struct, zlib, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def rzip_decompress(path):
    d = open(path, 'rb').read()
    assert d[:6] == b'#RZIPv', d[:8]
    chunk = struct.unpack_from('<I', d, 8)[0]
    total = struct.unpack_from('<Q', d, 12)[0]
    p = 20
    out = bytearray()
    while p + 4 <= len(d) and len(out) < total:
        csz = struct.unpack_from('<I', d, p)[0]
        p += 4
        if csz == 0 or p + csz > len(d):
            break
        try:
            out += zlib.decompress(d[p:p + csz])
        except zlib.error:
            # 세션8-a 교훈: 뒤쪽 청크가 손상돼도 앞은 쓸 수 있다
            try:
                out += zlib.decompressobj().decompress(d[p:p + csz])
            except zlib.error:
                break
        p += csz
    return bytes(out[:total]), total


def find_sections(raw, name):
    """<u8 len><name><u32le size> 헤더 스캔 → [(off_data, size)]."""
    out = []
    nm = name.encode('ascii')
    pat = bytes([len(nm)]) + nm
    pos = 0
    while True:
        i = raw.find(pat, pos)
        if i < 0:
            break
        pos = i + 1
        hdr = i + 1 + len(nm)
        if hdr + 4 > len(raw):
            continue
        size = struct.unpack_from('<I', raw, hdr)[0]
        if 0 < size <= len(raw) - (hdr + 4):
            out.append((hdr + 4, size))
    return out


def swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def analyze(path):
    blob, total = rzip_decompress(path)
    print('== %s ==  해제 %d/%d' % (os.path.basename(path), len(blob), total))
    regs = find_sections(blob, 'RawRegs')
    vrams = find_sections(blob, 'VRAM')
    rams = find_sections(blob, 'RAM')
    print('  RawRegs:', [(hex(o), s) for o, s in regs],
          ' VRAM:', [(hex(o), s) for o, s in vrams],
          ' RAM:', [(hex(o), s) for o, s in rams])
    return blob, regs, vrams, rams


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    STDIR = r'D:\hospi\RetroArch\states\Beetle Saturn'
    BASE = 'Advanced World War - Sennen Teikoku no Koubou - Last of the Millennium (Japan) (Rev B) (22M)'
    labels = {'state10': '전투제', 'state11': '세이브', 'state8': '로드', 'state9': '설정'}
    outdir = os.path.join(ROOT, 'work', 'dbg11')
    os.makedirs(outdir, exist_ok=True)
    for st, lab in labels.items():
        p = os.path.join(STDIR, BASE + '.' + st)
        blob, regs, vrams, rams = analyze(p)
        open(os.path.join(outdir, '%s_%s.bin' % (st, lab)), 'wb').write(blob)
