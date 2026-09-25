# -*- coding: utf-8 -*-
"""ASC16CG·ASCMSCG·**SAKUCG** 공용 한글 슬롯 — 유닛명 전용 (세션15-e, 세션17-c 확장).

왜 필요한가
  유닛명 표(MUSEUM 0x7E404)는 **사본이 하나인데 두 화면이 읽는다**:
      전투화면 좌패널 = ASC16CG  /  병기도감 = ASCMSCG  /  **개발·생산 = SAKUCG**
  ★세션17-c: 세 번째 소비자(SAKUCG)를 세션15-e가 놓쳐서 개발 화면 유닛명이 깨졌다
    (실기: `Ⅲ호돌격포B형` → **`3림심봉률B류`**). 240칸 중 220칸이 SAKUCG 텍스트와 충돌.
    ⇒ **세 폰트 모두에서 비어 있는 인덱스**로 재배정한다(가능 자리 228 / 수요 227).
  미션타이틀·편성명은 사본이 3벌이라 「모듈별 인코딩」으로 풀렸지만, 여기는 같은 바이트다.
  ⇒ ASC16CG 슬롯으로 인코딩하면 병기도감에서 깨진다(실기: `37mm니サ進接`).
  ⇒ **두 폰트의 같은 인덱스에 같은 한글 글리프**를 넣는 수밖에 없다.

성립하는 이유
  두 폰트는 글리프 0~819 가 **바이트 동일**(세션15 실측)이다. 그러니 어떤 가나·한자
  인덱스 i 를 골라도 두 폰트에서 같은 글자를 덮는 것이라 의미가 어긋나지 않는다.

배정 규칙
  · 대상 = kr_s15.UNIT16 + KANJI_UNITS 가 쓰는 한글 음절
  · 자리 = 가나·한자 글리프 중 **두 등록부(asc16_slots·museum_slots) 어디에도 안 쓰인** 인덱스
  · 문장부호성 가나(ー·・…)와 라틴·숫자·로마숫자는 제외 (유닛명 로마자가 그걸 쓴다)
  · work/shared_unit_slots.json 에 고정 — 흔들리면 두 폰트를 다시 다 써야 한다
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, 'work', 'shared_unit_slots.json')
ASC16 = os.path.join(ROOT, 'work', 'asc16_slots.json')
MUSEUM = os.path.join(ROOT, 'work', 'museum_slots.json')
SAKUCG = os.path.join(ROOT, 'work', 'sakucg_slots.json')
SCHOOL_SH = os.path.join(ROOT, 'work', 'shared_school_slots.json')

MAXG = 820                      # 두 폰트가 바이트 동일한 구간 (0~819)
PUNCT_KANA = {'ー', '・', '゛', '゜', 'ヽ', 'ヾ', 'ゝ', 'ゞ'}


def _need():
    import kr_s15 as S
    from collections import Counter
    freq = Counter()
    srcs = [S.UNIT16, S.KANJI_UNITS]
    import json as _j, os as _o                       # 세션15-f: 가타카나 유닛명도 두 폰트 공용
    _f = _o.path.join(ROOT, 'work', 'katakana_names.json')
    if _o.path.exists(_f):
        srcs.append(_j.load(open(_f, encoding='utf-8')))
    # ★★세션19: **부대명·장군명도 여기 들어와야 한다.**
    #   UPK 로스터 16×16 이름 필드(build_general16)는 사본이 하나인데
    #   전투맵 = ASC16CG / **인터미션·작전 = SAKUCG** 두 화면이 읽는다.
    #   세션17-c 는 유닛명만 세 폰트 공용으로 만들고 부대명을 빠뜨려, 공용에 없는
    #   음절 49종이 SAKUCG 에서 원본 글리프로 떴다 —
    #   실기: `プルシー軍`→`프로이센군`인데 화면은 **`프로이握군`**(898=`센`이 SAKUCG 에선 `握`),
    #        `ポーランド空軍Ⅰ`→`폴란드공군Ⅰ`인데 화면은 **`녁란드공군Ⅰ`**(299=`폴`→`녁`).
    #   384종 중 323종(1,014레코드)이 깨져 있었다.
    _f2 = _o.path.join(ROOT, 'work', 'force16_names.json')
    if _o.path.exists(_f2):
        srcs.append(_j.load(open(_f2, encoding='utf-8')))
    for d in srcs:
        for v in d.values():
            for c in v:
                if '가' <= c <= '힣':
                    freq[c] += 1
    return [c for c, _ in sorted(freq.items(), key=lambda t: (-t[1], t[0]))]


def _load(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}


def build(verbose=True):
    need = _need()
    shared = _load(STORE)
    a16 = _load(ASC16)
    mus = _load(MUSEUM)
    sak = _load(SAKUCG)
    shs = _load(SCHOOL_SH)

    # ★인덱스 g 를 유닛명 음절 c 에 줄 수 있는 조건
    #   · 어느 등록부도 g 를 안 쓰면 → 아무 음절에나 줄 수 있다(자유 자리)
    #   · 어떤 등록부가 g 를 음절 x 로 쓰면 → **x 에게만** 줄 수 있다
    #     (같은 글자니 그 자리에 그 글자를 그리면 양쪽 화면이 다 맞는다)
    #   · 등록부들이 g 를 **서로 다른 음절**로 쓰면 → 아무에게도 못 준다
    owner, clash = {}, set()
    for reg in (a16, mus, sak, shs):
        for c, g in reg.items():
            if g in owner and owner[g] != c:
                clash.add(g)
            owner[g] = c

    def usable(i):
        ch = charmap.CHARS.get(i)
        if ch is None or len(ch) != 1 or ch in PUNCT_KANA:
            return False
        o = ord(ch)
        return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF

    free, reserved = [], {}
    for i in range(1, MAXG):
        if not usable(i) or i in clash:
            continue
        o = owner.get(i)
        if o is None:
            free.append(i)
        elif o in need:
            reserved.setdefault(o, i)
    for c, g in reserved.items():          # ① 같은 음절 자리 재사용
        if c not in shared and g not in set(shared.values()):
            shared[c] = g
    pool = [i for i in free if i not in set(shared.values())]
    print('  자리: 재사용 %d + 자유 %d = %d  (수요 %d)'
          % (len(reserved), len(pool), len(reserved) + len(pool), len(need)))
    added = 0
    for c in need:
        if c in shared:
            continue
        if not pool:
            raise SystemExit('★공용 슬롯 고갈 — 수요 %d' % len(need))
        shared[c] = pool.pop(0)
        added += 1
    json.dump(shared, open(STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    if verbose:
        print('  공용 유닛명 슬롯 %d음절 (신규 %d, 남은 후보 %d) — ASC16CG·ASCMSCG·SAKUCG 동일 인덱스'
              % (len(shared), added, len(pool)))
    return shared


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    s = build()
    print('예:', list(s.items())[:10])
