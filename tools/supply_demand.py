# -*- coding: utf-8 -*-
"""소형 폰트 한글화 — 공급(재정의 가능 슬롯) vs 수요(고유 한글 음절) 실측.

핵심 구조: 폰트 5벌이 바이트 동일 = 글리프 하나를 한글로 재정의하면 **모든 모듈**에서 바뀐다.
  ⇒ 어떤 가나 글리프 X를 한글로 쓰려면, 번역/로마자화 뒤에도 X를 참조하는 소형폰트 텍스트가
    **하나도 없어야** 한다. 카테고리가 가나로 남으면 그 가나는 공급에서 빠진다.

수요(한글 대상 카테고리)와 공급(가나로 남는 카테고리에 안 쓰이는 가나 + 안 쓰는 라틴/기호)을
시나리오별로 계산한다.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
from vocab_draft import WEAPON, TERRAIN, TIME, UI

EXTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'extract')


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return f.read()


def rec(buf, off, n=8):
    return sf.decode(buf, off, n, stop=False).rstrip('\x00 ').replace('\x00', '')


def kana_slots(strings):
    """문자열들이 쓰는 가나 글리프 인덱스(63~143)."""
    s = set()
    for t in strings:
        for ch in t:
            k = sf.REV.get(ch)
            if k is not None and 63 <= k <= 143:
                s.add(k)
    return s


def latin_sym_slots(strings):
    """소문자(37~62)·기호(144~171) 사용 인덱스."""
    lo, sym = set(), set()
    for t in strings:
        for ch in t:
            k = sf.REV.get(ch)
            if k is None:
                continue
            if 37 <= k <= 62:
                lo.add(k)
            elif 144 <= k <= 171:
                sym.add(k)
    return lo, sym


def hangul_syl(d):
    s = set()
    for v in d.values():
        for ch in v:
            if '가' <= ch <= '힣':
                s.add(ch)
    return s


def main():
    gmdt = load('GMDT')
    museum = load('MUSEUM')

    weapons = [rec(gmdt, 0x74c4 + i * 8) for i in range(181)]
    terrain = [rec(gmdt, 0x74c4 + (181 + i) * 8) for i in range(11)]
    places = [rec(gmdt, 0x74c4 + (192 + i) * 8) for i in range(437 - 192)]
    units = [rec(museum, 0x7e3c2 + i * 0x52) for i in range(645)]

    # UI 풀 원문 문자열 (0xff/fe/fd/00 구분)
    ui_pool = []
    region = gmdt[0x24740:0x24c60]
    cur = bytearray()
    for b in region:
        if b in (0, 0xfd, 0xfe, 0xff):
            if cur:
                ui_pool.append(sf.decode(cur, 0, len(cur), stop=False))
            cur = bytearray()
        else:
            cur.append(b)
    if cur:
        ui_pool.append(sf.decode(cur, 0, len(cur), stop=False))

    # 카테고리별 가나 사용
    cats = {
        'weapons': weapons, 'terrain': terrain, 'places': places,
        'units': units, 'ui': ui_pool,
    }
    kana = {k: kana_slots(v) for k, v in cats.items()}
    ALL_KANA = set()
    for v in kana.values():
        ALL_KANA |= v
    print('전체 소형폰트 가나 사용: %d / 81  (모든 알려진 소비자 합집합)' % len(ALL_KANA))
    for k, v in kana.items():
        print('  %-8s %d칸' % (k, len(v)))

    # 안 쓰는 라틴/기호 (한글로 재활용 가능한 비가나 슬롯)
    all_str = weapons + terrain + places + units + ui_pool
    lo, sym = latin_sym_slots(all_str)
    free_lo = [i for i in range(37, 63) if i not in lo]      # 안 쓰는 소문자
    free_sym = [i for i in range(144, 172) if i not in sym]   # 안 쓰는 기호
    print('\n비가나 여유: 안쓰는 소문자 %d칸 %s, 안쓰는 기호 %d칸 %s'
          % (len(free_lo), [sf.CHARS[i] for i in free_lo],
             len(free_sym), [sf.CHARS[i] for i in free_sym]))

    # 수요 (한글 대상 카테고리)
    dW, dT, dTm, dU = hangul_syl(WEAPON), hangul_syl(TERRAIN), hangul_syl(TIME), hangul_syl(UI)

    print('\n' + '=' * 64)
    print('시나리오 (units·places 는 항상 로마자화)')
    print('=' * 64)

    NONKANA_FREE = len(free_lo) + len(free_sym)
    EXPAND = 11   # 240글리프 확장분 (실기 확정, MUSEUM)

    # 참고: 시간대(アサ/ヒル…)·맵커맨드·지형문자열은 전부 UI 풀(kana['ui']) 안에 있다.
    def scenario(name, demand, kana_kept_cats):
        keep_kana = set()
        for c in kana_kept_cats:
            keep_kana |= kana[c]
        freed_kana = ALL_KANA - keep_kana
        supply = len(freed_kana) + NONKANA_FREE
        s0 = supply            # 확장 없이
        s1 = supply + EXPAND   # 확장 포함
        def st(sup):
            return ('여유 %d' % (sup - len(demand))) if len(demand) <= sup else ('부족 %d' % (len(demand) - sup))
        print('  %-30s 수요 %3d  공급 확장전 %3d(%s) / 확장후 %3d(%s)'
              % (name, len(demand),
                 s0, st(s0), s1, st(s1)))

    # dU 는 UI dict 전체(시간대 TIME 은 별도 dict). UI 풀에 시간대도 있으므로 함께 한글화 가정.
    dUI_all = dU | dTm
    scenario('①무기+지형+UI 전부 한글', dW | dT | dUI_all, [])            # 모든 가나 해방
    scenario('②무기+지형만 한글(UI 가나유지)', dW | dT, ['ui'])
    scenario('③무기+지형+지명한글아님·UI 한글', dW | dT | dUI_all, [])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
