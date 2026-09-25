# -*- coding: utf-8 -*-
"""16×16 텍스트 풀(구분자 0xFFFF)의 **진짜 경계**를 종료자로 확정한다 — 세션16.

세션15-g 교훈: `/SCHOOL` 은 눈대중으로 잡은 0x39000~0x3BC00 이 **양끝 다 틀렸다**
(앞 12바이트에 버튼 라벨, 뒤 180칸에 브리핑 전문이 잘려 있었다).
같은 실수를 시나리오 3풀에 반복하지 않으려고 만든다.

방법 — 워드 단위로 훑으며 「텍스트다움」을 본다:
  · 유효 셀 = 0(공백) · 0xFFxx(제어/종료) · 1~NG(폰트 글리프 인덱스)
  · 창(WIN 워드) 안 유효율이 THRESH 이상인 구간만 텍스트로 본다
  · 텍스트 구간의 시작/끝은 **가장 가까운 0xFFFF 종료자**로 스냅한다

사용: python tools/pool_bounds16.py            전 풀
      python tools/pool_bounds16.py KEKKA 0x20000 0x24000 825
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files

WIN = 32
THRESH = 0.92
MIN_RUN = 16          # 이보다 짧은 텍스트 조각은 노이즈로 본다(워드)

# 모듈: (폰트 글리프수, 넉넉한 탐색범위)
TARGETS = [
    ('/KEKKA',   825,  0x01F000, 0x024000),
    ('/SAKUSEN', 1017, 0x047000, 0x050000),
    ('/INTERM',  697,  0x068000, 0x071000),
]


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, 'rb') as f:
                return read_range(f, lba, size)
    raise SystemExit('no such file: ' + path)


def cells(d, lo, hi):
    return [(d[i] << 8) | d[i + 1] for i in range(lo, min(hi, len(d) - 1), 2)]


MAXREC = 80           # 이보다 긴 레코드는 텍스트로 안 본다(워드)


def split_records(v):
    """0xFFFF 로 자른 (시작인덱스, 셀리스트). 종료자는 포함하지 않는다."""
    out = []
    s = 0
    for i, x in enumerate(v):
        if x == 0xFFFF:
            out.append((s, v[s:i]))
            s = i + 1
    if s < len(v):
        out.append((s, v[s:]))
    return out


def is_text(rec, ng):
    """텍스트 레코드 판정 — 글리프가 하나라도 있고, 이상 셀이 없고, 길이가 상식적."""
    if not rec or len(rec) > MAXREC:
        return False
    glyphs = 0
    for x in rec:
        if x == 0 or x >= 0xFF00:
            continue
        if 1 <= x <= ng:
            glyphs += 1
        else:
            return False
    return glyphs > 0


def bounds(d, lo, hi, ng):
    v = cells(d, lo, hi)
    recs = split_records(v)
    flag = [is_text(r, ng) for _, r in recs]
    runs = []
    i = 0
    while i < len(recs):
        if flag[i]:
            j = i
            nbad = 0
            k = i
            while k < len(recs):
                if flag[k]:
                    j = k
                    nbad = 0
                else:
                    nbad += 1
                    if nbad > 2:      # 비텍스트 3연속이면 구간 종료
                        break
                k += 1
            if j - i >= 2:
                a = recs[i][0]
                b = recs[j][0] + len(recs[j][1]) + 1      # 종료자 포함
                runs.append((lo + a * 2, lo + min(b, len(v)) * 2, j - i + 1))
            i = k
        else:
            i += 1
    return runs


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1:
        mod, lo, hi, ng = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), int(sys.argv[4])
        tg = [('/' + mod.lstrip('/'), ng, lo, hi)]
    else:
        tg = TARGETS
    for mod, ng, lo, hi in tg:
        d = get(mod)
        print('=== %s  탐색 0x%06X~0x%06X (파일 %d B, 폰트 %d글리프)'
              % (mod, lo, hi, len(d), ng))
        for a, b in bounds(d, lo, hi, ng):
            print('   텍스트 0x%06X ~ 0x%06X   (%d 워드)' % (a, b, (b - a) // 2))


if __name__ == '__main__':
    main()
