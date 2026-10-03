# -*- coding: utf-8 -*-
"""군적 등록(이름 입력) 화면 `中止` 버튼 → 「중지」 (VDP1 스프라이트 텍스처 제자리 교체, 2026-10-03).

★정체 = `/GMSELDT 0x305C`, 32x16 4bpp 256B — 「決定」(0x2F5C, build_ketei.py) **바로 다음** 256B.
  포맷·팔레트가 같아 실기 통과한 「결정」과 같은 렌더(`render_kr(ramp='dark')`)를 쓴다.
  디스크 전체에 사본 1곳뿐(전수 검색).

빌드: python tools/build_chuushi.py <Track01.bin>            드라이런(+미리보기)
      python tools/build_chuushi.py <Track01.bin> --write    기록
      python tools/build_chuushi.py <Track01.bin> --revert   원상복구
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec
from hangul import render_kr
from fontcompare4 import levels_of_glyph
from build_interm_title import read_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX_OFF = 0x305C
TEX_LEN = 256
KR = '중지'


def gmseldt(path):
    with open(path, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'GMSELDT')
        _, lba, size, _ = hits[0]
        return lba, size, read_file(f, lba, size)


def make_texture():
    lv = [levels_of_glyph(render_kr(c, ramp='dark')) for c in KR]
    out = bytearray(TEX_LEN)
    for y in range(16):
        for x in range(32):
            n = lv[x // 16][y][x % 16]
            i = y * 16 + x // 2
            out[i] = (out[i] & 0x0F) | (n << 4) if x % 2 == 0 else (out[i] & 0xF0) | n
    return bytes(out)


def show(tex, path):
    from PIL import Image
    img = Image.new('L', (32, 16), 0)
    for y in range(16):
        for x in range(32):
            b = tex[y * 16 + x // 2]
            img.putpixel((x, y), ((b >> 4) if x % 2 == 0 else (b & 15)) * 17)
    img.resize((256, 128), Image.NEAREST).save(path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        raise SystemExit(__doc__)
    dst = args[0]
    revert = '--revert' in sys.argv
    write = '--write' in sys.argv or revert
    olba, osize, O = gmseldt(TRACK1)
    orig = O[TEX_OFF:TEX_OFF + TEX_LEN]
    # 앵커: 바로 앞 256B 가 「決定」 텍스처(본체 15 다수) 이고, 이 자리도 같은 분포
    n15 = sum(1 for b in orig for n in (b >> 4, b & 15) if n == 15)
    if not 60 <= n15 <= 160:
        raise SystemExit('★0x%x 가 예상 텍스처가 아니다(15 = %d)' % (TEX_OFF, n15))
    new = make_texture()
    os.makedirs(os.path.join(ROOT, 'work', 'chuushi'), exist_ok=True)
    show(orig, os.path.join(ROOT, 'work', 'chuushi', 'orig.png'))
    show(new, os.path.join(ROOT, 'work', 'chuushi', 'new.png'))
    lba, size, cur = gmseldt(dst)
    if (lba, size) != (olba, osize):
        raise SystemExit('대상의 /GMSELDT 위치가 원본과 다르다')
    print('GMSELDT lba=%d 0x%x → 「%s」' % (lba, TEX_OFF, KR))
    if not write:
        print('드라이런 — 기록 안 함 (--write / --revert).')
        return
    src_b, dst_b = (new, orig) if revert else (orig, new)
    if cur[TEX_OFF:TEX_OFF + TEX_LEN] != src_b:
        raise SystemExit('대조 실패 — %s' % ('패치본이 아님' if revert else '이미 패치됨?'))
    touched = set()
    with open(dst, 'r+b') as w:
        for i in range(TEX_LEN):
            p = TEX_OFF + i
            sec = lba + p // USER
            w.seek(sec * RAW + HDR + p % USER)
            w.write(dst_b[i:i + 1])
            touched.add(sec)
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    _, _, back = gmseldt(dst)
    if back[TEX_OFF:TEX_OFF + TEX_LEN] != dst_b:
        raise SystemExit('독립검증 실패')
    if any(back[i] != cur[i] for i in range(size) if not TEX_OFF <= i < TEX_OFF + TEX_LEN):
        raise SystemExit('범위 밖 변경')
    print('%s 완료 — %d섹터, 독립검증 통과' % ('원상복구' if revert else '기록', len(touched)))


if __name__ == '__main__':
    main()
