# -*- coding: utf-8 -*-
"""SCHOOL 내장 폰트 **글리프 슬롯 회수** — 세션15-g.

★확장이 물리적으로 불가능하다: 폰트 `0x1C574` + 917×128 = **0x38FF4**, 본문이 **0x39000**에서
  시작한다(간격 12바이트). ⇒ 917이 하드 상한이고 **회수만이 유일한 예산원**이다.
  (천장 1024는 charnum 여유일 뿐 파일에 자리가 없다.)

★조건은 오히려 좋다 — **소비자가 `/SCHOOL` 단일 파일**이라 완전 열거가 된다(SAKUCG와 동일).
  그리고 본문 4,120자를 **전부 번역**하므로 그 텍스트가 쓰던 가나·한자가 통째로 풀린다.

판정: `/SCHOOL` 전체에서 **우리가 덮어쓸 구간을 제외한** 곳이 참조하는 글리프 인덱스를 census.
  덮어쓸 구간 = 본문 0x39000~0x3BC00 + 공군동료 이름 레코드(16×16 필드).
  ⚠️라틴·숫자·기호는 번역문이 쓰므로 회수 대상에서 뺀다(「」！？／・．－ 등).
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap
from school_charmap import SCHOOL_CHARS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'work', 'school_reclaim.json')

NGLYPH = 917
# ★실측 정정(세션15-g): 처음 잡은 0x39000~0x3BC00 은 **양끝이 다 틀렸다**.
#   아래는 폰트 끝 = 본문 시작(0x38FF4, 「戦闘講義」 라벨이 12바이트 틈에 끼어 있다)과
#   마지막 레코드의 종료자(0xFFFF @0x3BD68)로 다시 잡은 값. 잘린 범위 탓에 rec55 뒤 9줄이
#   통째로 번역에서 빠져 실기에 일본어로 남았다 ⇒ **범위는 종료자로 확정하라.**
TEXT_LO, TEXT_HI = 0x38FF4, 0x3BD6A
REC_BASE, STRIDE, NREC, OFF16, W16 = 0x07AF5C, 0x62, 35, 0x0A, 8
# ★이름 입력 가나 팔레트 — 사용자 결정으로 **공백 처리**하므로 회수 대상에 넣는다
PALETTE_LO, PALETTE_HI = 0x003EF8, 0x004048
DENSE_WIN, DENSE_MIN = 11, 8

# 🐞세션17: 폰트 **비트맵 구간**을 안 가려서 픽셀 바이트가 글리프 인덱스로 오인됐다.
#   (0x1C574 + 917×128 = 0x38FF4. 실제로 '保'·'選'·'燃' 이 여기서만 「참조」로 잡혔다.)
FONT_LO, FONT_HI = 0x01C574, 0x038FF4
# 🐞세션17: 등차수열도 걸러야 한다. `116,118,120,122…`(2씩) `890,891,892…`(1씩) 같은
#   좌표·오프셋 테이블이 밀도 판정을 통과해 「텍스트」로 잡혔다. 진짜 텍스트는 인덱스가
#   무작위라 등차가 길게 이어지지 않는다. [[feedback_scan_coverage_and_detectors]]
ARITH_RUN = 6          # 같은 공차가 이만큼 이어지면 테이블로 보고 배제


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, 'rb') as f:
                return read_range(f, lba, size)
    raise SystemExit('no such file: ' + path)


def masked(d):
    """우리가 덮어쓸 구간을 0xFFFF 로 가려 census 대상에서 뺀다."""
    b = bytearray(d)
    for i in range(TEXT_LO, min(TEXT_HI, len(b)), 2):
        b[i:i + 2] = b'\xff\xff'
    for n in range(NREC):
        o = REC_BASE + n * STRIDE + OFF16
        for k in range(W16 * 2):
            if o + k < len(b):
                b[o + k] = 0xFF
    for i in range(PALETTE_LO, min(PALETTE_HI, len(b)), 2):   # 가나 팔레트
        b[i] = 0xFF
        b[i + 1] = 0xFF
    for i in range(FONT_LO, min(FONT_HI, len(b)), 2):         # 폰트 비트맵(세션17)
        b[i:i + 2] = b'\xff\xff'
    return bytes(b)


def _arith_mask(v, ok):
    """등차수열 위치를 표시한다 — 좌표·오프셋 테이블을 텍스트로 오인하지 않으려고."""
    n = len(v)
    bad = [False] * n
    i = 0
    while i < n - 1:
        if not (ok[i] and ok[i + 1]):
            i += 1
            continue
        step = v[i + 1] - v[i]
        j = i + 1
        while j < n - 1 and ok[j + 1] and v[j + 1] - v[j] == step:
            j += 1
        if j - i + 1 >= ARITH_RUN:
            for k in range(i, j + 1):
                bad[k] = True
        i = j if j > i else i + 1
    return bad


def census():
    """남는 텍스트가 참조하는 글리프 인덱스 집합."""
    d = masked(get('/SCHOOL'))
    n = len(d) // 2
    v = [(d[2 * k] << 8) | d[2 * k + 1] for k in range(n)]
    ok = [1 if 1 <= x < NGLYPH else 0 for x in v]
    arith = _arith_mask(v, ok)
    used = set()
    half = DENSE_WIN // 2
    for k in range(n):
        if not ok[k] or arith[k]:
            continue
        lo, hi = max(0, k - half), min(n, k + half + 1)
        if sum(ok[lo:hi]) >= DENSE_MIN:      # 밀도 판정 = 진짜 텍스트만
            used.add(v[k])
    return used


def load(refresh=False):
    """회수 가능 슬롯(오름차순). 라틴·숫자·기호는 남긴다."""
    if not refresh and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding='utf-8'))['free']
    used = census()
    t = dict(charmap.CHARS)
    t.update(SCHOOL_CHARS)
    # 번역문이 한글 아닌 문자로 쓰는 글리프 = 보존
    keep = set()
    try:
        import school_kr as K
        for kl in K.LINES.values():
            for line in kl:
                for c in line:
                    if not ('가' <= c <= '힣'):
                        keep.add(c)
    except ImportError:
        pass
    keep |= set('0123456789 ／・．－「」！？（）')

    def reclaimable(i):
        ch = t.get(i)
        if ch is None or len(ch) != 1 or ch in keep:
            return False
        o = ord(ch)
        return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF

    free = sorted(i for i in range(1, NGLYPH) if i not in used and reclaimable(i))
    json.dump({'free': free, 'used': len(used)},
              open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    return free


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    free = load(refresh=True)
    print('SCHOOL 폰트 %d글리프 — 회수 가능 %d칸' % (NGLYPH, len(free)))
    print('  앞 30:', free[:30])
    try:
        import school_kr as K
        syl = set()
        for kl in K.LINES.values():
            for line in kl:
                syl |= {c for c in line if '가' <= c <= '힣'}
        import json as _j
        p = os.path.join(ROOT, 'work', 'school_slots.json')
        if os.path.exists(p):
            syl |= set(_j.load(open(p, encoding='utf-8')))
        print('  수요 %d음절 → %s' %
              (len(syl), '✅ 여유 %d' % (len(free) - len(syl))
               if len(syl) <= len(free) else '★부족 %d' % (len(syl) - len(free))))
    except ImportError:
        pass
