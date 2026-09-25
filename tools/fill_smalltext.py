# -*- coding: utf-8 -*-
"""smalltext.tsv 의 kr 컬럼 채우기 (1차: 무기·지형·UI 한글).

무기/지형/UI는 가나 토큰을 최장일치로 찾아 vocab_draft 값으로 치환, 숫자·라틴·기호는 유지.
유닛·지명(로마자)은 별도 결정 대기라 이번엔 비운다.
8칸 고정폭 표(무기)의 초과를 검출해 출력.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
from vocab_draft import WEAPON, TERRAIN, TIME, UI, ROMAJI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'work', 'smalltext', 'smalltext.tsv')

# 최장일치 치환 사전 (가나 토큰 → 한국어/라틴)
TOK = {}
TOK.update(WEAPON)
TOK.update(TERRAIN)
TOK.update(TIME)
TOK.update(UI)
TOK.update(ROMAJI)
# 8칸 초과 방지용 짧은 로마자 (문맥상 숫자가 붙는 무기)
TOK['カノン'] = 'Can'      # 155㎜カノンL → 155㎜CanL
TOK['シュレッケ'] = 'Schrek'  # P· 접두 고려


def is_kana(c):
    # 재정의(해방) 대상 가나만. ー(154)·・(145)는 기호 슬롯이라 유지 → 제외.
    return ('゠' <= c <= 'ヿ') and c not in ('ー', '・')


def translate(jp):
    """가나 런을 최장일치로 치환, 나머지는 유지."""
    out = []
    i = 0
    n = len(jp)
    while i < n:
        if is_kana(jp[i]):
            j = n
            hit = None
            # 최장일치
            while j > i:
                seg = jp[i:j]
                if seg in TOK:
                    hit = (seg, TOK[seg])
                    break
                j -= 1
            if hit:
                out.append(hit[1])
                i += len(hit[0])
            else:
                out.append(jp[i])   # 미등록 가나 (그대로 — 나중에 검출)
                i += 1
        else:
            out.append(jp[i])
            i += 1
    return ''.join(out)


def encodable(kr):
    """모든 글자가 인코딩 가능한가 (한글은 신규슬롯 예정이라 OK로 간주, 나머지는 REV 확인)."""
    bad = []
    for c in kr:
        if '가' <= c <= '힣':
            continue
        if c not in sf.REV:
            bad.append(c)
    return bad


def main():
    rows = [l.rstrip('\n').split('\t') for l in open(TSV, encoding='utf-8')]
    header, data = rows[0], rows[1:]
    overflow, unmapped, badchar = [], [], []

    HARDVERIFY = {'ヒナミ', 'セイミヤ'}   # 아이콘 마커 사이 미상 필드 — 실기확인 대상, 미번역 유지
    marker_skip = []
    for r in data:
        mod, kind, off, ln, jp, hx, idx, kr = r
        if not jp:
            continue
        raw = bytes.fromhex(hx)
        if any(b > 171 for b in raw):     # <ac><ad><ae> 등 그래픽/아이콘 마커 = 텍스트 아님
            marker_skip.append((mod, kind, jp, hx))
            continue
        if jp in HARDVERIFY:
            continue
        target = None
        if kind == 'weapons' or (kind == 'names' and int(idx) < 181):
            target = translate(jp)
            maxlen = 8
        elif kind == 'names' and 181 <= int(idx) < 192:   # GMDT 지형
            target = translate(jp)
            maxlen = 8
        elif kind == 'terrain':                            # SAKUSEN 지형
            target = translate(jp)
            maxlen = None
        elif kind == 'ui':
            target = translate(jp)
            maxlen = None
        else:
            continue  # units / places (지명) 는 로마자 결정 대기

        r[7] = target
        # 미치환 가나 검출
        if any(is_kana(c) and c not in '・' for c in target):
            leftover = [c for c in target if is_kana(c) and c != '・']
            unmapped.append((mod, kind, jp, target, ''.join(leftover)))
        # 8칸 초과 (글리프 수 기준: 한글1·기호1·㎜1)
        if maxlen:
            glyphs = len(target)  # 근사(합자 ㎜/㎏ 1칸)
            if glyphs > maxlen:
                overflow.append((mod, kind, jp, target, glyphs))
        bc = encodable(target)
        if bc:
            badchar.append((mod, kind, jp, target, bc))

    with open(TSV, 'w', encoding='utf-8') as f:
        f.write('\t'.join(header) + '\n')
        for r in data:
            f.write('\t'.join(r) + '\n')

    print('채움 완료. 무기/지형/UI 한글 삽입.')
    print('\n미치환 가나 남은 항목 %d개:' % len(unmapped))
    seen = set()
    for mod, kind, jp, tg, lo in unmapped:
        if jp in seen:
            continue
        seen.add(jp)
        print('  [%s] %-16s -> %-16s (남은가나 %s)' % (kind, jp, tg, lo))
    print('\n8칸 초과 %d개:' % len(overflow))
    seen = set()
    for mod, kind, jp, tg, g in overflow:
        if jp in seen:
            continue
        seen.add(jp)
        print('  %-16s -> %-14s (%d칸)' % (jp, tg, g))
    print('\n인코딩불가 문자 %d개' % len(badchar))
    for mod, kind, jp, tg, bc in badchar[:20]:
        print('  %-16s -> %-14s bad=%s' % (jp, tg, bc))
    print('\n마커/그래픽 스킵 %d개 (미번역 유지)' % len(marker_skip))
    print('실기확인 대상(아이콘 사이 미상): ヒナミ, セイミヤ')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
