# -*- coding: utf-8 -*-
"""사관학교(/SCHOOL) 한글화 통합 빌더 — 폰트·본문·이름·팔레트 (세션15-g).

한 번에 넷을 기록한다. **슬롯을 한 곳에서 배정**하는 게 요점 —
조각내면 배정이 두 벌 되어 이미 기록한 텍스트가 어긋난다(세션15-c 실사고 `정예병`→`정네병`).

  ① 폰트   0x1C574 + idx×128 에 한글 글리프 **제자리 기록**(크기·LBA 불변)
     ★확장 불가: 0x1C574 + 917×128 = 0x38FF4 이고 본문이 0x39000에서 시작한다.
       ⇒ **회수 슬롯만이 예산원**(school_reclaim). 실측 회수 406칸 / 수요 361.
  ② 본문   0x39000~0x3BC00, 56레코드. 제어코드({FC}{FD}{FE}{FB}{F9}{F8})는 그대로 두고
     텍스트 줄만 같은 순서로 교체. 남는 칸은 0x0000(공백) 패딩.
  ③ 이름   0x07AF5C + n×0x62, 35레코드. +0x0A 16×16 한글 / +0x44 소형 8×8 로마자.
     ⚠️소형은 세션5가 가나 슬롯을 한글로 덮은 뒤 **계속 깨져 있었다**(ヘレナ→「미결무」).
  ④ 팔레트 0x3EF8~0x4048 이름입력 가나 168칸을 공백(0x0000)으로 — 사용자 결정.
     이걸 비워야 가나 글리프가 회수 대상이 된다.

빌드: python tools/build_school_text.py            드라이런
      python tools/build_school_text.py --write     F: ISO 기록
      python tools/build_school_text.py --resync    구성 바뀐 재기록
"""
import os
import re
import sys
import csv
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import charmap
import school_kr as K
import school_reclaim as R
from school_charmap import SCHOOL_CHARS
from hangul import render_kr
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec
from build_school_names import NAMES, REC_BASE, STRIDE, NREC, OFF16, OFFSMALL, W16, WSMALL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
FONT_OFF, GLYPH, NGLYPH = 0x1C574, 128, 917
TEXT_LO, TEXT_HI = 0x39000, 0x3BC00
PALETTE_LO, PALETTE_HI = 0x003EF8, 0x004048
SLOTS = os.path.join(ROOT, 'work', 'school_slots.json')
RAMP = 'dark'


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def tables():
    t = dict(charmap.CHARS)
    t.update(SCHOOL_CHARS)
    rev = {}
    for k, v in t.items():
        rev.setdefault(v, k)
    return t, rev


def small_map():
    rows = list(csv.reader(open(os.path.join(ROOT, 'work', 'smalltext', 'smalltext.tsv'),
                                encoding='utf-8'), delimiter='\t'))[1:]
    m = {}
    for r in rows:
        jp, hx = r[4], r[5]
        try:
            b = bytes.fromhex(hx)
        except Exception:
            continue
        if len(jp) == len(b):
            for c, x in zip(jp, b):
                m.setdefault(c, x)
    return m


def build_slots():
    """본문 + 이름의 한글 음절 → 회수 슬롯. work/school_slots.json 에 **고정**."""
    from collections import Counter
    freq = Counter()
    for kl in K.LINES.values():
        for line in kl:
            for c in line:
                if '가' <= c <= '힣':
                    freq[c] += 1
    for kr, _ in NAMES.values():
        for c in kr:
            if '가' <= c <= '힣':
                freq[c] += 1
    order = [c for c, _ in sorted(freq.items(), key=lambda t: (-t[1], t[0]))]
    free = R.load()
    slot = json.load(open(SLOTS, encoding='utf-8')) if os.path.exists(SLOTS) else {}
    # ★917 이상은 파일에 자리가 없다 — 옛 임시 배정을 버린다
    slot = {c: g for c, g in slot.items() if g < NGLYPH}
    taken = set(slot.values())
    # ★세션17: 부관이름 공용 슬롯(ASC16CG·SCHOOL 동일 인덱스)은 **배정 금지**.
    import shared_school_slots
    taken |= set(shared_school_slots.build(verbose=False).values())
    pool = [g for g in free if g not in taken]
    for c in order:
        if c in slot:
            continue
        if not pool:
            raise SystemExit('★SCHOOL 슬롯 고갈 — 수요 %d / 회수 %d' % (len(order), len(free)))
        slot[c] = pool.pop(0)
    json.dump(slot, open(SLOTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('슬롯 %d음절 → 회수 %d칸 중 사용 (여유 %d)' % (len(slot), len(free), len(free) - len(slot)))
    return slot


# 16×16 폰트엔 **전각 기호만** 있다(다른 빌더와 같은 제약).
# 문장부호성 가나 — 일본어 잔존 집계에서 제외한다(번역문이 쓴다).
_PUNCT_KANA = {'ー', '・', '゛', '゜', 'ゝ', 'ゞ', 'ヽ', 'ヾ'}

PUNCT = {'.': '。', ',': '、', '?': '？', '!': '！', '-': 'ー', '·': '・',
         '(': '（', ')': '）', '/': '／', '~': 'ー'}


def enc16(s, slot, rev):
    out = bytearray()
    for c in s:
        if '가' <= c <= '힣':
            g = slot.get(c)
            if g is None:
                raise SystemExit('한글 슬롯 없음 %r in %r' % (c, s))
        else:
            g = rev.get(c)
            if g is None:
                g = rev.get(PUNCT.get(c))
            if g is None and 0x21 <= ord(c) <= 0x7E:
                g = rev.get(chr(ord(c) + 0xFEE0))
            if g is None:
                raise SystemExit('글리프 없음 %r in %r' % (c, s))
        out += struct.pack('>H', g)
    return bytes(out)


def plan_text(d, slot, rev, t):
    """본문 56레코드 — (offset, old, new)."""
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'work', 'school', 'school.tsv'),
                                    encoding='utf-8'), delimiter='\t'))
    plans = []
    for r in rows:
        idx = int(r['idx'])
        off = int(r['offset'], 16)
        cells = int(r['words'])
        segs = [p for p in re.split(r'(\{F[0-9A-F]\})', r['jp']) if p]
        kl = K.LINES[idx]
        li = 0
        nb = bytearray()
        for p in segs:
            if p.startswith('{'):
                # ★tsv 의 {FC} 는 **하위 바이트 표기**다 — 실제 셀 값은 0xFFFC.
                #   0x00FC 로 쓰면 제어코드가 아니라 글리프 252(形)가 된다(1차 빌드 사고).
                nb += struct.pack('>H', 0xFF00 | int(p[1:-1], 16))
            else:
                # ★★각 세그먼트를 **원본과 정확히 같은 셀 수**로 채운다.
                #   안 지키면 뒤따르는 제어코드가 전부 앞으로 밀려 화면이 무너진다
                #   (세션15-g 실사고: 277곳 밀림 → 대사창 전멸).
                if len(kl[li]) > len(p):
                    raise SystemExit('rec %d seg%d 한글 %d칸 > 원본 %d칸: %r'
                                     % (idx, li, len(kl[li]), len(p), kl[li]))
                nb += enc16(kl[li], slot, rev).ljust(len(p) * 2, b'\x00')
                li += 1
        if len(nb) > cells * 2:
            raise SystemExit('rec %d %d칸 > %d' % (idx, len(nb) // 2, cells))
        nb = bytes(nb).ljust(cells * 2, b'\x00')
        plans.append((off, d[off:off + cells * 2], nb, 'rec%d' % idx))
    return plans


def gate_ctrl(d, plans):
    """★관문 — 제어코드(0xFFxx)가 원본과 **한 셀도 어긋나지 않아야** 한다.

    세션15-g 1차 빌드가 여기서 무너졌다: 한글 줄이 원문보다 짧은데 패딩을 안 해
    277곳이 앞으로 밀렸고, 폰트·인코딩이 완벽했는데도 대사창이 전멸했다.
    되읽기 검증은 「내가 계획한 대로 써졌나」만 보므로 이 사고를 못 잡는다.
    """
    bad = 0
    for off, old, new, tag in plans:
        for i in range(0, len(new), 2):
            a = (old[i] << 8) | old[i + 1]
            b = (new[i] << 8) | new[i + 1]
            if (a >= 0xFF00) != (b >= 0xFF00) or (a >= 0xFF00 and a != b):
                if bad < 10:
                    print('  ❌%s @0x%06x 셀%d  원본 %04X → %04X' % (tag, off, i // 2, a, b))
                bad += 1
    if bad:
        raise SystemExit('★제어코드 정합 실패 %d곳 — 기록 중단' % bad)
    print('관문 통과 — 제어코드 위치 원본과 완전 일치.')


def plan_names(d, slot, rev, t, sm):
    # 🐞🐞세션17: 이름 16×16 필드는 **본문 슬롯(slot)으로 인코딩하면 안 된다.**
    #   이 표는 사본이 하나인데 **전투화면이 ASC16CG 로 같이 읽는다** ⇒ 「로절리」가
    #   전투화면에 **「줄詰입」**으로 떴다(사용자 스샷 2026-07-26).
    #   ⇒ 두 폰트에서 동시에 자유로운 **공용 슬롯**으로 인코딩한다.
    #   ★여기가 실제 기록 지점이다 — build_school_names 만 고치면 아무 효과가 없다.
    import shared_school_slots
    slot = shared_school_slots.build(verbose=False)
    plans = []
    for n in range(NREC):
        o = REC_BASE + n * STRIDE
        jp = ''
        for j in range(W16 + 2):
            v = struct.unpack_from('>H', d, o + OFF16 + j * 2)[0]
            if v in (0, 0xFFFF):
                break
            jp += t.get(v, '?')
        if jp not in NAMES:
            raise SystemExit('이름 rec %d 원문 불일치 %r' % (n, jp))
        kr, latin = NAMES[jp]
        nb = enc16(kr, slot, rev).ljust(W16 * 2, b'\x00')
        plans.append((o + OFF16, d[o + OFF16:o + OFF16 + W16 * 2], nb, jp + '16'))
        sb = bytes(sm[c] if c in sm else ord(c) for c in latin).ljust(WSMALL, b'\x00')
        plans.append((o + OFFSMALL, d[o + OFFSMALL:o + OFFSMALL + WSMALL], sb, jp + '8'))
    return plans


def plan_palette(d, t):
    """이름입력 가나 팔레트 → 공백(0x0000)."""
    nb = bytearray(d[PALETTE_LO:PALETTE_HI])
    n = 0
    for i in range(0, len(nb), 2):
        v = (nb[i] << 8) | nb[i + 1]
        ch = t.get(v)
        if ch and (('\u3040' <= ch <= '\u309f') or ('\u30a0' <= ch <= '\u30ff')) and ch != 'ー':
            nb[i] = 0
            nb[i + 1] = 0
            n += 1
    old = d[PALETTE_LO:PALETTE_HI]
    return ([(PALETTE_LO, old, bytes(nb), '팔레트')] if old != bytes(nb) else []), n


def build_font(d, slot):
    font = bytearray(d[FONT_OFF:FONT_OFF + NGLYPH * GLYPH])
    for c, g in slot.items():
        font[g * GLYPH:(g + 1) * GLYPH] = render_kr(c, ramp=RAMP)
    # ★세션17: 동료(부관) 이름 16×16 필드는 **전투화면이 ASC16CG로 같이 읽는다.**
    #   두 폰트의 같은 인덱스에 같은 글리프를 그린다(shared_school_slots).
    #   ⚠️`slot`(본문용 school_slots)에 병합하지 않는다 — 본문 인코딩이 어긋난다.
    import shared_school_slots
    for c, g in shared_school_slots.build(verbose=False).items():
        if g < NGLYPH:
            font[g * GLYPH:(g + 1) * GLYPH] = render_kr(c, ramp=RAMP)
    return bytes(font)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync

    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'SCHOOL')
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
    t, rev = tables()
    slot = build_slots()
    sm = small_map()

    tp = plan_text(d, slot, rev, t)
    gate_ctrl(d, tp)
    npl = plan_names(d, slot, rev, t, sm)
    pp, nkana = plan_palette(d, t)
    font = build_font(d, slot)
    print('SCHOOL lba=%d  본문 %d레코드 / 이름 %d곳 / 팔레트 가나 %d칸 공백화'
          % (lba, len(tp), len(npl), nkana))
    print('폰트 %d글리프 제자리 기록 (0x%06X~, 크기 불변)' % (NGLYPH, FONT_OFF))
    for o, a, b, tag in (tp[:3] + npl[:3]):
        print('   0x%06x  %s' % (o, tag))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    plans = tp + npl + pp + [(FONT_OFF, d[FONT_OFF:FONT_OFF + NGLYPH * GLYPH], font, '폰트')]
    touched = set()
    with open(dst, 'r+b') as w:
        for off, old, new, tag in plans:
            for k in range(len(new)):
                lo = off + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                if not resync and w.read(1) != old[k:k + 1]:
                    raise SystemExit('%s @0x%x 대조 실패 — 이미 패치됨?' % (tag, off))
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

    # 독립 되읽기
    bad = 0
    with open(dst, 'rb') as r:
        cur = read_file(r, lba, size)
    for off, old, new, tag in plans:
        if cur[off:off + len(new)] != new:
            bad += 1
            print('  ❌%s @0x%06x 되읽기 불일치' % (tag, off))
    inv = {g: c for c, g in slot.items()}
    jp_left = 0
    for off, old, new, tag in tp:
        for i in range(0, len(new), 2):
            v = (new[i] << 8) | new[i + 1]
            if v in (0,) or v >= 0xFF00 or v in inv:
                continue
            ch = t.get(v)
            # ⚠️문장부호성 가나는 번역문이 **일부러 쓰는** 글자다 — 잔존으로 세면 안 된다.
            #   `・`(U+30FB)가 가나 범위(3040~30FF)에 들어 「잔존 7」로 오탐됐다(세션17).
            if ch and ch not in _PUNCT_KANA and (
                    '぀' <= ch <= 'ヿ' or '一' <= ch <= '鿿'):
                jp_left += 1
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 되읽기 일치, 본문 일본어 잔존 %d, EDC/ECC 유효.' % jp_left)


if __name__ == '__main__':
    main()
