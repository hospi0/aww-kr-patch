# -*- coding: utf-8 -*-
"""smalltext.tsv 유닛·지명 로마자/한글 채우기 (romaji_map + DESC_HANGUL).

유닛: 베이스 토큰(UNIT_BASE)+접미 유지, 서술형은 한글(DESC_HANGUL)/라틴(DESC_ROMAJI).
지명: 전체 매칭(PLACES) 우선, 아니면 토큰 치환. 미커버는 남겨서 검출.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
from vocab_draft import TERRAIN, DESC_HANGUL, ROMAJI
from romaji_map import DESC_ROMAJI, UNIT_BASE, PLACES, REVIEW
from kata_latin import kata_to_latin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'work', 'smalltext', 'smalltext.tsv')

UNIT_DICT = {}
UNIT_DICT.update(UNIT_BASE)
UNIT_DICT.update(DESC_HANGUL)
UNIT_DICT.update(DESC_ROMAJI)
UNIT_DICT.update(ROMAJI)       # 무기 로마자와 겹치는 것 (Bazooka 등)

PLACE_DICT = {}
PLACE_DICT.update(PLACES)
PLACE_DICT.update(REVIEW)
PLACE_DICT.update(TERRAIN)     # 붕괴/도시 등 지형 접두


def is_kana(c):
    return ('゠' <= c <= 'ヿ') and c not in ('ー', '・')


def tok_translate(jp, D):
    out, i, n = [], 0, len(jp)
    while i < n:
        if is_kana(jp[i]):
            j, hit = n, None
            while j > i:
                if jp[i:j] in D:
                    hit = (jp[i:j], D[jp[i:j]]); break
                j -= 1
            if hit:
                out.append(hit[1]); i += len(hit[0])
            else:
                out.append(jp[i]); i += 1
        else:
            out.append(jp[i]); i += 1
    return ''.join(out)


def freed_kana_left(s):
    return [c for c in s if is_kana(c)]


import re
_SUF = re.compile(r'([0-9Ⅰ-ⅧA-Z()\[\]✕✖./··]+)$')


def fit8(s, maxlen=8):
    """8칸 초과 시 뒤쪽 모델접미(숫자·로마숫자·변형기호)를 보존하고 베이스를 자른다."""
    if len(s) <= maxlen:
        return s
    m = _SUF.search(s)
    suf = m.group(1) if m else ''
    if len(suf) >= maxlen:
        return s[:maxlen]
    base = s[:len(s) - len(suf)]
    return base[:maxlen - len(suf)] + suf


def main():
    rows = [l.rstrip('\n').split('\t') for l in open(TSV, encoding='utf-8')]
    header, data = rows[0], rows[1:]
    stat = {'units': [0, 0], 'places': [0, 0]}   # [covered, total]
    left_u, left_p = set(), set()

    for r in data:
        mod, kind, off, ln, jp, hx, idx, kr = r
        if not jp:
            continue
        if kind == 'units':
            tgt = tok_translate(jp, UNIT_DICT)
            if freed_kana_left(tgt):          # 미커버 → 음차 폴백
                tgt = kata_to_latin(tgt)
                left_u.add(jp)
            else:
                stat['units'][0] += 1
            r[7] = fit8(tgt)                   # 8칸 고정폭 맞춤
            stat['units'][1] += 1
        elif kind == 'places' or (kind == 'names' and 192 <= int(idx) < 437):
            tgt = PLACE_DICT.get(jp) or tok_translate(jp, PLACE_DICT)
            if freed_kana_left(tgt):          # 미커버 → 음차 폴백
                tgt = kata_to_latin(tgt)
                left_p.add(jp)
            else:
                stat['places'][0] += 1
            # GMDT 이름표(names)·SAKUSEN 지명풀(places) 둘 다 고정 8바이트
            r[7] = fit8(tgt)
            stat['places'][1] += 1

    with open(TSV, 'w', encoding='utf-8') as f:
        f.write('\t'.join(header) + '\n')
        for r in data:
            f.write('\t'.join(r) + '\n')

    print('유닛  커버 %d/%d  (%.0f%%)' % (stat['units'][0], stat['units'][1],
          100 * stat['units'][0] / max(1, stat['units'][1])))
    print('지명  커버 %d/%d  (%.0f%%)' % (stat['places'][0], stat['places'][1],
          100 * stat['places'][0] / max(1, stat['places'][1])))
    print('\n미커버 유닛 %d종:' % len(left_u))
    for u in sorted(left_u)[:60]:
        print('  ', u)
    print('\n미커버 지명 %d종:' % len(left_p))
    for p in sorted(left_p)[:60]:
        print('  ', p)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
