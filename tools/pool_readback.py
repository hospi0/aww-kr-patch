# -*- coding: utf-8 -*-
"""F: 패치본 ISO에서 **대사 풀을 되읽어** 지금 화면에 뜰 문자열을 복원한다 (세션18).

세션17-c 가 공용 슬롯을 재배정한 뒤 폰트 등록부가 흔들렸으므로,
「번역표가 맞나」가 아니라 **「그 폰트로 디코드하면 한글로 보이나」** 를 본다.
집계: 한글 셀 / 가나·한자 잔존 셀 / 미상 인덱스.

사용: python tools/pool_readback.py [풀이름 ...]
"""
import os
import sys
import struct
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap
from isoread import TRACK1, read_range
from scan_files import files
from extract_pool import POOLS, SPLIT, SEP
from gen_audit import FONTS, _merge

# ★원문 디코드는 **그 모듈의 폰트 맵**으로 해야 한다.
#   charmap.CHARS 는 ASC16CG 전용이라 다른 폰트에 쓰면 원문이 통째로 엉뚱해진다
#   (실제로 「性能を武装し」 같은 무의미한 원문이 나왔다).
_FM = json.load(open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'work', 'fontmaps.json'), encoding='utf-8'))


def base_map(font):
    # ⚠️ASC16CG 는 **charmap.CHARS** 가 정본이다. fontmaps['ASC16CG2'] 는 일부 인덱스를
    #   다르게 안다(279 를 `優` 로 읽어 `강설시、` 를 `강설시優` 로 오판했다).
    if font in ('ASC16CG', 'SCHOOL'):
        return dict(charmap.CHARS)
    key = font
    if key in _FM:
        return {int(k): v for k, v in _FM[key].items()}
    return dict(charmap.CHARS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHED = os.path.join(r'F:\hospi\roms\ss roms\aww', os.path.basename(TRACK1))

# 풀 → 그 모듈이 실제로 쓰는 폰트
POOL_FONT = {
    'interm_brief': 'ASCIMCG', 'interm_title': 'ASCIMCG',
    'interm_chrono': 'ASCIMCG', 'interm_doc': 'ASCIMCG',
    'sakusen_msg': 'SAKUCG',
    'kekka_medal': 'ASC16CG', 'kekka_result': 'ASC16CG',
    'school': 'SCHOOL',
}


def get(path, iso):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(iso, 'rb') as f:
                return read_range(f, lba, size)
    raise SystemExit('파일 없음 %s' % path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    want = [a for a in sys.argv[1:] if not a.startswith('-')] or list(POOLS)
    show = '--show' in sys.argv
    REGS = {k: _merge(v) for k, v in FONTS.items()}
    for name in want:
        path, _f, a, b, desc = POOLS[name]
        font = POOL_FONT[name]
        m = REGS[font]
        BASE = base_map(font)
        d = get(path, PATCHED)
        spans = SPLIT.get(name, [(a, b)])
        kr = jp = unk = 0
        bad = []
        for s, e in spans:
            o = s
            cur = []
            while o + 1 < e:
                v = struct.unpack_from('>H', d, o)[0]
                o += 2
                if v == SEP or v == 0:
                    if cur:
                        txt = ''.join(c for c, _ in cur)
                        if any(t == 'jp' for _, t in cur):
                            bad.append((s, txt))
                        cur = []
                    continue
                c = m.get(v)
                if c:
                    kr += 1
                    cur.append((c, 'kr'))
                    continue
                c = BASE.get(v)
                if c is None:
                    unk += 1
                    cur.append(('〈%d〉' % v, 'unk'))
                elif len(c) == 1 and ('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff'):
                    jp += 1
                    cur.append((c, 'jp'))
                else:
                    cur.append((c, 'ascii'))
        print('%-14s %-9s 한글 %5d / ★일본어잔존 %4d / 미상 %4d   레코드 %d개에 잔존'
              % (name, font, kr, jp, unk, len(bad)))
        if show:
            for s, t in bad[:12]:
                print('    %s' % t[:70])


if __name__ == '__main__':
    main()
