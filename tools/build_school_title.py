# -*- coding: utf-8 -*-
"""사관학교 제목·부제 그래픽 한글화 (세션19) — /SCHOOL 제자리 패치.

무엇을 하나
  ① 그래픽 블록(0x0678C4~, 8bpp 8x8 타일)에 한글 타일을 기록한다.
  ② 배치 테이블(0x066A14, 4B/셀)의 **5셀**을 새 타일 329~333 으로 돌린다.
     원본이 中/上 모서리에 쓰던 **공용 빈 타일 116**(45곳 참조)을 한글 획이 덮지
     않게 하기 위한 것. 이걸 빼먹으면 116 을 쓰는 화면이 전부 깨진다.

대상 (school_title_kr 참조)
  제목 4  : 초급/중급/상급전투강의 · 졸업시험
  부제 4  : 병기 이동과 전투에 대해 / 「병기 보충」과「도시 점령」에 대해 /
            「색적효과」와「날씨」에 대해 / 최종능력심사

★크기·LBA·디렉터리 전부 불변인 **제자리 패치**다. 새 타일도 블록 바로 뒤의
  이미 로드되는 빈 영역(파일 0x06CB04~, VRAM 0x059240~)을 쓴다.

빌드: python tools/build_school_title.py            드라이런
      python tools/build_school_title.py --write    F: ISO 기록
      python tools/build_school_title.py --resync   구성 바뀐 재기록
      python tools/build_school_title.py --revert   원상복구
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import school_title_kr as K
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
GLYPH = 64                      # 8bpp 8x8


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def plans(orig):
    """[(오프셋, 원본바이트, 새바이트, 설명)]"""
    out = []
    for t, blob in sorted(K.build().items()):
        o = K.BASE + t * GLYPH
        if orig[o:o + GLYPH] != blob:
            out.append((o, orig[o:o + GLYPH], blob, '타일%d' % t))
    for cell, t in sorted(K.RETARGET.items()):
        o = K.TABLE + cell * 4 + 2
        nb = struct.pack('>H', 0x2A00 + t * 2)
        if orig[o:o + 2] != nb:
            out.append((o, orig[o:o + 2], nb, '배치셀%d→타일%d' % (cell, t)))
    # ★세션19 가 잘못 쓴 옛 타일 자리를 **원본(전부 0)으로 되돌린다.**
    #   plans 는 원본↔목표 비교라 「목표도 0」이면 계획에 안 잡히는데, F: ISO 에는
    #   값이 남아 있어 졸업시험 화면 맨 위에 조각으로 떴다. 명시적으로 넣어야 지워진다.
    for t in getattr(K, 'LEGACY_TILES', []):
        o = K.BASE + t * GLYPH
        out.append((o, orig[o:o + GLYPH], orig[o:o + GLYPH], '옛타일%d 원복' % t))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync

    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'SCHOOL')
        _, lba, size, _ = hits[0]
        orig = read_file(f, lba, size)
    pl = plans(orig)
    ntile = sum(1 for p in pl if p[3].startswith('타일'))
    print('/SCHOOL lba=%d size=%d — 타일 %d개 + 배치셀 %d개'
          % (lba, size, ntile, len(pl) - ntile))
    for o, a, b, tag in pl:
        if not tag.startswith('타일'):
            print('   %-22s 0x%06x  %s → %s' % (tag, o, a.hex(), b.hex()))

    # 관문: 새 타일 자리가 원본에서 비어 있어야 한다(다른 그래픽을 덮으면 안 됨)
    for t in sorted(set(K.RETARGET.values())):
        o = K.BASE + t * GLYPH
        if any(orig[o:o + GLYPH]):
            raise SystemExit('★새 타일 %d(0x%06x) 자리가 비어 있지 않다' % (t, o))
    print('관문 통과 — 새 타일 %s 자리 전부 0' % sorted(set(K.RETARGET.values())))

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for o, a, b, tag in pl:
            src, dstb = (b, a) if revert else (a, b)
            for k in range(len(a)):
                lo = o + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if w.read(1) != src[k:k + 1] and not resync:
                    raise SystemExit('%s @0x%x 대조 실패 — %s'
                                     % (tag, o, '패치본이 아님' if revert else '이미 패치됨?'))
                w.seek(pos)
                w.write(dstb[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)

    # 독립 되읽기
    with open(dst, 'rb') as r:
        cur = read_file(r, lba, size)
    bad = 0
    for o, a, b, tag in pl:
        want = a if revert else b
        if cur[o:o + len(want)] != want:
            bad += 1
            if bad <= 5:
                print('   ★불일치 %s @0x%06x' % (tag, o))
    if bad:
        raise SystemExit('독립검증 실패 %d곳' % bad)
    print('독립검증 통과 — 되읽기 일치 (%d곳)' % len(pl))


if __name__ == '__main__':
    main()
