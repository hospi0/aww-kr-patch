# -*- coding: utf-8 -*-
"""시나리오 번역표 관문 — 기록 **전에** 걸러야 하는 것만 본다 (세션16).

세션15-g 교훈: 되읽기 검증은 「계획대로 써졌나」만 본다. 계획 자체가 틀리면 못 잡는다.
그래서 번역표 단계에서 다음 넷을 강제한다.

  ① 길이     한글 셀 수 ≤ 원문 셀 수 (넘으면 옆 레코드를 먹는다)
  ② 제어코드 {FD} 등이 원문과 **같은 개수·같은 순서**, 세그먼트별 길이도 원문 이하
  ③ 치환토큰 원문에 있던 `F`(장군명)·`G`(병기명)가 **같은 레코드에** 남아 있는가
  ④ 인코딩   그 모듈 폰트로 낼 수 없는 문자가 없는가(반각·한글식 부호 등)

사용: python tools/scenario_check.py kekka_medal
"""
import os
import re
import sys
import csv
import json
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 풀 이름 → (번역표 모듈, 폰트이름 in fontmaps 또는 None=charmap)
POOL_KR = {
    'kekka_medal':  ('kekka_kr', None),
    'kekka_result': ('kekka_kr', None),
    'sakusen_msg':  ('sakusen_kr', 'SAKUCG'),
    'interm_brief': ('interm_kr', 'ASCIMCG'),
    'interm_title': ('interm_small_kr', 'ASCIMCG'),
    'interm_chrono': ('interm_small_kr', 'ASCIMCG'),
    'interm_doc':   ('interm_small_kr', 'ASCIMCG'),
}

ALT_DICT = {'kekka_result': 'RESULT', 'interm_title': 'TITLE', 'interm_chrono': 'CHRONO', 'interm_doc': 'DOC'}

CTRL = re.compile(r'\{[0-9A-F]{2}\}')
# 16×16 폰트엔 전각 기호만 있다 — 번역표에서 반각을 쓰면 여기서 잡는다.
PUNCT = {'.': '。', ',': '、', '?': '？', '!': '！', '(': '（', ')': '）',
         '·': '・', '%': '％', '-': 'ー', ':': '：'}


def font_chars(font):
    if font is None:
        return set(charmap.CHARS.values())
    fm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))
    return set(fm[font].values())


def standalone(s, tok):
    """앞뒤가 라틴·숫자가 아닌 `F`/`G` 개수 = 이름 치환자."""
    n = 0
    for m in re.finditer(re.escape(tok), s):
        a = s[m.start() - 1] if m.start() else ''
        b = s[m.end()] if m.end() < len(s) else ''
        if not (a.isascii() and a.isalnum()) and not (b.isascii() and b.isalnum()):
            n += 1
    return n


def segs(s):
    """제어코드로 자른 (세그먼트리스트, 제어코드리스트)."""
    parts = CTRL.split(s)
    codes = CTRL.findall(s)
    return parts, codes


def expand_groups(mod, rows):
    """번역표의 G(문단표) → 레코드별 한글. 문단은 원본 줄폭에 흘려 넣는다."""
    from scenario_wrap import wrap
    out, fail = {}, []
    for start, (cnt, text) in getattr(mod, 'G', {}).items():
        widths = [int(rows[start + k]['cells']) for k in range(cnt)]
        lines = wrap(text, widths)
        if lines is None:
            # ★보수적으로 본다 — 줄바꿈이 낱말 중간이면 공백 절약이 없다.
            capacity = sum(widths)
            fail.append('rec%-4d %2d줄 용량%3d / 번역%3d (%+d) %r'
                        % (start, cnt, capacity, len(text), capacity - len(text), text))
            continue
        for k, ln in enumerate(lines):
            out[start + k] = ln
    return out, fail


def check(name, verbose=False):
    mod_name, font = POOL_KR[name]
    mod = importlib.import_module(mod_name)
    rows0 = list(csv.DictReader(open(os.path.join(ROOT, 'work', 'scenario', name + '.tsv'),
                                     encoding='utf-8'), delimiter='\t'))
    KR = dict(getattr(mod, ALT_DICT.get(name, 'KR'), getattr(mod, 'KR', {})))
    gk, gfail = expand_groups(mod, rows0)
    KR.update(gk)
    rows = rows0
    chars = font_chars(font)
    bad = list(gfail)
    syl = set()
    done = 0
    for r in rows:
        idx = int(r['idx'])
        cells = int(r['cells'])
        jp = r['jp']
        kr = KR.get(idx)
        if kr is None:
            continue
        done += 1
        jsegs, jcodes = segs(jp)
        ksegs, kcodes = segs(kr)
        # ① 전체 길이
        if len(CTRL.sub('', kr)) + len(kcodes) > cells:
            bad.append('rec%-4d 길이 %d칸 > 원문 %d칸  %r'
                       % (idx, len(CTRL.sub('', kr)) + len(kcodes), cells, kr))
        # ② 제어코드
        if jcodes != kcodes:
            bad.append('rec%-4d 제어코드 불일치 원문%s → 번역%s' % (idx, jcodes, kcodes))
        elif jcodes:
            for k, (a, b) in enumerate(zip(jsegs, ksegs)):
                if len(b) > len(a):
                    bad.append('rec%-4d 세그%d %d칸 > 원문 %d칸  %r' % (idx, k, len(b), len(a), b))
        # ③ 치환 토큰 — **홀로 선 F·G만** 센다.
        #   `FPW`·`BGM` 처럼 다른 라틴 문자에 붙은 것은 낱말이지 치환자가 아니다.
        for tok in ('F', 'G'):
            if standalone(jp, tok) != standalone(kr, tok):
                bad.append('rec%-4d 치환토큰 %s 개수 %d → %d  %r'
                           % (idx, tok, standalone(jp, tok), standalone(kr, tok), kr))
        # ④ 인코딩 가능성
        for c in CTRL.sub('', kr):
            if '가' <= c <= '힣':
                syl.add(c)
                continue
            if c in chars or PUNCT.get(c) in chars:
                continue
            if 0x21 <= ord(c) <= 0x7E and chr(ord(c) + 0xFEE0) in chars:
                continue
            bad.append('rec%-4d 폰트에 없는 문자 %r  %r' % (idx, c, kr))
    print('=== %s  번역 %d / %d레코드   고유 한글음절 %d'
          % (name, done, len(rows), len(syl)))
    for b in bad:
        print('  ❌', b)
    if not bad:
        print('  관문 통과 — 길이·제어코드·치환토큰·인코딩 이상 없음.')
    return len(bad), syl


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    names = sys.argv[1:] or list(POOL_KR)
    tot = 0
    allsyl = set()
    for n in names:
        try:
            b, s = check(n)
        except ModuleNotFoundError:
            print('=== %s  번역표 없음(미착수)' % n)
            continue
        tot += b
        allsyl |= s
    if len(names) > 1:
        print('\n합계 고유 한글음절 %d' % len(allsyl))
    if tot:
        raise SystemExit('★관문 실패 %d건' % tot)


if __name__ == '__main__':
    main()
