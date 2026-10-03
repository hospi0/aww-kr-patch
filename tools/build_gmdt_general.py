# -*- coding: utf-8 -*-
"""장군 화면 특수능력 설명문 기록 — /GMDT 0x0169E4~0x0171E8 (세션18).

이 구역은 **어느 빌더도 담당한 적이 없어** 통째로 원문 일본어로 남아 있었다.
세션17-c 가 슬롯을 대량 회수한 뒤 그 일본어가 회수 슬롯을 참조해
`텍軍총포되카殊움力범프브는징명。` 처럼 떴다(실기 스샷).

★치환은 **원본 바이트 앵커** — 원본 TRACK1 에서 원문 셀열이 정확히 일치하는 자리만 친다.
★length-locked: 역어 ≤ 원문 칸수, 남는 칸은 널 패딩.
★`{FD}`(0xFFFD)는 원문 자리 그대로 유지한다(줄바꿈 제어).
★--resync 는 이 자리에 무엇이 들어 있든 덮는다 ([[feedback_resync_already_guard]]).
⚠️새 음절이 생기면 ASC16CG 폰트에 없으므로 **build_ui16 을 먼저** 돌려야 한다.

빌드: python tools/build_gmdt_general.py            드라이런
      python tools/build_gmdt_general.py --write     F: ISO 기록
      python tools/build_gmdt_general.py --resync    구성 바뀐 재기록
      python tools/build_gmdt_general.py --revert    원상복구
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kr_rules import squeeze
import ecc
import charmap
import gmdt_general_kr as G
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
MOD, LO, HI = '/GMDT', 0x0169E4, 0x0171E8
FD = 0xFFFD


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def slots():
    d = {}
    for fn in ('asc16_slots.json', 'shared_unit_slots.json'):
        p = os.path.join(ROOT, 'work', fn)
        if os.path.exists(p):
            for c, g in json.load(open(p, encoding='utf-8')).items():
                d.setdefault(c, int(g))
    return d


def enc(s, slot, rev):
    s = squeeze(s)                       # 문장부호 뒤 공백 1칸 삭제(kr_rules)
    """`{FD}` 토큰은 0xFFFD 한 칸으로 나간다."""
    out = bytearray()
    i = 0
    while i < len(s):
        if s.startswith('{FD}', i):
            out += struct.pack('>H', FD)
            i += 4
            continue
        c = s[i]
        i += 1
        if '가' <= c <= '힣':
            g = slot.get(c)
            if g is None:
                raise KeyError('한글 슬롯 없음 %r (build_ui16 먼저)' % c)
        else:
            g = rev.get(c)
            if g is None:
                raise KeyError('인코딩 불가 %r in %r' % (c, s))
        out += struct.pack('>H', g)
    return bytes(out)


def build_plans():
    m = {q: (l, s) for q, l, s in files(skip_media=False)}
    rev = {}
    for k, v in charmap.CHARS.items():
        rev.setdefault(v, k)
    rev.setdefault('　', 0)
    slot = slots()
    tbl = G.table()
    lba, size = m[MOD]
    with open(TRACK1, 'rb') as f:
        orig = read_file(f, lba, size)
    plans, taken, missing = [], set(), []
    # 긴 원문부터 — 짧은 문구가 긴 문장 안에서 먼저 잡히는 것을 막는다
    for jp in sorted(tbl, key=len, reverse=True):
        kr = tbl[jp]
        try:
            pat = enc(jp, slot, rev)
            nb = enc(kr, slot, rev)
        except KeyError as e:
            missing.append((jp, str(e)))
            continue
        if len(nb) > len(pat):
            missing.append((jp, '칸수 초과 %d>%d' % (len(nb) // 2, len(pat) // 2)))
            continue
        nb = nb.ljust(len(pat), b'\x00')
        i = orig.find(pat, LO)
        while 0 <= i < HI:
            if not (set(range(i, i + len(pat))) & taken):
                plans.append((i, orig[i:i + len(pat)], nb, jp, kr))
                taken.update(range(i, i + len(pat)))
            i = orig.find(pat, i + 2)
    plans.sort()
    return lba, size, orig, plans, missing


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    lba, size, orig, plans, missing = build_plans()
    print('%s 0x%05X~0x%05X — 치환 %d곳 / 번역표 %d종'
          % (MOD, LO, HI, len(plans), len(G.table())))
    for o, a, b, jp, kr in plans[:8]:
        print('   0x%06X %-24s → %s' % (o, jp, kr))
    if len(plans) > 8:
        print('   ... 외 %d곳' % (len(plans) - 8))
    if missing:
        print('⚠️미적용 %d종: %s' % (len(missing), missing[:4]))
    # 남은 일본어 셀 집계 (계획 적용 후 기준)
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    with open(dst, 'r+b') as f:
        buf = bytearray(read_file(f, lba, size))
        for o, a, b, jp, kr in plans:
            src, dstb = (b, a) if revert else (a, b)
            if not resync and bytes(buf[o:o + len(a)]) != src:
                raise SystemExit('★0x%06X 대조 실패 — 중단 (%s)' % (o, jp))
            buf[o:o + len(a)] = dstb
        secs = sorted({(o + k) // USER for o, a, b, _, _ in plans for k in range(len(a))})
        for s in secs:
            f.seek((lba + s) * RAW)
            raw = bytearray(f.read(RAW))
            raw[HDR:HDR + USER] = buf[s * USER:(s + 1) * USER]
            f.seek((lba + s) * RAW)
            f.write(ecc.fix_sector(raw))
    print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(secs))
    bad = 0
    with open(dst, 'rb') as f:
        back = read_file(f, lba, size)
        for o, a, b, _, _ in plans:
            if back[o:o + len(a)] != (a if revert else b):
                bad += 1
        # 독립 되읽기 — 이 구역에 일본어 셀이 몇 개 남았나
        jpn = 0
        for i in range(LO, HI, 2):
            v = struct.unpack_from('>H', back, i)[0]
            c = charmap.CHARS.get(v)
            if c and len(c) == 1 and ('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff'):
                jpn += 1
    print('독립검증 %s — 구역 내 일본어 셀 잔존 %d'
          % ('통과' if bad == 0 else '❌실패 %d곳' % bad, jpn))


if __name__ == '__main__':
    main()
