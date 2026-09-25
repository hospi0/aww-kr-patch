# -*- coding: utf-8 -*-
"""소형 8x8 폰트 가나(63~143)를 쓰는 **모든 구조**를 찾는다.

배경: 폰트 5벌 바이트동일 → 가나 글리프를 한글로 재정의하면 그 가나를 쓰는 모든 소형폰트
      텍스트가 바뀐다. 재정의 전에 소비자를 빠짐없이 열거하지 못하면 표시버그(플레이어가
      엉뚱한 한글을 본다). [[feedback_kr_patch_verification]] §11, 세션4 0x7e7ec 교훈.

방법: 가나 바이트가 등장하는 오프셋을 모아 근접 클러스터로 묶는다. 알려진 테이블
      (무기/지형/지명/유닛/UI풀)과 대조해 **미확인 구조**를 드러낸다.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf

EXTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'extract')

FONT_MODULES = ['GMDT', 'MUSEUM', 'SAKUSEN', 'KEKKA', 'INTERM']

# 폰트 데이터 자체(가나 글리프 비트맵)는 제외해야 한다 — 가나 바이트가 아니라 글리프 픽셀.
FONT_RANGE = {  # (fo, fo+256*32) 확장 여유까지
    'GMDT': (0x28ef8, 0x28ef8 + 256 * 32),
    'MUSEUM': (0x109e8, 0x109e8 + 256 * 32),
    'SAKUSEN': (0x1c9cc, 0x1c9cc + 256 * 32),
    'KEKKA': (0x17cb8, 0x17cb8 + 256 * 32),
    'INTERM': (0x3ab40, 0x3ab40 + 256 * 32),
}

# 알려진 소비자 (모듈, 시작, 끝, 이름)
KNOWN = {
    'GMDT': [(0x74c4, 0x74c4 + 437 * 8, '이름표(무기/지형/지명)'),
             (0x24740, 0x24c60, 'UI풀')],
    'MUSEUM': [(0x7e3c2, 0x7e3c2 + 645 * 0x52, '유닛명표'),
               (0x90210, 0x90210 + 181 * 8, '무기표사본')],
    'SAKUSEN': [(0x542d8, 0x542d8 + 181 * 8, '무기표사본')],
    'KEKKA': [(0x3af82, 0x3af82 + 181 * 8, '무기표사본')],
    'INTERM': [],
}


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return f.read()


def is_kana(b):
    return 63 <= b <= 143


def known_label(mod, off):
    for s, e, name in KNOWN.get(mod, []):
        if s <= off < e:
            return name
    return None


def valid_glyph(b):
    # 렌더 가능한 텍스트 글리프: 공백0, 숫자/영문/가나/기호 1~171. 172~255(아이콘/미정)는 텍스트 아님.
    return b <= 171


def find_text_runs(buf, fr):
    """오직 유효 글리프 바이트(≤171)로만 된 런 중, 가나 밀도 높고 단어스러운 것.

    필터: 런은 전부 ≤171, 길이≥4, 가나 비율≥35%, 가나 2개 이상. 폰트구간 제외.
    노이즈(0xc0~0xff 섞인 바이너리)는 유효글리프 조건에서 걸러진다.
    """
    runs = []
    i, n = 0, len(buf)
    while i < n:
        if fr[0] <= i < fr[1]:
            i = fr[1]
            continue
        if valid_glyph(buf[i]) and is_kana(buf[i]):
            j = i
            while j < n and valid_glyph(buf[j]) and not (fr[0] <= j < fr[1]):
                j += 1
            run = buf[i:j]
            nk = sum(1 for b in run if is_kana(b))
            # 공백/0 제외한 실사용 길이
            core = [b for b in run if b != 0]
            if len(core) >= 4 and nk >= 2 and nk / max(1, len(core)) >= 0.35:
                runs.append((i, j, len(run), nk))
            i = j
        else:
            i += 1
    return runs


def scan(mod):
    buf = load(mod)
    fr = FONT_RANGE[mod]
    runs = find_text_runs(buf, fr)
    # 알려진 소비자 안/밖 분류
    known_runs, unknown_runs = [], []
    for r in runs:
        lab = known_label(mod, r[0])
        (known_runs if lab else unknown_runs).append((r, lab))
    print('=' * 72)
    print('%s  텍스트런 %d개 (알려진 %d / 미확인 %d)'
          % (mod, len(runs), len(known_runs), len(unknown_runs)))
    # 미확인을 오프셋순으로, 근접한 것끼리 묶어 구조 추정
    unknown_runs.sort(key=lambda x: x[0][0])
    print('  --- 미확인 텍스트런 (오프셋순) ---')
    for (s, e, span, nk), _ in unknown_runs[:60]:
        sample = sf.decode(buf, s, min(span, 44), stop=False)
        print('    0x%06x  len=%-4d 가나=%-3d  %s' % (s, span, nk, sample[:40]))
    if len(unknown_runs) > 60:
        print('    ... 외 %d개' % (len(unknown_runs) - 60))
    return unknown_runs


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    tot = 0
    for m in FONT_MODULES:
        tot += len(scan(m))
    print('\n총 미확인 텍스트런: %d' % tot)
