# -*- coding: utf-8 -*-
"""/INTERM 시나리오 분기·연표·사료 한글화 빌더 — 세션16.

  ① 폰트   /ASCIMCG (697글리프 × 128B) 회수 슬롯에 한글 **제자리 기록**(크기·LBA 불변)
  ② 본문   0x06AD70~0x06EE60 402레코드 — 1:1(KR) + 문단 재줄바꿈(G)
  ③ 제목   0x06EE60~0x06F386 77 — kr_s15.TITLES 재사용(같은 시나리오가 화면마다 달리 불리면 안 된다)
  ④ 연표·사료 0x06F386~0x06F790

★ASCIMCG 는 /INTERM 전용이라 가나·한자를 **전부** 회수한다
  ([[feedback_aww_full_kr_budget]]). `ー・゛゜…` 문장부호성 가나와 `▶`(줄바꿈 표시자)·
  라틴·숫자·기호는 남긴다.
★슬롯 배정은 `work/ascimcg_slots.json` 에 **고정**한다 — 재정렬하면 이미 기록한 텍스트가
  통째로 어긋난다(세션15-c 실사고 「정예병」→「정네병」).

빌드: python tools/build_interm_text.py            드라이런
      python tools/build_interm_text.py --write     F: ISO 기록(폰트+텍스트)
      python tools/build_interm_text.py --resync    구성 바뀐 재기록
"""
import os
import sys
import csv
import json
import struct
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kr_rules import squeeze
import ecc
import interm_kr as K
import interm_small_kr as T
from hangul import render_kr
from scenario_wrap import wrap
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
SLOTS = os.path.join(ROOT, 'work', 'ascimcg_slots.json')
GLYPH, NGLYPH = 128, 697
PUNCT_KANA = {'ー', '・', '゛', '゜', 'ヽ', 'ヾ', 'ゝ', 'ゞ'}
PUNCT = {'.': '。', ',': '、', '?': '？', '!': '！', '-': 'ー', '·': '・',
         '(': '（', ')': '）', '%': '％', ':': '：'}

# 풀 → (tsv 이름, 1:1 표, 문단표)
POOLS = [('interm_brief', K.KR, K.G),
         ('interm_title', T.TITLE, {}),
         ('interm_chrono', T.CHRONO, {}),
         ('interm_doc', T.DOC, {})]


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def font_map():
    fm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['ASCIMCG']
    cm = {int(k): v for k, v in fm.items()}
    rev = {}
    for k, v in cm.items():
        rev.setdefault(v, k)
    return cm, rev


def free_full(cm):
    """가나·한자 전부 회수(문장부호성 가나 제외)."""
    out = []
    for i, ch in cm.items():
        if not ch or len(ch) != 1 or ch in PUNCT_KANA or i >= NGLYPH:
            continue
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF:
            out.append(i)
    return sorted(out)


def rows_of(pool):
    return list(csv.DictReader(open(os.path.join(ROOT, 'work', 'scenario', pool + '.tsv'),
                                    encoding='utf-8'), delimiter='\t'))


def expand(pool, kr1, g, rows):
    """1:1 + 문단 → {idx: 한글줄}."""
    out = dict(kr1)
    for start, (cnt, text) in g.items():
        widths = [int(rows[start + k]['cells']) for k in range(cnt)]
        lines = wrap(squeeze(text), widths)   # ★접기 전에 공백 정리
        if lines is None:
            raise SystemExit('%s rec%d 문단 줄바꿈 실패: %r' % (pool, start, text))
        for k, ln in enumerate(lines):
            out[start + k] = ln
    return out


def build_slots(texts, cm):
    freq = Counter()
    for s in texts:
        for c in s:
            if '가' <= c <= '힣':
                freq[c] += 1
    order = [c for c, _ in sorted(freq.items(), key=lambda t: (-t[1], t[0]))]
    free = free_full(cm)
    slot = json.load(open(SLOTS, encoding='utf-8')) if os.path.exists(SLOTS) else {}
    taken = set(slot.values())
    pool = [g for g in free if g not in taken]
    for c in order:
        if c in slot:
            continue
        if not pool:
            raise SystemExit('★ASCIMCG 슬롯 고갈 — 수요 %d / 회수 %d' % (len(order), len(free)))
        slot[c] = pool.pop(0)
    json.dump(slot, open(SLOTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('ASCIMCG 한글 %d음절 → 회수 %d칸 중 사용 (여유 %d)'
          % (len(slot), len(free), len(free) - len(slot)))
    return slot


def enc(s, slot, rev):
    s = squeeze(s)                       # 문장부호 뒤 공백 1칸 삭제(kr_rules)
    out = bytearray()
    for c in s:
        if '가' <= c <= '힣':
            g = slot.get(c)
            if g is None:
                raise SystemExit('ASCIMCG 슬롯 없음 %r in %r' % (c, s))
        else:
            g = rev.get(c)                      # ⚠️`or` 금지(글리프 0 = falsy)
            if g is None:
                g = rev.get(PUNCT.get(c))
            if g is None and 0x21 <= ord(c) <= 0x7E:
                g = rev.get(chr(ord(c) + 0xFEE0))
            if g is None:
                raise SystemExit('ASCIMCG 글리프 없음 %r in %r' % (c, s))
        out += struct.pack('>H', g)
    return bytes(out)


def plan(d, slot, rev):
    plans = []
    for pool, kr1, g in POOLS:
        rows = rows_of(pool)
        table = expand(pool, kr1, g, rows)
        for r in rows:
            idx = int(r['idx'])
            kr = table.get(idx)
            if kr is None:
                continue
            off, cells = int(r['offset'], 16), int(r['cells'])
            nb = enc(kr, slot, rev)
            if len(nb) > cells * 2:
                raise SystemExit('%s rec%d %d칸 > %d칸: %r' % (pool, idx, len(nb) // 2, cells, kr))
            plans.append((off, d[off:off + cells * 2], nb.ljust(cells * 2, b'\x00'),
                          '%s%d' % (pool[7:10], idx)))
    return plans


def gate(plans):
    """★종료자(0xFFFF)를 덮으면 레코드가 합쳐진다 — 기록 전에 막는다."""
    bad = 0
    for off, old, new, tag in plans:
        for i in range(0, len(old), 2):
            if (old[i] << 8 | old[i + 1]) == 0xFFFF:
                bad += 1
                if bad < 6:
                    print('  ❌%s @0x%06x 셀%d 에 종료자' % (tag, off, i // 2))
    if bad:
        raise SystemExit('★종료자 침범 %d곳 — 기록 중단' % bad)
    print('관문 통과 — 계획 영역에 종료자 없음.')


def font_bytes(orig, slot):
    buf = bytearray(orig)
    for c, g in slot.items():
        buf[g * GLYPH:(g + 1) * GLYPH] = render_kr(c, ramp='dark')
    return bytes(buf)


def write_region(w, lba, off, old, new, resync, tag, touched):
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


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or resync

    cm, rev = font_map()
    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'INTERM')
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
        fhits, _, _, _ = find_dirrec(f, 'ASCIMCG')
        _, flba, fsize, _ = fhits[0]
        fdat = read_file(f, flba, fsize)
    if fsize // GLYPH != NGLYPH:
        raise SystemExit('ASCIMCG 글리프 수 %d (기대 %d)' % (fsize // GLYPH, NGLYPH))

    texts = []
    for pool, kr1, g in POOLS:
        texts += list(expand(pool, kr1, g, rows_of(pool)).values())
    slot = build_slots(texts, cm)
    pl = plan(d, slot, rev)
    gate(pl)
    print('/INTERM lba=%d size=%d — %d레코드 / ASCIMCG lba=%d %d글리프'
          % (lba, size, len(pl), flba, NGLYPH))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    newfont = font_bytes(fdat, slot)
    touched_f, touched_t = set(), set()
    with open(dst, 'r+b') as w:
        write_region(w, flba, 0, fdat, newfont, True, '폰트', touched_f)   # 폰트는 항상 덮어쓴다
        for off, old, new, tag in pl:
            write_region(w, lba, off, old, new, resync, tag, touched_t)
        print('쓴 섹터 폰트 %d + 텍스트 %d, EDC/ECC 재계산...' % (len(touched_f), len(touched_t)))
        for sec in sorted(touched_f | touched_t):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)

    with open(dst, 'rb') as r:
        cur = read_file(r, lba, size)
        curf = read_file(r, flba, fsize)
    bad = sum(1 for off, old, new, tag in pl if cur[off:off + len(new)] != new)
    if curf != newfont:
        bad += 1
        print('  ❌폰트 되읽기 불일치')
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 폰트·텍스트 되읽기 일치, EDC/ECC 유효.')


if __name__ == '__main__':
    main()
