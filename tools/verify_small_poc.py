"""소형 폰트 PoC 독립 검증 — **패치된 ISO에서 다시 읽어** 확인한다.

빌더의 자기검사는 못 믿는다([[feedback_kr_patch_verification]]).
검사 항목:
  1) 이미지 크기 불변 · 파일 LBA/크기 불변
  2) 변경 섹터가 대상 파일 범위 안
  3) EDC/ECC 유효
  4) 폰트 5벌이 서로 완전 동일 + 한글 슬롯이 실제로 새 글리프
  5) ★이름표를 되읽어 디코드한 문자열이 의도한 한글과 **정확히** 일치
  6) 손대지 않은 레코드는 원본과 바이트 동일
  7) 심은 한글 슬롯을 렌더해 PNG 로 남긴다
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
import ecc
import smallfont as sf
from build_small_poc import FONT_OFF, TABLE_OFF, STRIDE, EDITS, FREE_SLOTS
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(r'F:\hospi\roms\ss roms\aww', os.path.basename(TRACK1))


def main():
    ok = True

    def chk(cond, msg):
        nonlocal ok
        print(('  OK  ' if cond else '  FAIL') + '  ' + msg)
        ok = ok and bool(cond)

    chk(os.path.getsize(DST) == os.path.getsize(TRACK1), '이미지 크기 불변')
    src = open(TRACK1, 'rb')
    dst = open(DST, 'rb')
    fs = {p: (l, s) for p, l, s in files(skip_media=False)}

    # 2) 변경 섹터가 대상 파일 안인가
    target = set()
    for m in FONT_OFF:
        lba, size = fs['/' + m]
        target |= set(range(lba, lba + (size + USER - 1) // USER))
    changed = []
    nsec = os.path.getsize(TRACK1) // RAW
    for sec in range(nsec):
        src.seek(sec * RAW + HDR)
        dst.seek(sec * RAW + HDR)
        if src.read(USER) != dst.read(USER):
            changed.append(sec)
    chk(changed and set(changed) <= target,
        '변경 섹터 %d개 전부 대상 파일 범위 안' % len(changed))

    # 3) EDC/ECC
    bad = 0
    for sec in changed:
        dst.seek(sec * RAW)
        raw = dst.read(RAW)
        if ecc.fix_sector(raw) != raw:
            bad += 1
    chk(bad == 0, 'EDC/ECC 유효 (불량 %d)' % bad)

    # 4~6) 모듈별 검사
    need = []
    for _, _, kr in EDITS:
        for ch in kr:
            if '가' <= ch <= '힣' and ch not in need:
                need.append(ch)
    slot = {ch: FREE_SLOTS[i] for i, ch in enumerate(need)}
    # ★되읽기는 **패치된 코드표**로 해야 한다. 원본 표로 읽으면 슬롯38이 'b'로 나와
    #  멀쩡한 데이터가 전부 불일치로 뜬다(검사기와 인코더가 어긋난 전형적 사례).
    PATCHED = dict(sf.CHARS)
    PATCHED.update({v: k for k, v in slot.items()})

    def decode_kr(buf, off, n):
        return ''.join(PATCHED.get(b, '<%02x>' % b) for b in buf[off:off + n]).rstrip()

    fonts = {}
    for m, fo in FONT_OFF.items():
        lba, size = fs['/' + m]
        new = read_range(dst, lba, size)
        old = read_range(src, lba, size)
        fonts[m] = new[fo:fo + 176 * 32]
        # 한글 슬롯은 바뀌었고, 나머지 글리프는 그대로여야 한다
        moved = [i for i in range(176)
                 if new[fo + i * 32:fo + i * 32 + 32] != old[fo + i * 32:fo + i * 32 + 32]]
        chk(sorted(moved) == sorted(slot.values()),
            '%-8s 폰트: 바뀐 글리프 %d개 = 배정 슬롯과 정확히 일치' % (m, len(moved)))
        if m in TABLE_OFF:
            off, nrec = TABLE_OFF[m]
            edited = {i for i, _, _ in EDITS if i < nrec}
            diff = [i for i in range(nrec)
                    if new[off + i * STRIDE:off + (i + 1) * STRIDE]
                    != old[off + i * STRIDE:off + (i + 1) * STRIDE]]
            chk(set(diff) == edited, '%-8s 표: 바뀐 레코드 %d개 = 편집 목록과 일치' % (m, len(diff)))
            bad_rt = []
            for ridx, _, kr in EDITS:
                if ridx >= nrec:
                    continue
                got = decode_kr(new, off + ridx * STRIDE, STRIDE)
                if got != kr:
                    bad_rt.append((ridx, kr, got))
            chk(not bad_rt, '%-8s 표: 되읽기 디코드 일치 (불일치 %d)' % (m, len(bad_rt)))
            for r in bad_rt:
                print('        rec%-4d 의도 %r != 실제 %r' % r)

    chk(len(set(fonts.values())) == 1, '폰트 5벌 바이트 완전 동일')

    # 7) 심은 글리프 렌더
    f0 = fonts['GMDT']
    Z = 8
    im = Image.new('L', (len(need) * (8 * Z + 4), 8 * Z), 0)
    for k, ch in enumerate(need):
        i = slot[ch]
        gl = Image.new('L', (8, 8))
        p = gl.load()
        for y in range(8):
            for x in range(0, 8, 2):
                v = f0[i * 32 + y * 4 + x // 2]
                p[x, y] = 255 if v >> 4 else 0
                p[x + 1, y] = 255 if v & 15 else 0
        im.paste(gl.resize((8 * Z, 8 * Z), Image.NEAREST), (k * (8 * Z + 4), 0))
    out = os.path.join(ROOT, 'build', 'verify_small_glyphs.png')
    im.save(out)
    print('  글리프 렌더 ->', out)

    src.close()
    dst.close()
    print('\n' + ('ALL PASS' if ok else '*** 실패 항목 있음 ***'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
