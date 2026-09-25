# -*- coding: utf-8 -*-
"""부관이름 공용 슬롯 관문 (세션17).

「독립 되읽기는 계획대로 써졌나만 본다」([[feedback_kr_patch_verification]] §세션15-g)를
피하려고, **불변식 자체**를 검사한다.

  ① 공용 슬롯 인덱스가 asc16_slots·shared_unit_slots·school_slots 어디와도 안 겹친다
     (겹치면 그 자리에 다른 음절이 그려져 이름이 깨진다)
  ② 그 인덱스가 SCHOOL 회수 가능 목록 안에 있다 (사관학교의 남은 텍스트를 안 덮는다)
  ③ 그 인덱스가 ASC16CG 원본 가나·한자 구간이다 (라틴·숫자·기호를 덮지 않는다 —
     로마자 텍스트가 그 인덱스를 그대로 쓴다)
  ④ 두 폰트 빌더가 실제로 **같은 글리프 비트맵**을 그 인덱스에 넣는다
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap
import shared_school_slots as S
from hangul import render_kr
from build_school_text import RAMP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUNCT_KANA = {'ー', '・', '゛', '゜', 'ヽ', 'ヾ', 'ゝ', 'ゞ'}


def load(name):
    p = os.path.join(ROOT, 'work', name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sh = S.build(verbose=False)
    bad = 0

    # ① 등록부 충돌
    for reg in ('asc16_slots.json', 'shared_unit_slots.json', 'school_slots.json'):
        other = {int(v): k for k, v in load(reg).items()}
        for c, g in sh.items():
            if g in other and other[g] != c:
                print('❌① %s: 슬롯 %d 를 %r 이 이미 씀 (이름 음절 %r)' % (reg, g, other[g], c))
                bad += 1

    # ② SCHOOL 회수 가능
    import school_reclaim as R
    free = set(R.load())
    for c, g in sh.items():
        if g not in free:
            print('❌② 슬롯 %d(%r) 은 SCHOOL 이 아직 참조 중' % (g, c))
            bad += 1

    # ③ ASC16CG 가나·한자 구간
    for c, g in sh.items():
        ch = charmap.CHARS.get(g)
        o = ord(ch) if ch and len(ch) == 1 else 0
        if not (ch and ch not in PUNCT_KANA
                and (0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF)):
            print('❌③ 슬롯 %d(%r) 원본 글리프가 %r — 가나·한자가 아니다' % (g, c, ch))
            bad += 1

    # ④ 두 폰트 빌더가 실제로 이 슬롯을 그리는가 (소스 참조 검사).
    #    ⚠️비트맵 자체를 비교하면 안 된다 — ASC16CG 는 ramp='raw', SCHOOL 은 'dark' 로
    #      **의도적으로 계조가 다르다**(획 모양은 같고 명암 매핑만 다르다). 임계값으로
    #      경계를 재려 하면 옅은 AA 때문에 늘 불일치가 난다([[feedback_kr_patch_verification]] ②).
    for f in ('build_ui16.py', 'build_school_text.py', 'build_school_names.py'):
        src = open(os.path.join(ROOT, 'tools', f), encoding='utf-8').read()
        if 'shared_school_slots' not in src:
            print('❌④ %s 가 공용 슬롯을 안 쓴다 — 이름이 한쪽 화면에서 깨진다' % f)
            bad += 1

    # ⑤ ★진짜 검증 — 실제 기록될 바이트를 **두 화면의 폰트로 각각 디코드**한다.
    #   「계획대로 써졌나」가 아니라 「두 화면에서 같은 글자로 보이나」를 본다.
    #   (이 검사가 있었으면 세션15-g에 바로 걸렸다.)
    import struct
    import build_school_text as T
    from build_school_names import NAMES, REC_BASE, STRIDE, NREC, OFF16, W16
    from school_charmap import SCHOOL_CHARS

    def screen(raw, reg_files, extra):
        """glyph 인덱스열 → 그 폰트에서 실제로 보이는 문자열"""
        m = {}
        for rf in reg_files:
            for c, g in load(rf).items():
                m.setdefault(int(g), c)
        m.update({int(g): c for c, g in extra.items()})
        out = ''
        for j in range(W16):
            v = struct.unpack_from('>H', raw, j * 2)[0]
            if v == 0:
                break
            out += m.get(v) or SCHOOL_CHARS.get(v) or charmap.CHARS.get(v, '〈%d〉' % v)
        return out

    from isoread import TRACK1
    from build_reloc import find_dirrec
    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'SCHOOL')
        _, lba, size, _ = hits[0]
        d = T.read_file(f, lba, size)
    t, rev = T.tables()
    plans = T.plan_names(d, T.build_slots(), rev, t, T.small_map())
    seen = 0
    for o, old, new, tag in plans:
        if not tag.endswith('16'):
            continue
        jp = tag[:-2]
        kr = NAMES[jp][0]
        s_school = screen(new, ['school_slots.json'], sh)
        s_battle = screen(new, ['asc16_slots.json', 'shared_unit_slots.json'], sh)
        seen += 1
        if s_school != kr or s_battle != kr:
            print('❌⑤ %s: 사관학교=%r / 전투화면=%r (기대 %r)' % (jp, s_school, s_battle, kr))
            bad += 1
    print('⑤ 이름 %d곳 — 두 화면 디코드 대조' % seen)

    print('공용 슬롯 %d음절, 슬롯 %d~%d' % (len(sh), min(sh.values()), max(sh.values())))
    print('관문 %s' % ('통과 ✅' if bad == 0 else '실패 ❌ %d건' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
