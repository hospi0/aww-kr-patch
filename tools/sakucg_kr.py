# -*- coding: utf-8 -*-
"""SAKUCG 한글 글리프 — 슬롯 배정 + 폰트 제자리 기록 (세션15).

왜: 미션 타이틀·편성명 표는 **3벌 사본**인데 SAKUSEN 사본만 SAKUCG 를 쓴다.
    라틴은 세 폰트 인덱스가 같아 한 번에 됐지만(세션10·11), 한글은 SAKUCG 에 없다.
    ⇒ SAKUCG 의 **미참조 가나·한자 슬롯을 회수**해 한글을 넣고,
      SAKUSEN 사본만 그 인덱스로 인코딩한다.

★**제자리(inplace) 기록** — 파일 크기·LBA·디렉터리 전부 불변이다.
  폰트 재배치·확장은 이 프로젝트에서 반복해서 사고를 냈다(세션5 크래시, 세션14 디렉터리 리셋).
  회수 방식은 그 위험이 아예 없다.

배정은 `work/sakucg_slots.json` 에 고정 저장한다(재빌드 안정성 — 배정이 흔들리면
그 폰트로 인코딩한 텍스트를 전부 다시 써야 한다).
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import sakucg_reclaim as R
from hangul import render_kr
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
SLOTS = os.path.join(ROOT, 'work', 'sakucg_slots.json')
GLYPH = 128


def demand():
    """SAKUSEN 사본이 필요로 하는 한글 음절(빈도 내림차순 → 배정 안정).

    ★세션16: 작전·브리핑 본문(sakusen_kr)과 진영표(FORCES)도 여기에 들어온다.
      SAKUCG 를 쓰는 텍스트는 **전부 이 한 곳에서** 음절을 모아야 슬롯이 어긋나지 않는다.
    """
    from collections import Counter
    import kr_s15 as S
    freq = Counter()
    src = list(S.FORMATIONS.values()) + list(S.INFO_TITLES.values()) + list(S.MISSION16)
    try:
        import sakusen_kr as K
        src += list(K.KR.values()) + [t for _, t in K.G.values()] + list(K.FORCES)
        src += list(S.TYPEVAL_WEAPON.values()) + list(S.TYPEVAL_MOVE.values())
        src += list(S.MUSEUM_TYPES.values()) + list(S.MUSEUM_MOVES.values())
        src += ['토치카／요새', '더미', 'VP가 부족합니다']   # rec106 묶음표 보충분
    except ImportError:
        pass
    for v in src:
        for c in v:
            if '가' <= c <= '힣':
                freq[c] += 1
    return [c for c, _ in sorted(freq.items(), key=lambda t: (-t[1], t[0]))]


PUNCT_KANA = {'ー', '・', '゛', '゜', 'ヽ', 'ヾ', 'ゝ', 'ゞ'}


def free_full():
    """★세션16: SAKUCG **가나·한자 전부**를 회수 대상으로 본다.

    세션15는 「어떤 텍스트도 참조하지 않는 슬롯」만 254칸 회수했지만, 이제 SAKUSEN 의
    텍스트를 전부 번역하므로 원본 글리프는 아무도 안 읽는다
    ([[feedback_aww_full_kr_budget]] = 천장 전체가 공급).
    ⚠️라틴·숫자·로마숫자·기호와 **문장부호성 가나**(ー・゛゜…)는 남긴다 —
      `ー` 는 제식명 하이픈이라 회수하면 `B-17` 이 `B목17` 이 된다(세션15-c 실사고).
    """
    import json as _j
    fm = _j.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    out = []
    for k, ch in fm.items():
        i = int(k)
        if not ch or len(ch) != 1 or ch in PUNCT_KANA:
            continue
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF:
            out.append(i)
    return sorted(out)


def shared_reserved():
    """SAKUCG 가 **비켜줘야 하는** 인덱스 → 그 자리의 공용 음절.

    ★★세션19: 공용 슬롯은 「여러 폰트의 같은 인덱스에 같은 글리프」가 전제다.
      SAKUCG 전용 배정이 그 인덱스를 **다른 음절**로 쓰면 그 화면만 깨진다.
      · shared_slots(유닛명·부대명)  = ASC16CG·ASCMSCG·SAKUCG
      · shared_school_slots(동료이름) = ASC16CG·SCHOOL·**SAKUCG**  ← 세션17이 SAKUCG 를 빠뜨렸다
      실기 증상: 사관학교 동료 `로잘리` 가 인터미션에서 **`증벨길`** 로 떴다
      (로=214·잘=564·리=170 을 SAKUCG 전용 배정 `증`·`벨`·`길` 이 점유하고 있었다).
    ⇒ 공용 자리는 SAKUCG 전용 배정에서 제외하고, 이미 점유한 것은 **재배정**한다.
    """
    res = {}
    import shared_slots as _SU
    import shared_school_slots as _SS
    for c, g in _SU.build(verbose=False).items():
        res[int(g)] = c
    for c, g in _SS.build(verbose=False).items():
        res[int(g)] = c
    return res


def build_slots():
    need = demand()
    free = free_full()
    slot = {}
    if os.path.exists(SLOTS):
        slot = json.load(open(SLOTS, encoding='utf-8'))
    # ★공용 자리를 점유한 전용 배정은 놓아준다(그 음절은 아래에서 새 자리를 받는다).
    res = shared_reserved()
    evicted = [c for c, g in slot.items() if res.get(int(g), c) != c]
    for c in evicted:
        del slot[c]
    free = [i for i in free if i not in res]
    if evicted:
        print('  ★공용 자리와 겹쳐 재배정하는 SAKUCG 전용 음절 %d개: %s'
              % (len(evicted), ' '.join(evicted)))
    taken = set(slot.values())
    pool = [i for i in free if i not in taken]
    for c in need:
        if c in slot:
            continue
        if not pool:
            raise SystemExit('★SAKUCG 회수 슬롯 고갈 — 수요 %d / 가용 %d'
                             % (len(need), len(free)))
        slot[c] = pool.pop(0)
    json.dump(slot, open(SLOTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('SAKUCG 한글 %d음절 → 회수 슬롯 %d칸 중 사용 (여유 %d)'
          % (len(slot), len(free), len(free) - len(slot)))
    return slot


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def write_font(revert=False):
    """/SAKUCG 파일의 회수 슬롯에 한글 글리프를 제자리 기록(크기 불변)."""
    slot = build_slots()
    # ★세션17-c: 유닛명 표는 사본 하나인데 **개발·생산 화면(SAKUCG)** 도 읽는다.
    #   ASC16CG·ASCMSCG 와 **같은 인덱스에 같은 글리프**를 그려야 한다(shared_slots).
    #   ⚠️`slot` 에 병합하지 않는다 — 병합하면 SAKUCG 자체 텍스트의 음절 인덱스가 바뀐다.
    #     여기서는 **글리프만 추가로 그린다**.
    import shared_slots as _SH
    _shared = _SH.build(verbose=False)
    # ★세션19: 동료(부관) 이름 표도 사본이 하나인데 **인터미션·작전 화면이 SAKUCG 로 읽는다.**
    #   세션17 은 ASC16CG·SCHOOL 두 폰트에만 그려서 인터미션에서 `로잘리`→`증벨길` 로 깨졌다.
    #   ⚠️`slot` 에 병합하지 않는다 — SAKUCG 자체 텍스트의 음절 인덱스가 바뀐다. 글리프만 추가.
    #   🐞두 공용 등록부를 **dict 로 합치면 안 된다** — 같은 음절이 양쪽에서 다른 인덱스를
    #     가지면(`로`=unit589/school214 등 17개) 한쪽이 덮여 그 자리에 글리프가 안 그려진다.
    #     ⇒ **(음절, 인덱스) 쌍 리스트**로 이어 붙여 양쪽 자리를 다 그린다.
    import shared_school_slots as _SS
    _shared = list(_shared.items()) + list(_SS.build(verbose=False).items())
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    with open(TRACK1, 'rb') as o:
        hits, _, _, _ = find_dirrec(o, 'SAKUCG')
        if len(hits) != 1:
            raise SystemExit('SAKUCG 디렉터리 %d개' % len(hits))
        _, lba, size, _ = hits[0]
        orig = read_file(o, lba, size)
    print('SAKUCG lba=%d size=%d (%d글리프) — 제자리 기록' % (lba, size, size // GLYPH))

    touched = set()
    with open(dst, 'r+b') as w:
        for c, gi in list(slot.items()) + _shared:
            blob = orig[gi * GLYPH:(gi + 1) * GLYPH] if revert else bytes(render_kr(c, ramp='dark'))
            for k in range(GLYPH):
                lo = gi * GLYPH + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                w.write(blob[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    # 독립 되읽기
    bad = 0
    with open(dst, 'rb') as r:
        cur = read_file(r, lba, size)
        for c, gi in list(slot.items()) + _shared:
            want = orig[gi * GLYPH:(gi + 1) * GLYPH] if revert else bytes(render_kr(c, ramp='dark'))
            if cur[gi * GLYPH:(gi + 1) * GLYPH] != want:
                bad += 1
    if bad:
        raise SystemExit('독립검증 실패 %d칸' % bad)
    print('독립검증 통과 — 글리프 %d칸(+공용 유닛명 %d) %s'
          % (len(slot), len(_shared), '복구' if revert else '한글'))
    return slot


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--write' in sys.argv:
        write_font()
    elif '--revert' in sys.argv:
        write_font(revert=True)
    else:
        s = build_slots()
        print('드라이런 — 미기록 (--write / --revert)')
        print('  예:', list(s.items())[:8])
