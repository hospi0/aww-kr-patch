# -*- coding: utf-8 -*-
"""시나리오 타이틀(VDP1 스프라이트) 한글화 — /INTERM 제자리 패치 (2026-10-03 재작업).

★위치 = `/INTERM` 파일 오프셋 **0x3DFF8, 스왑 없음**, 320x80 4bpp x 11장(간격 0x3200).
  세이브스테이트 VDP1 텍스처(미션시작.state7, tex 0x33E20)와 12,800B 전부 일치로 확정.
  🐞옛 판(세션19~20)은 0x3E1E0 + swap16 으로 써서 글자가 규칙적으로 끊겼다.
렌더(테두리 2px·오른쪽 위 조명·위/오른쪽 흰 하이라이트)는 `interm_title_kr.py`.

빌드: python tools/build_interm_title.py <Track01.bin>            드라이런(+미리보기)
      python tools/build_interm_title.py <Track01.bin> --write    기록(원본 대조)
      python tools/build_interm_title.py <Track01.bin> --resync   대조 없이 덮어쓰기
      python tools/build_interm_title.py <Track01.bin> --revert   원상복구
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec
import interm_title_kr as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = T.W * T.H // 2


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def interm(path):
    with open(path, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'INTERM')
        _, lba, size, _ = hits[0]
        return lba, size, read_file(f, lba, size)


def plans(D):
    """[(파일 오프셋, 원본 12,800B, 새 12,800B)] x 11장."""
    res = T.render_all(D)
    return [(T.BASE + k * T.STEP, D[T.BASE + k * T.STEP:T.BASE + k * T.STEP + SIZE], T.pack(res[k]))
            for k in sorted(res)], res


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        raise SystemExit(__doc__)
    dst = args[0]
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    olba, osize, D = interm(TRACK1)
    # ★앵커: 원본 텍스처 #0 은 세이브스테이트와 바이트 일치한 그 자리여야 한다
    g0 = T.grid(D, 0)
    if T.top_of(g0) < 40 or sum(1 for v in g0[20] if v) < 50:
        raise SystemExit('★원본 0x%x 가 타이틀 텍스처가 아니다' % T.BASE)
    pl, res = plans(D)
    T.preview(D, res, os.path.join(ROOT, 'work', 'interm_title', 'preview.png'))
    lba, size, cur = interm(dst)
    if (lba, size) != (olba, osize):
        raise SystemExit('대상의 /INTERM 위치가 원본과 다르다(lba %d/%d)' % (lba, olba))
    nb = sum(sum(1 for a, b in zip(o, n) if a != b) for _, o, n in pl)
    print('/INTERM lba=%d — 타이틀 %d장, 바뀌는 바이트 %d' % (lba, len(pl), nb))
    if not write:
        print('드라이런 — 기록 안 함 (--write / --resync / --revert).')
        return
    touched = set()
    with open(dst, 'r+b') as w:
        for off, o, n in pl:
            src_b, dst_b = (n, o) if revert else (o, n)
            if not resync and cur[off:off + SIZE] != src_b:
                raise SystemExit('@0x%x 대조 실패 — %s' % (off, '패치본이 아님' if revert else '이미 패치됨?'))
            for i in range(SIZE):
                p = off + i
                sec = lba + p // USER
                w.seek(sec * RAW + HDR + p % USER)
                w.write(dst_b[i:i + 1])
                touched.add(sec)
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    _, _, back = interm(dst)
    for off, o, n in pl:
        if back[off:off + SIZE] != (o if revert else n):
            raise SystemExit('독립검증 실패 @0x%x' % off)
    outside = [i for i in range(size) if back[i] != cur[i]
               and not any(off <= i < off + SIZE for off, _, _ in pl)]
    if outside:
        raise SystemExit('범위 밖 변경 %d바이트' % len(outside))
    with open(dst, 'rb') as r:
        for sec in sorted(touched):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                raise SystemExit('EDC/ECC 불일치 섹터 %d' % sec)
    print('%s 완료 — %d섹터, 독립검증 통과(범위 밖 변경 0)' % ('원상복구' if revert else '기록', len(touched)))


if __name__ == '__main__':
    main()
