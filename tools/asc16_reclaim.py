# -*- coding: utf-8 -*-
"""ASC16CG **원본 글리프 슬롯 회수** — 세션14.

무엇을 하나
  ASC16CG(825글리프)의 인덱스 1..824 중 **패치 후에도 일본어로 남는 텍스트가
  한 번도 참조하지 않는** 슬롯을 census한다. 그 슬롯은 한글로 재정의해도
  화면이 안 깨지므로, 폰트를 키우지 않고(=VRAM 천장 900 그대로) 예산을 번다.

왜 free_slots.py를 안 쓰나 — 그 도구에 버그 2개가 있다(세션14 발견):
  ① 제외 목록(OTHER_FONT)에 **`/SCHOOL`이 빠져 있다.** SCHOOL은 자체 폰트 사본
     (0x1C574, ASCMSCG 계열)을 올리므로 ASC16CG 소비자가 아닌데, 사관학교 대사
     (`存在する`·`訓練`·`格納`·`待機状態`…)가 전부 '사용중'으로 잡혀 있었다.
  ② `scan(window=...)` 의 window 인자가 **함수 안에서 전혀 안 쓰인다.** 그래서
     `rank()` 가 창 크기를 바꿔 가며 매기는 위험 점수가 전부 같은 값이 된다.
  ⇒ 이 파일이 그 둘을 고쳐 다시 구현한 것이다. free_slots.py 결과는 쓰지 말 것.

판정 규칙 (과대탐지 = 안전한 방향)
  ① **엄격**(findtext2: 가나≥2·밀도·0xFFFF 종료)로 잡힌 레코드의 인덱스 = 사용중.
  ② 그 레코드 **주변 ±512워드 안**에서만 밀도 판정(11워드 창에 유효 글리프 ≥8)을
     추가로 돌린다. 구분자 없는 고정폭 배열(`中止終了中止占領墜落`)이나 미션별
     한자풀(`/M04/UCG`)처럼 엄격 검출기가 놓치는 진짜 텍스트를 잡기 위해서다.
     ⚠️밀도 문턱을 11/11(완전연속)로 올리면 안 된다 — 레코드 사이 `0xFFFF`
       구분자가 연속성을 끊어서 `戦略的勝利`(KEKKA)·`合計得点` 같은 **진짜 텍스트를
       자유로 오판**한다(세션14 실측: 62칸 → 100칸으로 부풀었다).
  ③ 파일 전체에 밀도 판정을 돌리면 유닛 스탯 같은 바이너리가 824종을 다 찍어
     한 칸도 안 남는다(free_slots.py 주석의 실측 그대로). 반드시 ①의 주변만.

기준 ISO = **F: 패치본**이다. 유닛명(build_unit16/upk)·미션명(build_missions16)이
이미 로마자화돼 그만큼 한자 참조가 줄어든 상태를 반영해야 하기 때문이다.
(원본 TRACK1로 재면 세션9의 「자유 2칸」 판정이 그대로 재현된다.)

사용:  python tools/asc16_reclaim.py            census 후 work/asc16_reclaim.json 갱신
       python tools/asc16_reclaim.py --show     캐시 내용만 보기
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isoread
import scan_files
from isoread import read_range
import findtext2 as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'work', 'asc16_reclaim.json')
FONTMAP = os.path.join(ROOT, 'work', 'fontmaps.json')
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

MAXG = 824
# 자기 화면에 **다른 폰트**를 올리는 모듈 = ASC16CG 소비자가 아니다.
#   ★/SCHOOL 포함이 세션14의 수정 지점(free_slots.py엔 빠져 있었다).
OTHER_FONT = ('/INTERM', '/GMSEL', '/SAKUSEN', '/MUSEUM', '/SCHOOL')
DENSE_WIN, DENSE_MIN, WINDOW = 11, 8, 512

# ── 수동 제외 (verify_reclaim.py가 실제로 잡아낸 위반) ───────────────────────
#   census는 「엄격 레코드 주변 밀도」로 판정하므로, 주변이 성긴(널·범위밖이 섞인)
#   자리에 홀로 박힌 글리프를 놓친다. 아래 둘이 실제로 그랬다:
#     757 `！` — GMDT 0x024C1E `LEVEL UP！！` (우리가 안 건드리는 잔존 텍스트)
#     724 `項` — GMDT 0x025D36 `項目制限`   (설정화면에서 일본어로 남는 항목)
#   ⇒ **verify_reclaim.py를 --write 전에 반드시 돌려서** 이 목록을 갱신할 것.
BLOCK = {757, 724}


def census(path):
    """path ISO에서 ASC16CG 인덱스 사용 집합을 구한다."""
    isoread.TRACK1 = path
    scan_files.TRACK1 = path
    used = set()
    with open(path, 'rb') as f:
        for p, lba, size in scan_files.files():
            if size < 32 or size > 3_000_000:
                continue
            if any(p.startswith(x) for x in OTHER_FONT):
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
    """회수 가능 슬롯 인덱스 목록(오름차순). 캐시 = work/asc16_reclaim.json."""
    if not refresh and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding='utf-8'))['free']
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(isoread.TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    orig = isoread.TRACK1
    used = census(dst)
    isoread.TRACK1 = orig                      # 전역 되돌림(다른 도구 오염 방지)
    scan_files.TRACK1 = orig
    free = sorted(set(range(1, MAXG + 1)) - used - BLOCK)
    json.dump({'free': free, 'used': len(used), 'blocked': sorted(BLOCK)},
              open(CACHE, 'w', encoding='utf-8'))
    return free


def main():
    free = load(refresh='--show' not in sys.argv)
    cm = json.load(open(FONTMAP, encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in cm.items()}
    print('★ASC16CG 회수 가능 슬롯 %d칸 (원본 1..%d 중)' % (len(free), MAXG))
    print('  공급 = 확장 75(825~899) + 회수 %d = %d칸' % (len(free), 75 + len(free)))
    print()
    for i in range(0, len(free), 10):
        print('   ' + '  '.join('%3d:%s' % (g, cm.get(g, '?')) for g in free[i:i + 10]))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
