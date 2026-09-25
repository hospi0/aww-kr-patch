# -*- coding: utf-8 -*-
"""ASC16CG·SCHOOL **공용** 한글 슬롯 — 사관학교 동료(부관) 이름 전용 (세션17).

왜 필요한가
  사관학교 동료 이름표(/SCHOOL 0x07AF5C, stride 0x62)는 **사본이 하나인데 두 화면이 읽는다**:
      사관학교 화면 = SCHOOL 내장 폰트   /   전투화면 좌패널·유닛 헤더 = ASC16CG
  세션15-g의 `build_school_names` 는 SCHOOL 슬롯으로만 인코딩했다.
  ⇒ 전투화면에서는 같은 인덱스가 ASC16CG 글리프로 렌더돼 깨진다.
     실기 증상(사용자 스샷 2026-07-26): 「로절리」가 **「줄詰입」**
     (SCHOOL 91=로·765=절·149=리  ↔  ASC16CG 91=줄·765=詰(미회수)·149=입).
  세션15-e 유닛명(`shared_slots.py`, ASC16CG↔ASCMSCG)과 **같은 클래스의 함정**이다.

성립하는 이유
  이 게임의 16×16 폰트들은 글리프 배열 순서가 같다(charmap 공통, 세션15 실측).
  그러니 가나·한자 인덱스 i 를 고르면 두 폰트에서 같은 글자를 덮는 것이라 의미가 안 어긋난다.

배정 규칙
  · 대상 = build_school_names.NAMES 의 16×16 한글 이름이 쓰는 음절
  · 자리 = **세 등록부(asc16_slots·shared_unit_slots·school_slots) 어디에도 안 쓰인** 인덱스 중
           `school_reclaim` 이 회수 가능이라고 판정한 것 (SCHOOL 본문이 아직 참조하면 안 된다)
  · 라틴·숫자·로마숫자·문장부호성 가나는 제외 (로마자 텍스트가 그 인덱스를 그대로 쓴다)
  · work/shared_school_slots.json 에 **고정** — 흔들리면 두 폰트를 다시 다 써야 한다
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, 'work', 'shared_school_slots.json')
REGS = ('asc16_slots.json', 'shared_unit_slots.json', 'school_slots.json')

MAXG = 820                      # 폰트들이 공통으로 갖는 구간 (ASC16CG 825글리프 안쪽)
PUNCT_KANA = {'ー', '・', '゛', '゜', 'ヽ', 'ヾ', 'ゝ', 'ゞ'}


def _need():
    """이름 음절 — 빈도 높은 순(자리 고갈 시 흔한 음절부터 확보)."""
    from build_school_names import NAMES
    from collections import Counter
    freq = Counter()
    for kr, _ in NAMES.values():
        for c in kr:
            if '가' <= c <= '힣':
                freq[c] += 1
    return [c for c, _ in sorted(freq.items(), key=lambda t: (-t[1], t[0]))]


def _load(name):
    p = os.path.join(ROOT, 'work', name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def build(verbose=True):
    need = _need()
    shared = _load(os.path.basename(STORE))

    # 다른 음절이 이미 쓰는 인덱스 = 못 쓴다.
    # (같은 음절이라도 등록부마다 인덱스가 다르므로, 공용 슬롯은 **별도 인덱스**를 받는다.
    #  본문 텍스트는 기존 등록부 인덱스를 계속 쓰고, 이름만 공용 인덱스를 쓴다 — 재정렬 없음.)
    blocked = set()
    for reg in REGS:
        blocked |= {int(g) for g in _load(reg).values()}
    blocked -= set(shared.values())

    import school_reclaim as R
    school_free = set(R.load())

    def usable(i):
        ch = charmap.CHARS.get(i)
        if ch is None or len(ch) != 1 or ch in PUNCT_KANA:
            return False
        o = ord(ch)
        return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF

    pool = [i for i in range(1, MAXG)
            if usable(i) and i in school_free
            and i not in blocked and i not in set(shared.values())]
    added = 0
    for c in need:
        if c in shared:
            continue
        if not pool:
            raise SystemExit('★ASC16CG·SCHOOL 공용 슬롯 고갈 — 수요 %d' % len(need))
        shared[c] = pool.pop(0)
        added += 1
    # 안 쓰게 된 음절도 등록부에 남긴다(다시 쓰일 때 같은 자리를 받도록)
    json.dump(shared, open(STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    if verbose:
        print('  공용 부관이름 슬롯 %d음절 (신규 %d, 남은 후보 %d) — ASC16CG·SCHOOL 동일 인덱스'
              % (len(shared), added, len(pool)))
    return shared


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    s = build()
    print('예:', list(s.items())[:12])
