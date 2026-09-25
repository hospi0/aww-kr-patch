# -*- coding: utf-8 -*-
"""소형폰트 **확장슬롯(230~239) 글리프 누락** 수정 (세션11).

증상: 전투맵 GND 「설원」의 `원`이 깨짐(사용자 실기 스샷). 같은 원인으로
      착**륙**·하**늘**·**더**미·**만**·**안**·**바**다·**호**수·설**원** = 확장 8음절 전부.

원인(확정): 세션5 build_smalltext가 GMDT 소형폰트를 229→240글리프로 늘리면서
  ①디스크립터 size필드(GMDT 0x2AB9C) = 7680  ②GAME 크기상수 2곳 = 1920
  은 패치했는데, **모듈 자체는 175,008B(229글리프분) 그대로**라 확장 글리프 데이터가 없다.
  ⇒ 게임은 "240글리프(7,680B)"라고 믿고 업로드하는데 뒤 344B를 **섹터 슬랙의 쓰레기**에서 읽는다.

수정: 확장 글리프(230~239)를 FO+i*32 에 기록 + **디렉터리 size 175,008→175,352**.
  ★GMDT는 86섹터(176,128B) 할당인데 175,008B만 써서 슬랙 1,120B → 175,352B가 그대로 들어감.
    **재배치 불필요**(파일 끝 섹터 안에서 해결).
  ⚠️슬롯 229는 디스크립터(8B @175,000)라 건드리지 않는다 — 230부터 기록.

빌드: python tools/fix_smallfont_ext.py            드라이런
      python tools/fix_smallfont_ext.py --write     F: ISO 기록
      python tools/fix_smallfont_ext.py --revert    원상복구(size 되돌림 + 확장영역 0)
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import build_smalltext as S
from hangul8comp import glyph8, to_tile
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
MOD = 'GMDT'
FO = S.FONT_FO[MOD]          # 0x28ef8
OLD_N, NEW_N = S.OLD_N, S.NEW_N   # 229, 240
OLD_SIZE = 175008
NEW_SIZE = FO + NEW_N * 32        # 175352


def ext_tiles():
    """확장슬롯(>=OLD_N) 음절 → {slot: 32B 타일}. build_smalltext와 동일 배정."""
    _hdr, rows = S.load_tsv()          # ★(header, rows) 튜플 — 통째로 넘기면 배정이 어긋난다
    slot, n_exp = S.assign_slots(rows)
    out = {}
    for c, i in slot.items():
        if i >= OLD_N:                    # 230~239
            out[i] = (c, to_tile(glyph8(c)))
    return out, slot


def main():
    revert = '--revert' in sys.argv
    write = '--write' in sys.argv or revert
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    tiles, slot = ext_tiles()
    print('확장슬롯 글리프 %d개: %s' % (len(tiles),
          ' '.join('%d=%s' % (i, c) for i, (c, _) in sorted(tiles.items()))))
    print('GMDT size %d → %d (FO=0x%x, %d글리프)' % (OLD_SIZE, NEW_SIZE, FO, NEW_N))

    with open(dst, 'r+b' if write else 'rb') as f:
        hits, rlba, rsize, _ = find_dirrec(f, MOD)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 %d개' % (MOD, len(hits)))
        _, lba, cur_size, rec_off = hits[0]
        print('%s lba=%d 현재 size=%d, 디렉터리 rec@0x%x' % (MOD, lba, cur_size, rec_off))
        alloc = ((cur_size + USER - 1) // USER) * USER
        if NEW_SIZE > ((OLD_SIZE + USER - 1) // USER) * USER:
            raise SystemExit('★할당 섹터 초과 — 재배치 필요(중단)')
        want_size = OLD_SIZE if revert else NEW_SIZE
        if cur_size == want_size:
            print('이미 %s 상태' % ('원본' if revert else '수정됨'))
        if not write:
            print('\n드라이런 — ISO 미기록 (--write / --revert).')
            return

        touched = set()
        # ① 확장 글리프 기록 (revert면 0으로)
        for i in range(OLD_N + 1, NEW_N):        # 230..239
            off = FO + i * 32
            data = bytes(32)
            if not revert and i in tiles:
                data = tiles[i][1]
            for k in range(32):
                lo = off + k
                sec = lba + lo // USER
                f.seek(sec * RAW + HDR + lo % USER)
                f.write(data[k:k + 1])
                touched.add(sec)
        # ② 디렉터리 size 갱신
        rd = bytearray()
        for k in range(0, rsize, USER):
            f.seek((rlba + k // USER) * RAW + HDR)
            rd += f.read(min(USER, rsize - k))
        struct.pack_into('<I', rd, rec_off + 10, want_size)
        struct.pack_into('>I', rd, rec_off + 14, want_size)
        for k in range(0, len(rd), USER):
            sec = rlba + k // USER
            f.seek(sec * RAW + HDR)
            f.write(bytes(rd[k:k + USER]).ljust(USER, b'\x00')[:USER])
            touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            f.seek(sec * RAW)
            raw = f.read(RAW)
            f.seek(sec * RAW)
            f.write(ecc.fix_sector(raw))

    # 독립 검증
    with open(dst, 'rb') as r:
        hits, _, _, _ = find_dirrec(r, MOD)
        _, lba, size, _ = hits[0]
        bad = 0
        if size != want_size:
            bad += 1
            print('  ❌디렉터리 size=%d (기대 %d)' % (size, want_size))
        for i, (c, tile) in sorted(tiles.items()):
            off = FO + i * 32
            got = bytearray()
            for k in range(32):
                lo = off + k
                sec = lba + lo // USER
                r.seek(sec * RAW + HDR + lo % USER)
                got += r.read(1)
            want = bytes(32) if revert else tile
            if bytes(got) != want:
                bad += 1
                print('  ❌슬롯%d(%s) 글리프 불일치' % (i, c))
        for sec in sorted({lba + (FO + i * 32) // USER for i in range(OLD_N + 1, NEW_N)}):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — size %d, 확장 글리프 %d개 일치, EDC/ECC 유효.' % (want_size, len(tiles)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
