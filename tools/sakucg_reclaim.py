# -*- coding: utf-8 -*-
"""SAKUCG **원본 글리프 슬롯 회수** — 세션15.

왜 필요한가: 미션 타이틀(66)·편성명(85) 표는 **3벌 사본**(GMDT·KEKKA·SAKUSEN)인데
  GMDT/KEKKA 는 ASC16CG(한글 슬롯 있음), SAKUSEN 만 SAKUCG(한글 0개)를 쓴다.
  세션10·11이 라틴으로 간 이유가 이것 — 라틴은 세 폰트에서 인덱스가 같다.
  ⇒ 사본마다 **그 모듈 폰트의 슬롯으로 따로 인코딩**하면 한글이 된다.

★ASC16CG 보다 훨씬 확실하다 — **SAKUCG 소비자는 `/SAKUSEN` 한 파일뿐**이다
  (세션8-a 화면별 폰트 역산: SAKUSEN=SAKUCG). 완전 열거가 가능하다.
  (ASC16CG 는 GAME·GMDT·KEKKA·UPK·미션별 UCG 에 흩어져 있어 추정이었다.)

판정 규칙은 asc16_reclaim 과 같다(과대탐지 = 안전한 방향):
  ① 엄격 검출기(findtext2)가 잡은 레코드의 인덱스 = 사용중
  ② 그 주변 ±WINDOW 안에서만 밀도 판정 추가 — 구분자 없는 고정폭 배열을 놓치지 않으려고
  ⚠️파일 전체 밀도 판정은 금지(유닛 스탯 바이너리가 전 인덱스를 다 찍는다)

기준 ISO = **F: 패치본**(유닛명 로마자화 등 현재 상태를 반영해야 한다).

사용: python tools/sakucg_reclaim.py           census → work/sakucg_reclaim.json
      python tools/sakucg_reclaim.py --show    캐시만 보기
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isoread
import scan_files
import findtext2 as F
from isoread import read_range
import charmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'work', 'sakucg_reclaim.json')
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

MAXG = 1016          # SAKUCG 1017글리프
WINDOW = 512
DENSE_WIN = 11
DENSE_MIN = 8
TARGET = '/SAKUSEN'


def census(path):
    isoread.TRACK1 = path
    scan_files.TRACK1 = path
    used = set()
    with open(path, 'rb') as f:
        for p, lba, size in scan_files.files():
            if p != TARGET:
                continue
            d = read_range(f, lba, size)
            n = len(d) // 2
            v = [(d[2 * k] << 8) | d[2 * k + 1] for k in range(n)]
            ok = [1 if 1 <= x <= MAXG else 0 for x in v]
            zones = []
            for off, ln, _ in F.records(d):
                i0 = off // 2
                for k in range(i0, min(n, i0 + ln)):
                    if ok[k]:
                        used.add(v[k])
                zones.append((max(0, i0 - WINDOW), min(n, i0 + ln + WINDOW)))
            half = DENSE_WIN // 2
            for a, b in zones:
                for k in range(a, b):
                    if not ok[k]:
                        continue
                    lo, hi = max(0, k - half), min(n, k + half + 1)
                    if sum(ok[lo:hi]) >= DENSE_MIN:
                        used.add(v[k])
    return used


def load(refresh=False):
    """회수 가능 슬롯(오름차순). 가나·한자만 — 라틴·숫자·로마숫자·기호는 남긴다."""
    if not refresh and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding='utf-8'))['free']
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(isoread.TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    orig = isoread.TRACK1
    used = census(dst)
    isoread.TRACK1 = orig
    scan_files.TRACK1 = orig

    fm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'),
                        encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in fm.items()}

    def kana_or_kanji(i):
        ch = cm.get(i) or charmap.CHARS.get(i)
        if ch is None or len(ch) != 1:
            return False
        o = ord(ch)
        return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF

    free = sorted(i for i in range(1, MAXG + 1)
                  if i not in used and kana_or_kanji(i))
    json.dump({'free': free, 'used': len(used)},
              open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    return free


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    free = load(refresh='--show' not in sys.argv)
    print('SAKUCG 회수 가능 %d칸 (전체 %d글리프)' % (len(free), MAXG + 1))
    print('앞 40:', free[:40])
