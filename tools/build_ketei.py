# -*- coding: utf-8 -*-
"""`決定` 버튼 → 「결정」 (VDP1 스프라이트 텍스처 직접 교체, 세션13).

★정체 = **GMSELDT 파일 안의 평문 텍스처** — 사용자가 Kronos VDP1 디버거로 잡아준 정보
  (Normal Sprite / texture 0x0007E420 / 32×16 / 4BPP 16색뱅크 / color bank 0x00012380)를
  단서로 스테이트에서 그 256B를 떠서 디스크를 검색했더니 **`/GMSELDT 0x2F5C` 1곳**에 그대로
  있었다. LWRAM 0x00202F5C = 0x200000 + 0x2F5C (GMSELDT가 LWRAM 0x200000에 1:1 적재).
  ⇒ **세션7 전투버튼처럼 코드주입이 필요 없다.** 텍스처 256B를 제자리 교체하면 끝.

★색인 규약 = 폰트 글리프와 동일 **본체 15 / 외곽 1 / 0 투명**(원본 실측).
  화면에서 검정 글자 + 옅은 테두리로 보이는 것과 일치 ⇒ 한글도 **M3 램프(어두운 계조만)** 로
  그리면 톤이 맞는다([[hangul.to_glyph_dark]]).

레이아웃: 32×16 4bpp, 행 16바이트. 왼쪽 16px = 첫 글자, 오른쪽 16px = 둘째 글자.

빌드: python tools/build_ketei.py           드라이런(+미리보기 PNG)
      python tools/build_ketei.py --write    F: ISO 기록
      python tools/build_ketei.py --revert   원상복구
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from hangul import render_kr
from fontcompare4 import levels_of_glyph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
TEX_OFF = 0x2F5C                  # /GMSELDT 안의 텍스처 오프셋 (앵커 검증 후 사용)
TEX_LEN = 256                     # 32×16 4bpp
KR = '결정'


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def make_texture():
    """32×16 4bpp 256바이트 — 한글 2자, 본체15/외곽 어두운계조(M3).

    ⚠️이 버튼은 **세션13-e 실기 통과본 그대로 유지**한다(사용자 지시: 지정한 버튼만 손댈 것).
    """
    lv = [levels_of_glyph(render_kr(c, ramp='dark')) for c in KR]
    out = bytearray(TEX_LEN)
    for y in range(16):
        for x in range(32):
            n = lv[0][y][x] if x < 16 else lv[1][y][x - 16]
            i = y * 16 + x // 2
            if x % 2 == 0:
                out[i] = (out[i] & 0x0F) | (n << 4)
            else:
                out[i] = (out[i] & 0xF0) | n
    return bytes(out)


def show(tex, path):
    from PIL import Image
    img = Image.new('L', (32, 16), 0)
    px = img.load()
    for y in range(16):
        for x in range(32):
            b = tex[y * 16 + x // 2]
            px[x, y] = ((b >> 4) if x % 2 == 0 else (b & 15)) * 17
    img.resize((32 * 8, 16 * 8), Image.NEAREST).save(path)
    print('미리보기 ->', path)


def orig_texture():
    """원본 텍스처(원본 ISO에서). 앵커 = 「본체15·외곽1」 분포 + 첫 행 패턴."""
    f = open(TRACK1, 'rb')
    gl, gsz = [(l, s) for p, l, s in files(skip_media=False) if p == '/GMSELDT'][0]
    d = read_file(f, gl, gsz)
    f.close()
    tex = d[TEX_OFF:TEX_OFF + TEX_LEN]
    nz = sum(1 for b in tex for n in (b >> 4, b & 15) if n)
    n15 = sum(1 for b in tex for n in (b >> 4, b & 15) if n == 15)
    if not (300 <= nz <= 500 and 60 <= n15 <= 140):
        raise SystemExit('★0x%x 가 예상 텍스처가 아니다(비영 %d, 15 %d)' % (TEX_OFF, nz, n15))
    return gl, tex


def main():
    revert = '--revert' in sys.argv
    # --resync: 이미 기록된 (다른) 한글 버전을 새 렌더로 덮는다. 위치는 원본 앵커로 검증돼 있다.
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    gl, orig = orig_texture()
    new = make_texture()
    print('GMSELDT lba=%d, 텍스처 0x%x (%dB) → 「%s」' % (gl, TEX_OFF, TEX_LEN, KR))
    show(new, os.path.join(ROOT, 'work', 'ketei_new.png'))
    show(orig, os.path.join(ROOT, 'work', 'ketei_orig.png'))
    if not write:
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    src, dstb = (new, orig) if revert else (orig, new)
    touched = set()
    with open(dst, 'r+b') as w:
        for k in range(TEX_LEN):
            lo = TEX_OFF + k
            sec = gl + lo // USER
            pos = sec * RAW + HDR + lo % USER
            w.seek(pos)
            if not resync and w.read(1) != src[k:k + 1]:
                raise SystemExit('0x%x 대조실패 — %s'
                                 % (lo, '패치본아님' if revert else '이미패치?'))
            w.seek(pos)
            w.write(dstb[k:k + 1])
            touched.add(sec)
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('%s 완료 — %d섹터' % ('원상복구' if revert else '패치', len(touched)))
    # 독립 되읽기
    with open(dst, 'rb') as r:
        cur = read_file(r, gl, TEX_OFF + TEX_LEN)[TEX_OFF:]
        if cur != dstb:
            raise SystemExit('독립검증 실패 — 되읽기 불일치')
        for sec in sorted(touched):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                raise SystemExit('독립검증 실패 — 섹터 %d EDC/ECC' % sec)
    print('독립검증 통과.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
