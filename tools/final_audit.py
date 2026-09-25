# -*- coding: utf-8 -*-
"""패치본 최종 감사 — **자리마다 그 모듈의 폰트로** 디코드한다 (세션18).

앞선 gen_audit 이 「잔재 17,652」를 낸 것은 두 가지 검출기 버그 때문이었다
([[feedback_scan_coverage_and_detectors]] — 검출기부터 의심하라):
  ① 모듈마다 폰트가 다른데 **모든 폰트로 다 대조**해 SAKUSEN 자리를 ASC16CG 로 읽었다
  ② `ティーガー` 가 `ティーガーⅠ` 의 **부분문자열**이라 긴 쪽이 맞는데도 잔재로 셌다

여기서는
  · 자리 → 파일 → 그 모듈 폰트 하나로만 디코드
  · 겹치는 자리는 **가장 긴 원문**에만 배정
  · 유닛명 표(UPK·MUSEUM 격자)는 예외로 **세 폰트 교차 일치**까지 본다

사용: python tools/final_audit.py
"""
import os
import sys
import json
import struct
import bisect
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap
from isoread import TRACK1, walk, read_sector
from gen_audit import FONTS, _merge, userdata, enc, sources, load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHED = os.path.join(r'F:\hospi\roms\ss roms\aww', os.path.basename(TRACK1))

# 파일(경로 접두) → 그 모듈이 렌더에 쓰는 폰트
FILE_FONT = [
    ('/SAKUSEN', 'SAKUCG'),
    ('/INTERM',  'ASCIMCG'),
    ('/SCHOOL',  'SCHOOL'),
    ('/MUSEUM',  'ASCMSCG'),
    ('/KEKKA',   'ASC16CG'),
    ('/GMDT',    'ASC16CG'),
    ('/GMSELDT', 'ASC16CG'),
    ('/GAME',    'ASC16CG'),
]
SHARED = ('/UPK',)          # 유닛명 표 = 세 폰트 공용
TRIPLE = ('ASC16CG', 'SAKUCG', 'ASCMSCG')
# 폰트 비트맵 파일은 텍스트가 아니다 — 스캔에서 제외한다
FONT_FILES = ('/ASC16CG', '/ASCMSCG', '/ASCIMCG', '/ASCGSCG', '/SAKUCG', '/SCHOOLCG')


def filemap():
    with open(TRACK1, 'rb') as f:
        pvd = read_sector(f, 16)
        rl = struct.unpack_from('<I', pvd, 158)[0]
        rs = struct.unpack_from('<I', pvd, 166)[0]
        fl = [x for x in walk(f, rl, rs) if not x['dir']]
    fl.sort(key=lambda x: x['lba'])
    return fl, [x['lba'] for x in fl]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fl, starts = filemap()

    def which(off):
        lba = off // 2048
        i = bisect.bisect_right(starts, lba) - 1
        if i >= 0 and lba < fl[i]['lba'] + (fl[i]['size'] + 2047) // 2048:
            return fl[i]['path']
        return '?'

    print('ISO 로딩...', flush=True)
    UO = userdata(TRACK1)
    UP = userdata(PATCHED)
    REGS = {k: _merge(v) for k, v in FONTS.items()}
    src = sources()
    # ★긴 원문 우선 — 겹치는 자리를 짧은 쪽이 가로채면 전부 오탐이 된다
    items = sorted(((k, v) for k, v in src.items()), key=lambda t: -len(t[0]))
    claimed = {}
    for jp, kr in items:
        pat = enc(jp)
        if not pat or len(pat) < 4:
            continue
        s = 0
        while True:
            j = UO.find(pat, s)
            if j < 0:
                break
            s = j + 2
            if not any(j + k in claimed for k in range(0, len(pat), 2)):
                for k in range(0, len(pat), 2):
                    claimed[j + k] = None
                claimed[j] = (jp, kr, len(pat))
    tot = Counter()
    bad = []
    for j, v in claimed.items():
        if not v:
            continue
        jp, kr, n = v
        path = which(j)
        if any(path.startswith(x) for x in FONT_FILES):
            tot['(폰트파일 제외)'] += 1
            continue
        b = UP[j:j + n]
        if b == enc(jp):
            tot['①미번역'] += 1
            bad.append(('미번역', path, jp, kr, jp))
            continue
        idx = [struct.unpack_from('>H', b, i)[0] for i in range(0, n, 2)]
        if any(x in path for x in SHARED):
            outs = {f: ''.join(REGS[f].get(x) or charmap.CHARS.get(x, '〈%d〉' % x)
                               for x in idx) for f in TRIPLE}
            vals = {v.rstrip('　 ') for v in outs.values()}
            if len(vals) == 1 and vals.pop() == kr.rstrip():
                tot['②정상(공용)'] += 1
            else:
                tot['③불일치(공용)'] += 1
                bad.append(('공용불일치', path, jp, kr, str(outs)))
            continue
        font = next((f for p, f in FILE_FONT if path.startswith(p)), None)
        if font is None:
            tot['(폰트미상 %s)' % path] += 1
            continue
        d = ''.join(REGS[font].get(x) or charmap.CHARS.get(x, '〈%d〉' % x) for x in idx)
        if d.rstrip('　 ') == kr.rstrip():
            tot['②정상'] += 1
        else:
            tot['③불일치'] += 1
            bad.append((font, path, jp, kr, d))
    print('\n=== 집계 ===')
    for k, v in sorted(tot.items(), key=lambda t: -t[1]):
        print('  %-22s %6d' % (k, v))
    print('\n=== ③불일치 / ①미번역 상위 ===')
    c = Counter((t[0], t[2], t[3], t[4]) for t in bad)
    for (f, jp, kr, d), n in c.most_common(30):
        print('  %5d  [%-11s] %-14s 기대=%-12s 현재=%s' % (n, f, jp, kr, d[:44]))
    print('\n문제 %d자리 / %d종' % (len(bad), len(c)))


if __name__ == '__main__':
    main()
