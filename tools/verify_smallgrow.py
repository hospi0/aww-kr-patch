"""소형 폰트 확장 실험 독립 검증 — 패치된 ISO에서 다시 읽는다."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
from build_reloc import find_dirrec
import ecc
import smallfont as sf
from build_smallgrow import PLANS, EDITS, OLD_N, NEW_N, FIRST_NEW, STRIDE, slots
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
    P = dict(sf.CHARS)
    P.update({v: k for k, v in slot.items()})
    dec = lambda b, o: ''.join(P.get(v, '<%02x>' % v) for v in b[o:o + STRIDE]).rstrip()

    target = set()
    fonts = {}
    for m, p in PLANS.items():
        hits, rlba, rsize, _ = find_dirrec(dst, m)
        _, lba, size, rec_off = hits[0]
        ohits, _, _, _ = find_dirrec(src, m)
        _, olba, osize, _ = ohits[0]
        chk(lba == olba, '%-7s lba 불변 (%d)' % (m, lba))
        new = read_range(dst, lba, size)
        old = read_range(src, olba, osize)
        fo = p['fo']
        desc = fo + OLD_N * 32
        ram, sz = struct.unpack_from('>II', new, desc)
        chk(sz == NEW_N * 32, '%-7s 디스크립터 크기 0x%x (=%d글리프)' % (m, sz, sz // 32))

        if p['mode'] == 'extend':
            chk(size == fo + NEW_N * 32, '%-7s 파일 %d -> %d B' % (m, osize, size))
            chk((osize + USER - 1) // USER == (size + USER - 1) // USER, '%-7s 섹터 수 불변' % m)
            rd = read_range(dst, rlba, rsize)
            le = struct.unpack_from('<I', rd, rec_off + 10)[0]
            be = struct.unpack_from('>I', rd, rec_off + 14)[0]
            chk(le == be == size, '%-7s 디렉터리 크기 LE/BE 갱신' % m)
            chk(ram == struct.unpack_from('>I', old, desc)[0], '%-7s RAM 주소 불변' % m)
            base = fo
        else:
            chk(size == osize, '%-7s 파일 크기 불변 (%d)' % (m, size))
            nfo = p['new_fo']
            chk(ram == p['ram_base'] + nfo, '%-7s RAM 주소 0x%08x -> 0x%08x'
                % (m, struct.unpack_from('>I', old, desc)[0], ram))
            chk(new[fo:fo + OLD_N * 32] == old[fo:fo + OLD_N * 32],
                '%-7s 원래 자리 폰트 그대로 (되돌릴 수 있음)' % m)
            base = nfo

        # 기존 229글리프가 신규 위치에 그대로 복사됐는가
        chk(new[base:base + OLD_N * 32] == old[fo:fo + OLD_N * 32],
            '%-7s 기존 글리프 0~228 바이트 완전 동일 (재활용 0건)' % m)
        # 신규 슬롯이 채워졌는가
        filled = [i for i in range(FIRST_NEW, NEW_N)
                  if any(new[base + i * 32: base + i * 32 + 32])]
        chk(sorted(filled) == sorted(slot.values()),
            '%-7s 채워진 신규 글리프 %d개 = 배정과 일치' % (m, len(filled)))
        fonts[m] = new[base:base + NEW_N * 32]

        bad = [(r, kr, dec(new, p['table'] + r * STRIDE))
               for r, _, kr, _ in EDITS if r < p['nrec']
               and dec(new, p['table'] + r * STRIDE) != kr]
        chk(not bad, '%-7s 이름표 되읽기 일치 (불일치 %d)' % (m, len(bad)))
        for b in bad:
            print('        rec%-4d 의도 %r != %r' % b)
        target |= set(range(lba, lba + (size + USER - 1) // USER))
        target |= set(range(rlba, rlba + (rsize + USER - 1) // USER))

    # ⚠️229는 GMDT에서만 디스크립터 8B를 물고 있다(설계상 사용 금지 슬롯) → 비교에서 뺀다
    keys = list(fonts)
    d229 = [i for i in range(NEW_N)
            if fonts[keys[0]][i * 32:(i + 1) * 32] != fonts[keys[1]][i * 32:(i + 1) * 32]]
    chk(d229 == [229], '두 모듈 폰트 동일 (229만 다름 = 설계대로, 차이 %s)' % d229)

    # 손 안 댄 모듈은 원본 그대로인가
    fs = {p: (l, s) for p, l, s in files(skip_media=False)}
    for m in ['SAKUSEN', 'KEKKA', 'INTERM']:
        l, s = fs['/' + m]
        chk(read_range(src, l, s) == read_range(dst, l, s), '%-8s 원본과 바이트 동일' % m)

    changed, bad = [], 0
    for sec in range(os.path.getsize(TRACK1) // RAW):
        src.seek(sec * RAW + HDR)
        dst.seek(sec * RAW + HDR)
        if src.read(USER) != dst.read(USER):
            changed.append(sec)
    chk(changed and set(changed) <= target, '변경 섹터 %d개 전부 대상 범위 안' % len(changed))
    for sec in changed:
        dst.seek(sec * RAW)
        raw = dst.read(RAW)
        if ecc.fix_sector(raw) != raw:
            bad += 1
    chk(bad == 0, 'EDC/ECC 유효 (불량 %d)' % bad)

    f0 = fonts['MUSEUM']
    Z = 8
    im = Image.new('L', (len(need) * (8 * Z + 4), 8 * Z), 0)
    for k, ch in enumerate(need):
        i = slot[ch]
        gl = Image.new('L', (8, 8))
        px = gl.load()
        for y in range(8):
            for x in range(0, 8, 2):
                v = f0[i * 32 + y * 4 + x // 2]
                px[x, y] = 255 if v >> 4 else 0
                px[x + 1, y] = 255 if v & 15 else 0
        im.paste(gl.resize((8 * Z, 8 * Z), Image.NEAREST), (k * (8 * Z + 4), 0))
    out = os.path.join(ROOT, 'build', 'verify_smallgrow_glyphs.png')
    im.save(out)
    print('  신규 글리프 렌더 ->', out)

    src.close()
    dst.close()
    print('\n' + ('ALL PASS' if ok else '*** 실패 항목 있음 ***'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
