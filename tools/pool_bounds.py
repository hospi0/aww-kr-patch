# -*- coding: utf-8 -*-
"""델리미터 풀(구분자 00/fd/fe/ff 로 갈리는 짧은 텍스트 나열)의 정확한 경계 탐지.

주어진 앵커에서 양방향으로 확장하며, "짧은 유효글리프 문자열 + 구분자" 패턴이
끊기는 곳(그래픽/데이터)을 경계로 잡는다.
텍스트 판정: 다음 구분자까지 길이 ≤ 20, 전부 유효글리프(≤171), 비어있지 않음.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf

EXTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'extract')
SEP = {0, 0xfd, 0xfe, 0xff}


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return f.read()


def next_field(buf, i, end):
    """i에서 시작하는 (구분자 스킵 후) 한 필드의 (start, bytes)와 다음 i."""
    while i < end and buf[i] in SEP:
        i += 1
    s = i
    while i < end and buf[i] not in SEP:
        i += 1
    return s, buf[s:i], i


def field_ok(fb):
    if len(fb) == 0 or len(fb) > 20:
        return False
    return all(b <= 171 for b in fb)


def find_bounds(buf, anchor, win_bad=6):
    """앵커 주변에서 텍스트 필드가 연속하는 최대 구간. 나쁜 필드 win_bad개 연속이면 끊음."""
    n = len(buf)
    # 앞으로
    i = anchor
    end_hi = anchor
    bad = 0
    while i < n:
        s, fb, i = next_field(buf, i, n)
        if not fb and i >= n:
            break
        if field_ok(fb):
            end_hi = i
            bad = 0
        else:
            bad += 1
            if bad >= win_bad:
                break
    # 뒤로 (역방향은 근사: 앵커에서 아래로 스캔하며 시작점 찾기)
    lo = anchor
    j = anchor
    bad = 0
    # 뒤로 걸어가며 구분자 경계를 찾아 필드 검사
    while j > 0:
        # j 직전 필드 찾기
        k = j - 1
        while k > 0 and buf[k] in SEP:
            k -= 1
        e = k + 1
        while k > 0 and buf[k - 1] not in SEP:
            k -= 1
        fb = buf[k:e]
        if field_ok(fb):
            lo = k
            bad = 0
        else:
            bad += 1
            if bad >= win_bad:
                break
        j = k
        if k == 0:
            break
    return lo, end_hi


def dump(buf, lo, hi, maxn=200):
    i = lo
    cnt = 0
    while i < hi and cnt < maxn:
        s, fb, i = next_field(buf, i, hi)
        if fb and any(63 <= b <= 143 for b in fb):
            print('  0x%06x  %-18s %s' % (s, sf.decode(fb, 0, len(fb), stop=False)[:22], fb.hex()))
            cnt += 1


TARGETS = [
    ('GMDT', 0x2484f, 'UI풀'),
    ('SAKUSEN', 0x492f2, '지형리스트'),
    ('SAKUSEN', 0x4ebf6, '지명+지형풀'),
]

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for mod, anchor, name in TARGETS:
        buf = load(mod)
        lo, hi = find_bounds(buf, anchor)
        print('=' * 64)
        print('%s %s  경계 0x%x ~ 0x%x  (%d B)  앵커 0x%x'
              % (mod, name, lo, hi, hi - lo, anchor))
        dump(buf, lo, hi, 12)
        print('  ... (끝부분)')
        # 끝 12개
        allf = []
        i = lo
        while i < hi:
            s, fb, i = next_field(buf, i, hi)
            if fb and any(63 <= b <= 143 for b in fb):
                allf.append((s, fb))
        for s, fb in allf[-6:]:
            print('  0x%06x  %-18s %s' % (s, sf.decode(fb, 0, len(fb), stop=False)[:22], fb.hex()))
