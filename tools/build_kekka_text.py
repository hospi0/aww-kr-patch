# -*- coding: utf-8 -*-
"""/KEKKA 훈장·특수능력·수여문 한글화 빌더 — 224레코드 (세션16).

★폰트는 여기서 안 만든다 — KEKKA 는 **전역 폰트 ASC16CG** 를 쓴다.
  글리프는 `build_ui16.py` 가 만든다(ui16_kr.budget_all 이 kekka_kr 음절을 포함한다).
  ⇒ **build_ui16 을 먼저 돌린 뒤** 이 빌더를 돌려야 한다. 순서가 바뀌면 글자가 빈칸으로 뜬다.

레코드는 0xFFFF 로 구분된 고정 길이다. 원문 셀 수를 넘으면 옆 레코드를 먹으므로
남는 칸은 0x0000(공백)으로 패딩한다. 제어코드({FD} 줄바꿈)는 원문과 같은 자리에 둔다.

빌드: python tools/build_kekka_text.py            드라이런
      python tools/build_kekka_text.py --write     F: ISO 기록
      python tools/build_kekka_text.py --resync    구성 바뀐 재기록
"""
import os
import re
import sys
import csv
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kr_rules import squeeze
import ecc
import charmap
import kekka_kr as K
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
# 같은 모듈의 두 풀 — 훈장/수여문 + 결과화면(세션16 전수 스캔에서 발견)
POOLS = [('kekka_medal', 'KR'), ('kekka_result', 'RESULT')]
SLOTS = os.path.join(ROOT, 'work', 'asc16_slots.json')
CTRL = re.compile(r'\{([0-9A-F]{2})\}')

# 16×16 폰트엔 전각 기호만 있다(다른 빌더와 같은 제약).
PUNCT = {'.': '。', ',': '、', '?': '？', '!': '！', '-': 'ー', '·': '・',
         '(': '（', ')': '）', '/': '／', '~': 'ー', '%': '％', ':': '：'}


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def tables():
    rev = {}
    for k, v in charmap.CHARS.items():
        rev.setdefault(v, k)
    return rev


def encode_seg(s, slot, rev):
    s = squeeze(s)                       # 문장부호 뒤 공백 1칸 삭제(kr_rules)
    out = bytearray()
    if True:
        for c in s:
            if '가' <= c <= '힣':
                g = slot.get(c)
                if g is None:
                    raise SystemExit('한글 슬롯 없음 %r in %r — build_ui16 먼저 돌릴 것' % (c, s))
            else:
                # ⚠️`or` 로 쓰면 안 된다 — 공백은 글리프 **0번**이라 falsy 다(1차 실행에서 터짐).
                g = rev.get(c)
                if g is None:
                    g = rev.get(PUNCT.get(c))
                if g is None and 0x21 <= ord(c) <= 0x7E:
                    g = rev.get(chr(ord(c) + 0xFEE0))
                if g is None:
                    raise SystemExit('글리프 없음 %r in %r' % (c, s))
            out += struct.pack('>H', g)
    return bytes(out)


def encode(jp, kr, slot, rev):
    """★제어코드 사이 세그먼트를 **원문과 같은 셀 수로 패딩**해서 인코딩한다.

    안 지키면 뒤따르는 제어코드가 앞으로 밀린다 — 세션15-g 사관학교 대사창이
    이것 하나로 전멸했다(폰트·인코딩은 완벽했는데도).
    """
    jsegs, jcodes = CTRL.split(jp)[0::2], CTRL.findall(jp)
    ksegs, kcodes = CTRL.split(kr)[0::2], CTRL.findall(kr)
    if jcodes != kcodes:
        raise SystemExit('제어코드 불일치 %r → %r' % (jp, kr))
    out = bytearray()
    for i, kseg in enumerate(ksegs):
        if len(kseg) > len(jsegs[i]):
            raise SystemExit('세그%d %d칸 > 원문 %d칸: %r' % (i, len(kseg), len(jsegs[i]), kseg))
        out += encode_seg(kseg, slot, rev).ljust(len(jsegs[i]) * 2, b'\x00')
        if i < len(kcodes):
            out += struct.pack('>H', 0xFF00 | int(kcodes[i], 16))
    return bytes(out)


def plan(d, slot, rev):
    plans = []
    for pool, attr in POOLS:
        plans += plan_pool(d, slot, rev, pool, getattr(K, attr))
    return plans


def plan_pool(d, slot, rev, pool, table):
    tsv = os.path.join(ROOT, 'work', 'scenario', pool + '.tsv')
    rows = list(csv.DictReader(open(tsv, encoding='utf-8'), delimiter='\t'))
    plans = []
    for r in rows:
        idx = int(r['idx'])
        kr = table.get(idx)
        if kr is None:
            continue
        off, cells = int(r['offset'], 16), int(r['cells'])
        nb = encode(r['jp'], kr, slot, rev)
        if len(nb) > cells * 2:
            raise SystemExit('%s rec%d %d칸 > 원문 %d칸: %r'
                             % (pool, idx, len(nb) // 2, cells, kr))
        plans.append((off, d[off:off + cells * 2], nb.ljust(cells * 2, b'\x00'),
                      '%s%d' % (pool.split('_')[1][:3], idx), r['jp'], kr))
    return plans


def gate(plans):
    """★제어코드는 원문과 **한 셀도 어긋나면 안 된다**(세션15-g 대사창 전멸의 원인)."""
    bad = 0
    for off, old, new, tag, jp, kr in plans:
        for i in range(0, len(new), 2):
            a = (old[i] << 8) | old[i + 1]
            b = (new[i] << 8) | new[i + 1]
            if (a >= 0xFF00) != (b >= 0xFF00) or (a >= 0xFF00 and a != b):
                if bad < 10:
                    print('  ❌%s @0x%06x 셀%d 원본 %04X → %04X' % (tag, off, i // 2, a, b))
                bad += 1
    if bad:
        raise SystemExit('★제어코드 정합 실패 %d곳 — 기록 중단' % bad)
    print('관문 통과 — 제어코드 위치·값이 원본과 일치.')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or resync

    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'KEKKA')
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
    slot = json.load(open(SLOTS, encoding='utf-8'))
    rev = tables()
    pl = plan(d, slot, rev)
    gate(pl)
    print('/KEKKA lba=%d size=%d — %d레코드 치환' % (lba, size, len(pl)))
    for off, old, new, tag, jp, kr in pl[:5]:
        print('   0x%06x %-8s %s → %s' % (off, tag, jp[:20], kr[:20]))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for off, old, new, tag, jp, kr in pl:
            for k in range(len(new)):
                lo = off + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                if not resync and w.read(1) != old[k:k + 1]:
                    raise SystemExit('%s @0x%x 대조 실패 — 이미 패치됨? (--resync)' % (tag, off))
                w.seek(pos)
                w.write(new[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)

    # 독립 되읽기 + 일본어 잔존 검사
    with open(dst, 'rb') as r:
        cur = read_file(r, lba, size)
    bad = sum(1 for off, old, new, tag, jp, kr in pl if cur[off:off + len(new)] != new)
    inv = {g: c for c, g in slot.items()}
    left = 0
    for off, old, new, tag, jp, kr in pl:
        for i in range(0, len(new), 2):
            v = (new[i] << 8) | new[i + 1]
            if v == 0 or v >= 0xFF00 or v in inv:
                continue
            ch = charmap.CHARS.get(v)
            if ch and (('\u3040' <= ch <= '\u30ff' and ch != 'ー') or '\u4e00' <= ch <= '\u9fff'):
                left += 1
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 되읽기 일치, 일본어 잔존 %d칸, EDC/ECC 유효.' % left)


if __name__ == '__main__':
    main()
