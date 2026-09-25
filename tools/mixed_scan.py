# -*- coding: utf-8 -*-
"""★이번 사고의 지문 — 「한글과 원본 가나·한자가 **한 문자열 안에 섞인** 자리」 (세션18).

왜 이게 지문인가
  슬롯을 재배정한 뒤 **일부 빌더만 재기록**하면, 같은 문자열의 사본마다 세대가 갈린다.
  옛 세대 자리는 새 등록부로 디코드하면 **일부 음절만 한글**이고 나머지는 그 슬롯의
  원본 글리프(한자·가나)로 보인다 — 화면의 `승候등車`·`2림톡뤄F류` 가 정확히 그것이다.
  ⇒ 「원본과 다르다(=빌더가 건드렸다) + 그런데 디코드하면 한자가 섞인다」 = 옛 세대.

미번역과의 구별
  미번역 자리는 **원본 바이트 그대로**다(원본과 diff 가 없다). 여기서는 제외한다.

사용: python tools/mixed_scan.py [--show N]
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import charmap
from isoread import TRACK1, read_range
from build_reloc import find_dirrec
from gen_audit import FONTS, _merge

# ★폴백 맵도 **그 모듈의 폰트**여야 한다. charmap.CHARS(ASC16CG 전용)로 폴백하면
#   ASCIMCG·ASCMSCG 자리가 통째로 「한자 섞임」으로 오판된다(오탐 수백 건).
_FM = json.load(open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'work', 'fontmaps.json'), encoding='utf-8'))


def base_map(font):
    if font == 'GMSELDT':
        return {int(k): v for k, v in _FM['ASC16CG2'].items()}
    if font == 'SCHOOL':
        import school_charmap
        return dict(school_charmap.SCHOOL_CHARS)
    # ⚠️ASC16CG 는 **charmap.CHARS** 가 정본이다. fontmaps['ASC16CG2'] 는 일부 인덱스를
    #   다르게 안다(279 를 `優` 로 읽어 `강설시、` 를 `강설시優` 로 오판했다).
    if font in ('ASC16CG', 'SCHOOL'):
        return dict(charmap.CHARS)
    key = font
    if key in _FM:
        return {int(k): v for k, v in _FM[key].items()}
    return dict(charmap.CHARS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHED = os.path.join(r'F:\hospi\roms\ss roms\aww', os.path.basename(TRACK1))

# 모듈 → 그 화면이 쓰는 폰트
MODULES = [
    ('GMDT',    'ASC16CG'),
    ('KEKKA',   'ASC16CG'),
    ('GAME',    'ASC16CG'),
    ('GMSELDT', 'GMSELDT'),
    ('SAKUSEN', 'SAKUCG'),
    ('INTERM',  'ASCIMCG'),
    ('MUSEUM',  'ASCMSCG'),
    ('SCHOOL',  'SCHOOL'),
]
# \u26a0\ufe0f`\u30fb`(U+30FB)\u00b7`\u30fc`\u00b7`\u3005` \ub294 \ud55c\uae00 \ubb38\uc7a5\uc5d0\ub3c4 \uc815\uc0c1\uc73c\ub85c \uc4f0\uc778\ub2e4(`\ub124\ub35c\ub780\ub4dc\u30fb\ubca8\uae30\uc5d0`).
#   \uac00\ub098 \ubc94\uc704\ub77c\ub294 \uc774\uc720\ub85c \uc138\uba74 \uc624\ud0d0 \uc218\uc2ed \uac74\uc774 \ub09c\ub2e4.
PUNCT = set('\u30fb\u30fc\u3005\u30fd\u30fe\u309d\u309e\u309b\u309c')
KANA = lambda c: (len(c) == 1 and c not in PUNCT
                  and ('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff'))
HAN = lambda c: len(c) == 1 and '\uac00' <= c <= '\ud7a3'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 10
    REGS = {k: _merge(v) for k, v in FONTS.items()}
    grand = 0
    for mod, font in MODULES:
        m = REGS.get(font) or REGS['ASC16CG']
        BASE = base_map(font)
        try:
            with open(TRACK1, 'rb') as f:
                hits, _, _, _ = find_dirrec(f, mod)
                _, lba, size, _ = hits[0]
                o = read_range(f, lba, size)
            with open(PATCHED, 'rb') as f:
                hits, _, _, _ = find_dirrec(f, mod)
                _, lba2, size2, _ = hits[0]
                p = read_range(f, lba2, size2)
        except Exception as e:
            print('%-9s 읽기 실패 %s' % (mod, e))
            continue
        n = min(len(o), len(p)) // 2
        # 문자열 런 = 널·0xFFFF 로 끊는다
        bad = []
        i = 0
        while i < n:
            v = struct.unpack_from('>H', p, i * 2)[0]
            if v == 0 or v == 0xFFFF or v > 1200:
                i += 1
                continue
            j = i
            while j < n:
                w = struct.unpack_from('>H', p, j * 2)[0]
                if w == 0 or w == 0xFFFF or w > 1200:
                    break
                j += 1
            if j - i >= 3:
                idx = [struct.unpack_from('>H', p, k * 2)[0] for k in range(i, j)]
                oidx = [struct.unpack_from('>H', o, k * 2)[0] for k in range(i, j)]
                if idx != oidx:                       # 빌더가 건드린 자리만
                    # ★바뀐 셀 구간으로 좁힌다 — 앞뒤에 붙은 **원본 그대로의 다른 필드**를
                    #   같이 세면 `탱0あ비르벨빈트` 처럼 정상 자리가 혼재로 잡힌다.
                    lo_ = next(k for k in range(len(idx)) if idx[k] != oidx[k])
                    hi_ = len(idx) - next(k for k in range(len(idx))
                                          if idx[-1 - k] != oidx[-1 - k])
                    idx = idx[lo_:hi_]
                    s = ''.join(m.get(x) or BASE.get(x, '') for x in idx)
                    han = sum(1 for c in s if HAN(c))
                    kana = sum(1 for c in s if KANA(c))
                    if han >= 2 and kana >= 1:        # ★한글과 원본글자가 섞였다
                        bad.append((i * 2, s))
            i = j + 1
        grand += len(bad)
        print('%-9s [%-8s] ★혼재 %4d곳' % (mod, font, len(bad)))
        for off, s in bad[:show]:
            print('      0x%06x  %s' % (off, s[:56]))
    print('\n총 %d곳' % grand)


if __name__ == '__main__':
    main()
