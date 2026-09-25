# -*- coding: utf-8 -*-
"""회수 슬롯 안전성 검증 — build_ui16 --write **전에** 반드시 돌린다 (세션14).

무엇을 검사하나
  build_ui16이 한글로 재정의할 「회수 슬롯」(원본 글리프 인덱스)을, **패치 후에도
  일본어로 남는 텍스트가 참조하는지** 본다. 하나라도 걸리면 그 화면이 깨진다.

왜 asc16_reclaim의 census만으론 부족한가
  census는 **현재 F: ISO**를 읽는다. 그런데 재빌드 절차는
      reset_ui16_region.py (풀 윈도우를 **원본 일본어로 되돌림**)  →  build_ui16 --write
  이다. 리셋이 되살린 원본 일본어 중 **우리 번역표에 없는 것**은 그대로 남는다.
  census 시점의 F:에는 그 자리가 (영문/한글로 패치돼) 없었으므로 census가 못 본다.
  ⇒ 「리셋이 되살리는 원본 바이트」를 기준으로 다시 검사해야 한다.
     (세션11의 「리셋 사각지대」 사고와 같은 부류를 반대 방향에서 막는 것.)

검사 방법
  ① 6개 풀 윈도우의 **원본 바이트**를 가져온다(reset이 되쓸 바로 그 내용).
  ② build_ui16의 계획(plan)을 적용해 **패치 후 최종 상태**를 메모리에 만든다.
  ③ 그 최종 상태에서 회수 슬롯 인덱스가 하나라도 나오면 실패로 보고한다.
  ④ 덤으로 회수 슬롯이 **폰트 범위 안(1..824)** 이고 서로 안 겹치는지도 확인한다.

사용:  python tools/verify_reclaim.py
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ui16 as B
import ui16_kr as K
import asc16_reclaim
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    cm, rev = B.load_map()
    slot = B.build_slots()
    reclaim = sorted(g for g in slot.values() if g < B.OLD_N)
    print('\n회수 슬롯 %d칸 = %s\n'
          % (len(reclaim), ' '.join('%d:%s' % (g, cm.get(g, '?')) for g in reclaim)))

    bad = 0
    # ④ 범위·중복
    if len(set(slot.values())) != len(slot):
        print('  ❌슬롯 중복 배정'); bad += 1
    for g in reclaim:
        if not (1 <= g < B.OLD_N):
            print('  ❌회수 슬롯 %d 범위 밖' % g); bad += 1

    f = open(TRACK1, 'rb')
    plans, mods = B.plan_text(f, rev, slot)

    # ①② 풀 윈도우 = 원본 바이트에 계획 적용
    ent = {p: (l, s) for p, l, s in files(skip_media=False)}
    wins = []
    for mod, anchor, back, fwd, tbl, wr in B.POOLS:
        lba, size = ent['/' + mod]
        d = bytearray(B.read_file(f, lba, size))
        ab = B.enc_jp(anchor, rev)
        i = d.find(bytes(ab))
        lo, hi = max(0, i - back), min(len(d), i + len(ab) + fwd)
        wins.append((mod, lo, hi, d))
    f.close()

    patched = {}
    ours = {}                       # ★우리가 쓴 바이트 범위 = 검사 제외
    for mod, lo, hi, d in wins:
        cur = patched.setdefault(mod, d)
        mine = ours.setdefault(mod, set())
        for pmod, o, raw, nb, jp, kr in plans:
            if pmod == mod:
                cur[o:o + len(nb)] = nb
                mine.update(range(o, o + len(nb)))

    rset = set(reclaim)
    print('── 패치 후 풀 윈도우에 회수 슬롯이 남는가 ──')
    print('   (우리가 쓴 한글 자리는 제외 — 거긴 회수 슬롯을 쓰는 게 정상이다)')
    for mod, lo, hi, _ in wins:
        d = patched[mod]
        mine = ours[mod]
        hitlist = []
        for off in range(lo, hi, 2):
            if off in mine:
                continue
            w = struct.unpack_from('>H', d, off)[0]
            if w in rset:
                ctx = ''.join(cm.get(x, '·' if x else ' ')
                              for x in (struct.unpack_from('>H', d, k)[0]
                                        for k in range(max(lo, off - 16), min(hi, off + 18), 2)))
                hitlist.append((off, w, ctx))
        if hitlist:
            bad += len(hitlist)
            print('  ❌%-5s 0x%06x..0x%06x — 회수 슬롯 참조 %d건' % (mod, lo, hi, len(hitlist)))
            for off, w, ctx in hitlist[:8]:
                print('       0x%06x  %d:%s   …%s…' % (off, w, cm.get(w, '?'), ctx))
        else:
            print('  ✅%-5s 0x%06x..0x%06x — 참조 0' % (mod, lo, hi))

    if bad:
        raise SystemExit('\n★검증 실패 %d건 — 회수 슬롯을 줄이거나 번역표를 손볼 것.' % bad)
    print('\n검증 통과 — 패치 후 풀 윈도우에 회수 슬롯 참조 0, 슬롯 배정 정상.')
    print('⚠️단, 풀 윈도우 **밖**의 소비자는 asc16_reclaim census가 담당한다(정적 추정).')
    print('  실기에서 일본어 화면(사관학교 제외)에 엉뚱한 한글이 뜨는지 확인할 것.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
