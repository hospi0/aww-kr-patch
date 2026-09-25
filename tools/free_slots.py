# -*- coding: utf-8 -*-
"""ASC16CG(16×16 폰트)에서 **아무 텍스트도 쓰지 않는 글리프 슬롯**을 고른다.

왜 필요한가 — 900 천장(맵이 0x1E000에 있어서 폰트가 그 앞까지만 자란다)을 뚫으려면
폰트를 다른 128KB 블록으로 옮겨야 하는데, GAME이 블록1·2·3을 모두 쓰기 때문에
안전한 목적지가 없다(세션9 조사). 그래서 **성장 대신 재사용**한다: 디스크 어디에서도
안 쓰이는 기존 슬롯을 한글로 재정의하면 폰트 크기·VRAM 배치가 그대로다.

안전 규칙(과대탐지 = 안전):
  1) 엄격 검출기(findtext2, 가나≥2·밀도≥0.55·0xFFFF 종료)로 잡힌 인덱스는 전부 '사용중'.
  2) 여기에 더해 **느슨한 검출기**(길이≥2 런, 가나·종료자 요구 없음)로도 검사한다.
     세션8-a의 `中止終了中止占領墜落`처럼 구분자 없는 고정폭 배열을 놓치지 않기 위해서다.
  3) 다른 폰트로 렌더되는 모듈(INTERM·GMSEL(DT)·SAKUSEN·MUSEUM **모듈 파일 자체**)만
     소비자에서 뺀다. 그 모듈들이 읽는 데이터 파일은 소속을 모르므로 **전부 소비자로 친다**.
     ⇒ 실제보다 훨씬 많은 슬롯을 '사용중'으로 판정한다(보수적).

결과는 인덱스 오름차순. 빌더는 필요한 개수만 앞에서부터 가져다 쓴다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import findtext2 as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'work', 'free_slots.json')

MAXG = 824
# 다른 폰트를 자기 화면에 올리는 모듈 파일들(이 파일 안의 텍스트는 ASC16CG로 안 그려진다)
OTHER_FONT = ('/INTERM', '/GMSEL', '/SAKUSEN', '/MUSEUM')


DENSE_WIN = 11        # 앞뒤 5워드 + 자기 자신
DENSE_MIN = 8         # 그중 유효 글리프가 이만큼이면 '텍스트 영역'으로 본다


def dense_used(d, out):
    """**밀도 기반 사용 판정** — 종료자도 가나도 요구하지 않는다.

    ★이게 핵심이다. findtext2(가나≥2·0xFFFF 종료)는 GMDT/KEKKA의 **미션명·부대명**처럼
      공백 패딩 고정폭·한자만 있는 필드를 통째로 놓친다(세션9에서 63칸 중 50칸이
      「イタリア半島の激闘」「バルカン侵攻作戦」류로 실제 사용중임이 드러났다).
      대신 '주변 11워드 중 8개 이상이 유효 글리프'면 그 자리를 텍스트로 본다.
      바이너리 오탐은 자유 슬롯을 줄일 뿐이라 안전한 방향이다.
    """
    n = len(d) // 2
    if n < DENSE_WIN:
        return
    vals = [(d[2 * k] << 8) | d[2 * k + 1] for k in range(n)]
    ok = [1 if 1 <= v <= MAXG else 0 for v in vals]
    half = DENSE_WIN // 2
    run = sum(ok[:DENSE_WIN])
    for k in range(half, n - half):
        if run >= DENSE_MIN and ok[k]:
            out.add(vals[k])
        nxt = k + half + 1
        if nxt < n:
            run += ok[nxt] - ok[k - half]


def loose_runs(d):
    """길이 2 이상인 '유효 인덱스 연속' 구간 — 종료자·가나를 요구하지 않는다."""
    n = len(d) // 2
    out, start = [], None
    for i in range(n):
        v = (d[2 * i] << 8) | d[2 * i + 1]
        if 1 <= v <= MAXG:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= 2:
                out.append((start, i))
            start = None
    if start is not None and n - start >= 2:
        out.append((start, n))
    return out


def scan(window=1024, verbose=True):
    """window = 엄격 레코드 주변 몇 바이트까지를 '텍스트 풀'로 보고 느슨 검사할지.

    ⚠️느슨 검사를 파일 전체에 돌리면 유닛 스탯 같은 바이너리가 824종을 다 찍어
    아무 슬롯도 안 남는다(실측). 진짜 렌더 텍스트는 **풀에 뭉쳐** 있으므로
    엄격 히트 주변만 본다 — 세션8-a가 놓친 배열도 라벨 풀 바로 옆에 있었다.
    """
    strict, loose = set(), set()
    nfile = 0
    with open(TRACK1, 'rb') as f:
        for p, lba, size in files():
            if size < 32 or size > 3_000_000:
                continue
            if any(p.startswith(x) for x in OTHER_FONT):
                continue
            d = read_range(f, lba, size)
            nfile += 1
            for off, ln, _dens in F.records(d):
                for i in range(ln):
                    v = (d[off + 2 * i] << 8) | d[off + 2 * i + 1]
                    if 1 <= v <= MAXG:
                        strict.add(v)
            dense_used(d, loose)
    free = [i for i in range(1, MAXG + 1) if i not in strict and i not in loose]
    if verbose:
        print('소비자 파일 %d개 — 엄격 사용 %d / 느슨 사용 %d / **미사용 %d칸**'
              % (nfile, len(strict), len(loose), len(free)))
    return free, strict, loose


WINDOWS = (256, 128, 64, 32, 16)


def rank(verbose=True):
    """엄격 미사용 슬롯을 **위험도 낮은 순**으로 정렬해 돌려준다.

    느슨 검출기는 창(window)을 넓힐수록 노이즈가 커져 824종을 다 찍는다(실측).
    그래서 창 크기를 여러 개 돌려 **어느 창에서 처음 걸리는지**를 위험 점수로 쓴다.
      - 어느 창에서도 안 걸림      → 가장 안전(점수 0)
      - 넓은 창에서만 걸림(256)    → 그다음
      - 좁은 창에서도 걸림(16)     → 가장 위험(텍스트 풀 바로 옆에 그 인덱스가 있다)
    같은 점수 안에서는 인덱스 오름차순(결정적).
    """
    free0, strict, _ = scan(window=0, verbose=False)
    flagged = {}
    for w in WINDOWS:                       # 넓은 창부터 → 좁은 창일수록 점수가 커진다
        _, _, loose = scan(window=w, verbose=False)
        for i in free0:
            if i in loose:
                flagged[i] = flagged.get(i, 0) + 1
    ranked = sorted(free0, key=lambda i: (flagged.get(i, 0), i))
    if verbose:
        print('엄격 사용 %d / 엄격 미사용 %d칸 — 위험점수 분포 %s'
              % (len(strict), len(free0),
                 {s: sum(1 for i in free0 if flagged.get(i, 0) == s)
                  for s in range(len(WINDOWS) + 1)}))
    return ranked, flagged


def load(refresh=False):
    """캐시된 자유 슬롯 목록(스캔이 느려 한 번만 돌린다)."""
    if not refresh and os.path.exists(CACHE):
        with open(CACHE, encoding='utf-8') as r:
            return json.load(r)['ranked']
    ranked, flagged = rank()
    with open(CACHE, 'w', encoding='utf-8') as w:
        json.dump({'ranked': ranked, 'risk': {str(k): v for k, v in flagged.items()}}, w)
    return ranked


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ranked = load(refresh='--refresh' in sys.argv)
    risk = json.load(open(CACHE, encoding='utf-8'))['risk']
    cm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in cm.items()}
    print('자유 슬롯 %d칸 (안전한 순)' % len(ranked))
    print(' '.join('%d:%s%s' % (i, cm.get(i, '?'), '!' * int(risk.get(str(i), 0)))
                   for i in ranked))
