"""실험 3 독립 검증 — 패치된 ISO에서 다시 읽는다.

⚠️ 이 파일은 UTF-8. PowerShell Get-Content/Set-Content/Out-File 로 편집하지 말 것(한글이 깨진다).
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
from build_reloc import find_dirrec
import ecc
import smallfont as sf
from build_smallreloc import (MOD, RAM_BASE, FO, NFO, ADDR_REFS, SIZE_REF, SIZE_CODE,
                              OLD_N, NEW_N, FIRST_NEW, TABLE, NREC, STRIDE, EDITS,
                              MARKER_SLOT, marker_tile, slots)
from hangul8comp import glyph8, to_tile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(r'F:\hospi\roms\ss roms\aww', os.path.basename(TRACK1))


def main():
    ok = True

    def chk(c, m):
        nonlocal ok
        print(('  OK  ' if c else '  FAIL') + '  ' + m)
        ok = ok and bool(c)

    chk(os.path.getsize(DST) == os.path.getsize(TRACK1), '이미지 크기 불변')
    src = open(TRACK1, 'rb')
    dst = open(DST, 'rb')
    need, slot = slots()

    hits, rlba, rsize, _ = find_dirrec(dst, MOD)
    _, lba, size, _ = hits[0]
    ohits, _, _, _ = find_dirrec(src, MOD)
    _, olba, osize, _ = ohits[0]
    chk(lba == olba and size == osize, '%s lba/크기 불변 (%d, %d B)' % (MOD, lba, size))
    new = read_range(dst, lba, size)
    old = read_range(src, olba, osize)

    for off in ADDR_REFS:
        chk(struct.unpack_from('>I', new, off)[0] == RAM_BASE + NFO,
            '주소 상수 0x%x -> 0x%08x' % (off, RAM_BASE + NFO))
    chk(struct.unpack_from('>I', new, SIZE_REF)[0] == NEW_N * 32,
        '크기 필드(디스크립터) 0x%x -> 0x%x' % (SIZE_REF, NEW_N * 32))
    chk(struct.unpack_from('>H', new, SIZE_CODE)[0] == NEW_N * 32 // 4,
        '크기 상수(코드 0x%x) = 0x%04x  롱워드 %d = %d글리프'
        % (SIZE_CODE, NEW_N * 32 // 4, NEW_N * 32 // 4, NEW_N))
    left = [o for o in range(0, len(new) - 4)
            if new[o:o + 4] == struct.pack('>I', RAM_BASE + FO)]
    chk(not left, '옛 폰트 주소 잔존 0곳 (남으면 %s)' % [hex(o) for o in left[:5]])

    # 원래 자리는 손대지 않았는가 (이분 실험의 대조)
    chk(new[FO:FO + OLD_N * 32] == old[FO:FO + OLD_N * 32],
        '원래 자리 폰트 원본 그대로 (재배치 실패 시 A가 그대로 보인다)')

    exp = bytearray(old[FO:FO + OLD_N * 32]) + bytearray((NEW_N - OLD_N) * 32)
    exp[MARKER_SLOT * 32:MARKER_SLOT * 32 + 32] = marker_tile()
    for ch, i in slot.items():
        exp[i * 32:i * 32 + 32] = to_tile(glyph8(ch))
    chk(new[NFO:NFO + NEW_N * 32] == bytes(exp),
        '재배치본 = 원본 + 표식1 + 한글%d' % len(need))
    diff = [i for i in range(OLD_N)
            if new[NFO + i * 32:NFO + (i + 1) * 32] != old[FO + i * 32:FO + (i + 1) * 32]]
    chk(diff == [MARKER_SLOT], '기존 글리프 중 바뀐 것은 표식 %s 뿐 (%s)'
        % (sf.CHARS[MARKER_SLOT], diff))

    P = dict(sf.CHARS)
    P.update({v: k for k, v in slot.items()})
    bad = [(r, kr, ''.join(P.get(v, '<%02x>' % v)
                           for v in new[TABLE + r * STRIDE:TABLE + (r + 1) * STRIDE]).rstrip())
           for r, _, kr in EDITS if r < NREC]
    bad = [b for b in bad if b[1] != b[2]]
    chk(not bad, '이름표 되읽기 일치 (불일치 %d)' % len(bad))
    for b in bad:
        print('        rec%-4d 의도 %r != %r' % b)

    fs = {p: (l, s) for p, l, s in files(skip_media=False)}
    for m in ['GMDT', 'SAKUSEN', 'KEKKA', 'INTERM', 'GAME']:
        l, s = fs['/' + m]
        chk(read_range(src, l, s) == read_range(dst, l, s), '%-8s 원본과 바이트 동일' % m)

    target = set(range(lba, lba + (size + USER - 1) // USER))
    changed, badsec = [], 0
    for sec in range(os.path.getsize(TRACK1) // RAW):
        src.seek(sec * RAW + HDR)
        dst.seek(sec * RAW + HDR)
        if src.read(USER) != dst.read(USER):
            changed.append(sec)
    chk(changed and set(changed) <= target,
        '변경 섹터 %d개 전부 %s 안' % (len(changed), MOD))
    for sec in changed:
        dst.seek(sec * RAW)
        raw = dst.read(RAW)
        if ecc.fix_sector(raw) != raw:
            badsec += 1
    chk(badsec == 0, 'EDC/ECC 유효 (불량 %d)' % badsec)

    Z = 8
    show = [MARKER_SLOT] + [slot[c] for c in need]
    im = Image.new('L', (len(show) * (8 * Z + 4), 8 * Z), 0)
    for k, i in enumerate(show):
        gl = Image.new('L', (8, 8))
        px = gl.load()
        for y in range(8):
            for x in range(0, 8, 2):
                v = new[NFO + i * 32 + y * 4 + x // 2]
                px[x, y] = 255 if v >> 4 else 0
                px[x + 1, y] = 255 if v & 15 else 0
        im.paste(gl.resize((8 * Z, 8 * Z), Image.NEAREST), (k * (8 * Z + 4), 0))
    out = os.path.join(ROOT, 'build', 'verify_smallreloc_glyphs.png')
    im.save(out)
    print('  표식+한글 렌더 ->', out)

    src.close()
    dst.close()
    print('\n' + ('ALL PASS' if ok else '*** 실패 항목 있음 ***'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
