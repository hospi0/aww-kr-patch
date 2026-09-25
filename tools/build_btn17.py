# -*- coding: utf-8 -*-
"""시나리오 화면 버튼 그래픽 17종 한글화 — ISO 기록 (세션17).

세션7 커맨드 버튼과 달리 **디스크에 무압축**으로 있어 코드주입 없이 제자리 패치한다.
(처음엔 압축으로 오판했다 — 세이브스테이트의 VDP1 VRAM·WorkRAM·CRAM 이 **swap16 저장**이라
 그 상태의 바이트로 디스크를 뒤져 0건이 나왔던 것. 스왑을 푸니 그대로 나왔다.)

렌더 방식(사용자 확정 2026-07-26):
  · 104×40 버튼 12종 = **배경색 획 + 가장자리 계조 음영**(감마 0.35, +60/−95, 14px)
  · 144×40 배너 4종  = **흰 획 + 검은 그림자**(목표값 수렴), 16px, 자간 86%, 왼쪽 위 정렬
  · 32×32 開発中     = 밝은 양각(배너와 같은 계조), 12px
팔레트 명도는 `work/btn17_lum.json` 에 **상수로 캐시**한다 — 스테이트 없이도 빌드되게
(세션13-e 교훈). ⚠️인터미션 8종과 開発中은 `/MUSEUM`·`/SAKUSEN` **양쪽 사본**에 쓴다.

빌드: python tools/build_btn17.py            드라이런
      python tools/build_btn17.py --write     F: ISO 기록
      python tools/build_btn17.py --resync    재기록
      python tools/build_btn17.py --revert    원상복구
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import btn17_render as R
from btn17_data import BUTTONS
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
LUM = json.load(open(os.path.join(ROOT, 'work', 'btn17_lum.json')))


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def render_all():
    """[(파일, 오프셋, 원본, 새것, 이름)] — 사본은 각각 한 항목."""
    plans = []
    for row in BUTTONS:
        jp, kr, W, H, bpp, locs = row
        if (W, H) == (144, 40):
            # ★배너는 금색·어두운 **두 팔레트**로 그려진다 — 둘 다 넘겨야 색 대비가 맞는다
            lum = LUM['banner']
            new, _ = R.draw_banner(row, lum, LUM['banner_gold'])
        elif (W, H) == (32, 32):
            lum = LUM['k32']
            R.FONT_PX = R.K32_PX
            new, _ = R.draw(row, lum)
        else:
            lum = LUM['btn104']
            R.FONT_PX = 14
            new, _ = R.draw(row, lum)
        old = R.get_tex(row)
        if new == old:
            print('  ⚠️%s 변화 없음' % jp)
            continue
        for p, off in locs:
            plans.append((p, off, old, new, '%s→%s' % (jp, kr)))
    return plans


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    plans = render_all()
    print('버튼 %d종 / 기록 대상 %d곳(사본 포함)'
          % (len(BUTTONS), len(plans)))
    bym = {}
    for p, off, old, new, nm in plans:
        bym.setdefault(p, []).append((off, old, new, nm))
    for p, lst in bym.items():
        print('   %-10s %d곳' % (p, len(lst)))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    m = {q: (l, s) for q, l, s in files(skip_media=False)}
    nsec = 0
    for p, lst in bym.items():
        lba, size = m[p]
        with open(dst, 'r+b') as f:
            buf = bytearray(read_file(f, lba, size))
            for off, old, new, nm in lst:
                src, dstb = (new, old) if revert else (old, new)
                if not resync and bytes(buf[off:off + len(old)]) != src:
                    raise SystemExit('★%s 0x%06X 대조 실패 — 중단 (%s)' % (p, off, nm))
                buf[off:off + len(old)] = dstb
            secs = sorted({(off + k) // USER for off, old, _n, _ in lst
                           for k in range(len(old))})
            for s in secs:
                f.seek((lba + s) * RAW)
                raw = bytearray(f.read(RAW))
                raw[HDR:HDR + USER] = buf[s * USER:(s + 1) * USER]
                f.seek((lba + s) * RAW)
                f.write(ecc.fix_sector(raw))
            nsec += len(secs)
    print('쓴 섹터 %d개, EDC/ECC 재계산...' % nsec)
    bad = 0
    with open(dst, 'rb') as f:
        for p, lst in bym.items():
            lba, size = m[p]
            back = read_file(f, lba, size)
            for off, old, new, nm in lst:
                want = old if revert else new
                if back[off:off + len(old)] != want:
                    print('   ❌%s 0x%06X %s' % (p, off, nm))
                    bad += 1
    print('독립검증 %s' % ('통과 — 되읽기 일치' if bad == 0 else '❌실패 %d곳' % bad))


if __name__ == '__main__':
    main()
