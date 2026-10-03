# -*- coding: utf-8 -*-
"""문장부호 뒤 공백 1칸 삭제 — 기록된 이미지에 **제자리** 적용 (2026-10-03, 사용자 «모든 문장»).

전프로젝트 규칙([[feedback_no_space_after_punct]]): 표준 문장부호 뒤 공백(반각·전각) **1칸**은 지우고,
2칸 이상 이어진 공백은 칸 맞춤이라 둔다.

왜 제자리인가: 이 프로젝트엔 마스터 빌드가 없고 각 빌더가 「그때의 F: 상태」를 전제로 짜여 있어
빌더 전체를 다시 돌리면 뒤에 돌린 빌더의 수정을 덮을 위험이 있다. 그래서
  ① 각 빌더가 **영구 고정**한 슬롯 표 + 글꼴 맵으로 「지금 문장」을 인코딩해 이미지에서 찾고
     (찾아진다 = 인코딩이 실제 기록과 같다는 검증)
  ② 같은 자리에 「공백 뺀 문장 + 빠진 만큼의 공백」(= 길이 불변, 끝 공백은 빈칸)을 쓴다.
번역표 원문도 함께 고쳐 두었으므로(다음 빌드부터 자동 반영) 이 도구는 **이미 고친 원문**의
「옛 문장」을 OLD 표로 갖고 있다.

사용: python tools/fix_punct_space.py <Track01.bin>            드라이런
      python tools/fix_punct_space.py <Track01.bin> --write    기록
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import RAW, HDR, USER
from build_reloc import find_dirrec
from build_interm_title import read_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from kr_rules import squeeze


def _json(name):
    return json.load(open(os.path.join(ROOT, 'work', name), encoding='utf-8'))


def _fontmap(name):
    fm = _json('fontmaps.json')[name]
    rev = {}
    for k, v in fm.items():
        rev.setdefault(v, int(k))
    return rev


# ── 표마다 인코더(각 빌더의 enc 와 같은 규칙) ─────────────────────────────
def enc_ui16():
    import build_ui16 as B
    B.squeeze = lambda t: t        # ★옛 문장을 그대로 인코딩해야 이미지에서 찾힌다
    import shared_slots
    _, rev = B.load_map()
    slot = dict(_json('asc16_slots.json'))
    slot.update(shared_slots.build(verbose=False))
    return lambda s: B.enc_kr(s, slot, rev)


def enc_school():
    import build_school_text as B
    B.squeeze = lambda t: t        # ★옛 문장을 그대로 인코딩해야 이미지에서 찾힌다
    _, rev = B.tables()
    slot = _json('school_slots.json')
    return lambda s: B.enc16(s, slot, rev)


def enc_interm():
    import build_interm_text as B
    B.squeeze = lambda t: t        # ★옛 문장을 그대로 인코딩해야 이미지에서 찾힌다
    _, rev = B.font_map()
    slot = _json('ascimcg_slots.json')
    return lambda s: B.enc(s, slot, rev)


def enc_chrono():
    import build_chrono as B
    B.squeeze = lambda t: t        # ★옛 문장을 그대로 인코딩해야 이미지에서 찾힌다
    import build_menu as BM
    _, rev = B.load_map()
    slot = dict(BM.build_slots())                 # 594~719 (build_chrono.build_slots 와 같은 합성)
    slot.update(_json('brief_slots.json'))
    slot.update(_json('chrono_slots.json'))
    return B.make_enc(rev, slot)


# (표 이름, 인코더, 찾을 파일들, 옛 문장들) — 옛 문장 = 이 도구를 만들기 직전 번역표 값
JOBS = [
    ('ui16 MESSAGES', enc_ui16, ['GAME', 'GMDT', 'KEKKA', 'SAKUSEN'], [
        '자동보충 ON. 보급·보충을 자동 실행',
        '저장 중입니다. 전원을 끄면',
    ]),
    ('chrono', enc_chrono, ['GMSELDT'], [
        '「전투 파쇼」 결성',
    ]),
    ('school LINES', enc_school, ['SCHOOL'], [
        '되어 있다. 지금까지처럼',
        '가상 적국인 적국, 그 거점 ',
        '항공기를 고르고 곧바로「발진」 ',
        '바뀐다. 이는 그 병기가「행동 ',
        '된다. 적군 행동을 보며 다음 ',
        '거듭 말한다. 되도록      ',
        '다음은 날씨 강의다. 방금 말한',
        '뭐, 이 정도 날씨라면     ',
        '문제는 날씨가 비, 눈이    ',
    ]),
]


# ★시나리오 문단(interm_kr.G)은 화면 줄 폭으로 **자동 줄바꿈**돼 여러 레코드에 걸쳐 기록된다.
#   공백 하나만 빠져도 문단 전체의 줄 나눔이 바뀌므로 **문단 단위로 다시 접어** 레코드 전부를 쓴다.
#   (옛 문장, 새 문장) — 새 문장 None = squeeze(옛). 136번은 줄바꿈 때문에 문장을 다듬었다(사용자 승인).
INTERM_OLD = [
    ('발칸 침공 등 예상 밖의 사태로 연기됐던 소련 침공작전『바르바로사 작전』 개시가 6월22일로 결정되었다。',
     '발칸 침공 등 뜻밖의 사태로 연기됐던 소련 침공작전 『바르바로사』는 6월22일 개시로 결정됐다。'),
    ('1945년1월20일▶「가을안개 작전」 성공으로▶연합국과 우리나라의 강화 성립。▶동시에 오늘 연합국은 소련에▶선전 포고。', None),
]


def interm_edits(f, files):
    import build_interm_text as B
    from scenario_wrap import wrap
    enc = enc_interm()
    if 'INTERM' not in files:
        h, _, _, _ = find_dirrec(f, 'INTERM')
        _, lba, size, _ = h[0]
        files['INTERM'] = (lba, read_file(f, lba, size))
    lba, d = files['INTERM']
    out = []
    for old, new in INTERM_OLD:
        new = squeeze(new or old)
        found = None
        for pool, _, g in B.POOLS:
            for start, (cnt, text) in g.items():
                if text in (old, new):
                    found = (pool, start, cnt)
        if not found:
            raise SystemExit('★interm 문단 못 찾음: %r' % old[:20])
        pool, start, cnt = found
        rows = B.rows_of(pool)
        widths = [int(rows[start + k]['cells']) for k in range(cnt)]
        lo, ln = wrap(old, widths), wrap(new, widths)
        if ln and any(len(x) == w and k + 1 < cnt and ln[k + 1] and x[-1] != ' '
                      and new.find(x + ln[k + 1][:1]) >= 0 for k, (x, w) in enumerate(zip(ln, widths))):
            print('  ⚠️낱말 중간 줄바꿈 남음: %r' % ln)
        if lo is None or ln is None:
            raise SystemExit('줄바꿈 실패 %r' % old[:20])
        for k in range(cnt):
            r = rows[start + k]
            off, cells = int(r['offset'], 16), int(r['cells'])
            ob = enc(lo[k]).ljust(cells * 2, b'\x00')
            nb = enc(ln[k]).ljust(cells * 2, b'\x00')
            if d[off:off + cells * 2] != ob:
                raise SystemExit('★interm %s rec%d 현재 기록이 옛 문장과 다르다' % (pool, start + k))
            if ob != nb:
                out.append((lba, off, ob, nb, 'interm /INTERM 0x%06x  %s → %s' % (off, lo[k], ln[k])))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        raise SystemExit(__doc__)
    dst = args[0]
    write = '--write' in sys.argv
    edits = []            # (lba, 파일오프셋, old, new, 표시)
    files = {}
    with open(dst, 'rb') as f:
        for tag, mk, names, olds in JOBS:
            enc = mk()
            for s in olds:
                t = squeeze(s)
                if t == s:
                    raise SystemExit('바꿀 게 없음: %r' % s)
                # ★interm 은 ▶ 가 줄바꿈 = 레코드 경계라 줄 단위로 인코딩된다
                parts = [(a, b) for a, b in zip(s.split('▶'), t.split('▶')) if a != b] \
                    if '▶' in s else [(s, t)]
                for a, b in parts:
                    old = enc(a)
                    new = enc(b).ljust(len(old), bytes(1))   # 빌더와 같은 0 채움
                    assert len(old) == len(new)
                    hit = 0
                    for nm in names:
                        if nm not in files:
                            h, _, _, _ = find_dirrec(f, nm)
                            _, lba, size, _ = h[0]
                            files[nm] = (lba, read_file(f, lba, size))
                        lba, d = files[nm]
                        i = d.find(old)
                        while i >= 0:
                            if i % 2 == 0:
                                edits.append((lba, i, old, new, '%s /%s 0x%06x  %s → %s' % (tag, nm, i, a, b)))
                                hit += 1
                            i = d.find(old, i + 1)
                    if not hit:
                        raise SystemExit('★못 찾음 [%s] %r — 인코딩이 기록과 다르다' % (tag, a))
        edits += interm_edits(f, files)
    for e in edits:
        print('  ' + e[4])
    print('고칠 곳 %d' % len(edits))
    if not write:
        print('드라이런 — 기록 안 함 (--write).')
        return
    touched = set()
    with open(dst, 'r+b') as w:
        for lba, off, old, new, _ in edits:
            for k in range(len(old)):
                p = off + k
                sec = lba + p // USER
                w.seek(sec * RAW + HDR + p % USER)
                if w.read(1) != old[k:k + 1]:
                    raise SystemExit('대조 실패 @0x%x' % p)
                w.seek(sec * RAW + HDR + p % USER)
                w.write(new[k:k + 1])
                touched.add(sec)
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    with open(dst, 'rb') as r:
        for lba, off, old, new, tag in edits:
            n = len(new)
            back = read_file(r, lba, off + n)[off:]
            if back != new:
                raise SystemExit('독립검증 실패 %s' % tag)
    print('기록 완료 — %d섹터, 독립검증 통과' % len(touched))


if __name__ == '__main__':
    main()
