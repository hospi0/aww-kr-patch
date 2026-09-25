# -*- coding: utf-8 -*-
"""패치본 ISO 전수 — 「어느 세대의 인덱스로 쓰였나」 감사 (세션18).

배경: 세션17-c가 공용 유닛명 슬롯을 재배정했는데 **일부 빌더만 재기록**해서
      같은 원문의 사본들이 서로 다른 세대의 인덱스로 남았다.
      화면은 사본마다 다른 것을 읽으므로 「표는 맞는데 화면은 깨진다」가 된다.

판정: 원문 문자열 S 의 원본 바이트열이 있던 **모든 자리**를 원본 ISO에서 찾고,
      패치본의 같은 자리를 다음 4가지로 분류한다.
        ① 원문 그대로      = 미번역
        ② 현재 계획값      = 정상 (등록부로 디코드하면 기대 역어)
        ③ 그 외            = ★옛 세대 잔재 (화면이 깨진다)
      ③이 이 사고의 지문이다.

사용: python tools/gen_audit.py [--full]
"""
import os
import sys
import json
import struct
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap
from isoread import TRACK1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHED = os.path.join(r'F:\hospi\roms\ss roms\aww', os.path.basename(TRACK1))
REV = {v: k for k, v in charmap.CHARS.items()}


def load(n):
    p = os.path.join(ROOT, 'work', n)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


# ★폰트별 등록부는 **여러 파일의 병합**이다 (degarble.REGISTRIES 와 같은 구성).
#   단독 파일로만 대조하면 병합 인코딩된 정상 텍스트를 「잔재」로 오판한다
#   ([[feedback_scan_coverage_and_detectors]] — 검출기부터 의심하라).
FONTS = {
    'ASC16CG': ['asc16_slots.json', 'shared_unit_slots.json', 'shared_school_slots.json'],
    'SAKUCG':  ['sakucg_slots.json', 'shared_unit_slots.json'],
    'ASCMSCG': ['museum_slots.json', 'shared_unit_slots.json'],
    'ASCIMCG': ['ascimcg_slots.json'],
    'ASCGSCG': ['brief_slots.json', 'chrono_slots.json'],
    'SCHOOL':  ['school_slots.json', 'shared_school_slots.json'],
}


def _merge(files):
    m = {}
    for fn in files:
        for c, g in load(fn).items():
            m.setdefault(int(g), c)
    return m


REGS = {k: _merge(v) for k, v in FONTS.items()}


def userdata(path):
    with open(path, 'rb') as f:
        f.seek(0, 2)
        n = f.tell() // 2352
        f.seek(0)
        out = bytearray()
        lba = 0
        while lba < n:
            f.seek(lba * 2352)
            raw = f.read(2352 * 8000)
            if not raw:
                break
            m = len(raw) // 2352
            for i in range(m):
                out += raw[i * 2352 + 16:i * 2352 + 16 + 2048]
            lba += m
    return bytes(out)


def enc(s):
    try:
        return b''.join(struct.pack('>H', REV[c]) for c in s)
    except KeyError:
        return None


def sources():
    """원문 → 기대 역어. 프로젝트의 모든 번역표를 합친다."""
    import kr_s15 as S
    out = {}
    out.update(S.UNIT16)
    out.update(S.KANJI_UNITS)
    out.update(load('katakana_names.json'))
    ku = load('katakana_units.json')
    if isinstance(ku, dict):
        out.update({k: v for k, v in ku.items() if isinstance(v, str)})
    MODS = ('ui16_kr', 'kekka_kr', 'sakusen_kr', 'interm_kr', 'gmdt_medal_kr',
            'museum_kr', 'generals_kr', 'school_kr', 'brief_kr', 'chrono_kr',
            'game_pool_kr', 'menu_kr', 'katakana_kr', 'interm_small_kr')
    SKIP = {'EXTRA_GLYPHS', 'UNMAPPED', 'FORCE_FIX'}
    for m in MODS:
        try:
            M = __import__(m)
        except Exception:
            continue
        for n in dir(M):
            if not n.isupper() or n in SKIP:
                continue
            d = getattr(M, n)
            if not isinstance(d, dict):
                continue
            for k, v in d.items():
                if isinstance(k, str) and isinstance(v, str):
                    out.setdefault(k, v)
    return {k: v for k, v in out.items() if len(k) >= 2}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print('ISO 로딩...', flush=True)
    UO = userdata(TRACK1)
    UP = userdata(PATCHED)
    src = sources()
    print('원문 %d종 대조 (원본 %.0fMB)' % (len(src), len(UO) / 1e6), flush=True)
    tot = Counter()
    stale_sites = []
    per = []
    for jp, kr in sorted(src.items()):
        pat = enc(jp)
        if not pat or len(pat) < 4:
            continue
        want = None
        c = Counter()
        s = 0
        sites = []
        while True:
            j = UO.find(pat, s)
            if j < 0:
                break
            sites.append(j)
            s = j + 2
            if len(sites) > 2000:
                break
        for j in sites:
            b = UP[j:j + len(pat)]
            idx = tuple(struct.unpack_from('>H', b, i)[0] for i in range(0, len(b), 2))
            if b == pat:
                c['①미번역'] += 1
                continue
            hit = None
            for name, m in REGS.items():
                d = ''.join(m.get(v) or charmap.CHARS.get(v, '?') for v in idx)
                if d == kr:
                    hit = name
                    break
            if hit:
                c['②' + hit] += 1
            else:
                c['③잔재'] += 1
                stale_sites.append((j, jp, kr, idx))
        for k, v in c.items():
            tot[k] += v
        if c.get('③잔재'):
            per.append((c['③잔재'], jp, kr, len(sites)))
    print('\n=== 전체 집계 ===')
    for k, v in sorted(tot.items(), key=lambda t: -t[1]):
        print('  %-16s %6d' % (k, v))
    print('\n=== ③잔재 상위 원문 ===')
    for n, jp, kr, tt in sorted(per, reverse=True)[:25]:
        print('  %5d/%-5d %-16s -> %s' % (n, tt, jp, kr))
    print('\n③잔재 총 %d자리 / 원문 %d종' % (len(stale_sites), len(per)))
    json.dump([[j, jp, kr, list(i)] for j, jp, kr, i in stale_sites],
              open(os.path.join(ROOT, 'work', 'stale_sites.json'), 'w'), indent=0)


if __name__ == '__main__':
    main()
