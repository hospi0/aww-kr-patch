# -*- coding: utf-8 -*-
"""/SAKUSEN 작전·생산 화면 + 브리핑 한글화 빌더 — 세션16.

한 번에 넷을 기록한다. **슬롯을 한 곳에서 배정**하는 게 요점(세션15-g 사관학교와 같은 이유):

  ① 폰트   /SAKUCG 회수 슬롯에 한글 글리프 제자리 기록 (sakucg_kr, 크기·LBA 불변)
  ② 본문   0x049494~0x04DFD4  699레코드 — 1:1(KR) + 문단 재줄바꿈(G)
  ③ 타입표 rec106(0x049ADC, 485칸) = 병기타입 50×7칸 + 이동타입 15×9칸 **고정폭 묶음표**
  ④ 진영표 0x04DFE6 은 **build_names16 소관**(편성명 3벌 사본) — 여기선 손대지 않는다

⚠️SAKUCG 는 /SAKUSEN 전용 폰트라 가나·한자를 전부 회수한다. 그래서 **이 모듈의 일본어
  텍스트를 하나라도 빠뜨리면 그 자리가 한글 글리프로 깨져 보인다.** ③④가 그 이유로 발견됐다.

빌드: python tools/build_sakusen_text.py            드라이런
      python tools/build_sakusen_text.py --write     F: ISO 기록(폰트+텍스트)
      python tools/build_sakusen_text.py --resync    구성 바뀐 재기록
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
import sakucg_kr as F
import sakusen_kr as K
import kr_s15 as S
from scenario_wrap import wrap
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
TSV = os.path.join(ROOT, 'work', 'scenario', 'sakusen_msg.tsv')
CTRL = re.compile(r'\{([0-9A-F]{2})\}')

# rec106 묶음표 배치(실측)
T106_WEAPON_N, T106_WEAPON_W = 50, 7
T106_MOVE_N, T106_MOVE_W = 15, 9

PUNCT = {'.': '。', ',': '、', '?': '？', '!': '！', '-': 'ー', '·': '・',
         '(': '（', ')': '）', '/': '／', '~': 'ー', '%': '％', ':': '：'}

# rec106 마지막 9칸은 타입이 아니라 메시지다(원문 `VPが足りません。`).
T106_TAIL_KR = 'VP가 부족합니다'
# 원문에 없어 kr_s15 에 안 들어 있는 항목
EXTRA_TYPES = {'トーチカ／要塞': '토치카／요새', 'ダミー': '더미'}


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def rev_map():
    fm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    rev = {}
    for k, v in fm.items():
        rev.setdefault(v, int(k))
    return rev


def enc(s, slot, rev):
    s = squeeze(s)                       # 문장부호 뒤 공백 1칸 삭제(kr_rules)
    out = bytearray()
    for c in s:
        if '가' <= c <= '힣':
            g = slot.get(c)
            if g is None:
                raise SystemExit('SAKUCG 슬롯 없음 %r in %r' % (c, s))
        else:
            # ⚠️`or` 금지 — 공백 글리프가 0번이면 falsy 다.
            g = rev.get(c)
            if g is None:
                g = rev.get(PUNCT.get(c))
            if g is None and 0x21 <= ord(c) <= 0x7E:
                g = rev.get(chr(ord(c) + 0xFEE0))
            if g is None:
                raise SystemExit('SAKUCG 글리프 없음 %r in %r' % (c, s))
        out += struct.pack('>H', g)
    return bytes(out)


def text_plans(d, slot, rev, rows):
    """1:1 레코드 + 문단(G) → (offset, old, new, tag)."""
    kr_by_idx = dict(K.KR)
    for start, (cnt, text) in K.G.items():
        widths = [int(rows[start + k]['cells']) for k in range(cnt)]
        lines = wrap(text, widths)
        if lines is None:
            raise SystemExit('rec%d 문단 줄바꿈 실패: %r' % (start, text))
        for k, ln in enumerate(lines):
            kr_by_idx[start + k] = ln
    plans = []
    for r in rows:
        idx = int(r['idx'])
        if idx == 106:                      # 묶음표는 따로
            continue
        kr = kr_by_idx.get(idx)
        if kr is None:
            continue
        off, cells = int(r['offset'], 16), int(r['cells'])
        nb = enc(kr, slot, rev)
        if len(nb) > cells * 2:
            raise SystemExit('rec%d %d칸 > %d칸: %r' % (idx, len(nb) // 2, cells, kr))
        plans.append((off, d[off:off + cells * 2], nb.ljust(cells * 2, b'\x00'), 'rec%d' % idx))
    return plans


def t106_plan(d, slot, rev, rows):
    """병기·이동 타입 묶음표 — **필드 시작 위치를 지켜** 필드 단위로 갈아끼운다."""
    r = rows[106]
    base, cells = int(r['offset'], 16), int(r['cells'])
    # ★병기도감 표(MUSEUM_*)에만 있는 항공기 타입이 여기에도 나온다 — 둘 다 합친다.
    tbl = {}
    for _d in (S.TYPEVAL_WEAPON, S.TYPEVAL_MOVE, S.MUSEUM_TYPES, S.MUSEUM_MOVES):
        tbl.update(_d)
    tbl.update(EXTRA_TYPES)
    from fontdec import table as _ftab, decode as _dec
    ft = _ftab('SAKUCG')
    nb = bytearray(d[base:base + cells * 2])
    n_done = 0
    for i in range(T106_WEAPON_N + T106_MOVE_N):
        if i < T106_WEAPON_N:
            a, w = i * T106_WEAPON_W, T106_WEAPON_W
        else:
            a = T106_WEAPON_N * T106_WEAPON_W + (i - T106_WEAPON_N) * T106_MOVE_W
            w = T106_MOVE_W
        if a + w > cells:
            break
        jp = ''.join(_dec(d, base + 2 * (a + j), 1, ft) for j in range(w)).strip()
        if not jp:
            continue
        kr = T106_TAIL_KR if jp.startswith('VP') else tbl.get(jp)
        if kr is None:
            raise SystemExit('rec106 필드%d 번역 없음: %r' % (i, jp))
        if len(kr) > w:
            raise SystemExit('rec106 필드%d %d칸 > %d칸: %r' % (i, len(kr), w, kr))
        nb[a * 2:(a + w) * 2] = enc(kr, slot, rev).ljust(w * 2, b'\x00')
        n_done += 1
    return [(base, d[base:base + cells * 2], bytes(nb), 'rec106(%d필드)' % n_done)]


def forces_plan(d, slot, rev):
    plans = []
    for i, kr in enumerate(K.FORCES):
        off = K.FORCES_BASE + i * K.FORCES_STRIDE
        nb = enc(kr, slot, rev).ljust(K.FORCES_W * 2, b'\x00')
        plans.append((off, d[off:off + K.FORCES_W * 2], nb, '진영%d' % i))
    return plans


def gate(plans, d):
    """★종료자(0xFFFF)를 한 칸도 덮지 않는지 — 세션8-a 세이브화면 파손과 같은 클래스."""
    bad = 0
    for off, old, new, tag in plans:
        for i in range(0, len(old), 2):
            if (old[i] << 8 | old[i + 1]) == 0xFFFF:
                bad += 1
                if bad < 6:
                    print('  ❌%s @0x%06x 셀%d 에 종료자가 있다' % (tag, off, i // 2))
    if bad:
        raise SystemExit('★종료자 침범 %d곳 — 기록 중단' % bad)
    print('관문 통과 — 계획 영역에 종료자 없음.')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or resync

    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'SAKUSEN')
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
    rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))
    slot = F.build_slots()
    rev = rev_map()

    pl = text_plans(d, slot, rev, rows) + t106_plan(d, slot, rev, rows) + forces_plan(d, slot, rev)
    gate(pl, d)
    print('/SAKUSEN lba=%d size=%d — 본문 %d + 묶음표 1 + 진영 %d'
          % (lba, size, len(pl) - 1 - len(K.FORCES), len(K.FORCES)))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    F.write_font()                     # ① 폰트 먼저(같은 slot 으로 배정됨)
    touched = set()
    with open(dst, 'r+b') as w:
        for off, old, new, tag in pl:
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

    with open(dst, 'rb') as r:
        cur = read_file(r, lba, size)
    bad = sum(1 for off, old, new, tag in pl if cur[off:off + len(new)] != new)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 되읽기 일치, EDC/ECC 유효.')


if __name__ == '__main__':
    main()
