# -*- coding: utf-8 -*-
"""전투 HUD 턴 카운터의 「第」 제거 (세션11).

증상: HUD 상단 "第1ターン"(→우리 번역 "第1턴")의 `第`가 남아 있다.
분석: `第`는 그래픽도, 데이터 문자열도 아니고 **코드가 그리는 폰트 글리프**다.
  GAME 0x012dd8 `mov.w @(0x012eb6),r4`가 글리프 인덱스 0x023c(第)를 로드해
  접두 글리프로 그린다(0x012dde `mov r4,r11` → 0x012e12 `mov r11,r5` → jsr 그리기).
  이 리터럴을 로드하는 코드는 GAME 전체에서 이 한 곳뿐(SH-2 리터럴 역추적).

패치: 리터럴 `0x012eb6` : `0x023c`(第) → `0x0000`(공백, ASC16CG glyph0 = ' ').
  ★코드 주입이 아니라 **상수 1워드 변경**. 정적 검증으로 안전 확정:
    루틴은 `cmp/eq r4,r3`(r3=11)로 분기하는데 第(0x23c)도 0도 11이 아니라
    **분기 결과가 동일** → 숫자 렌더 로직 불변, 접두 글리프만 第→공백.
  결과: "第1턴" → " 1턴"(第 자리에 공백 1칸, 사용자 승인).

빌드: python tools/build_hud_dai.py            드라이런
      python tools/build_hud_dai.py --write    F: ISO 기록
      python tools/build_hud_dai.py --revert   원상복구
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
OFF = 0x012eb6            # GAME 모듈 내 파일 오프셋 (리터럴 풀)
OLD = 0x023c             # 第 글리프 인덱스
NEW = 0x0000             # 공백 글리프


def sector_of(lba, off):
    return lba + off // USER, off % USER


def main():
    revert = '--revert' in sys.argv
    write = '--write' in sys.argv or revert
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    # 계획은 원본에서 — GAME 모듈 위치 + 리터럴이 정말 0x023c인지 확인
    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'GAME')
        if len(hits) != 1:
            raise SystemExit('GAME 디렉터리 레코드 %d개' % len(hits))
        _, lba, size, _ = hits[0]
        sec, pos = sector_of(lba, OFF)
        f.seek(sec * RAW + HDR + pos)
        cur = struct.unpack('>H', f.read(2))[0]
    if cur != OLD:
        raise SystemExit('원본 리터럴 0x%04x != 기대 0x%04x — 위치 재확인' % (cur, OLD))
    print('GAME lba=%d, 리터럴 0x%06x = 0x%04x(第) 확인' % (lba, OFF, cur))

    want = OLD if revert else NEW
    src = NEW if revert else OLD
    print('%s: 0x%06x  0x%04x → 0x%04x' %
          ('원상복구' if revert else '패치', OFF, src, want))
    if not write:
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return

    sec, pos = sector_of(lba, OFF)
    with open(dst, 'r+b') as w:
        w.seek(sec * RAW + HDR + pos)
        got = struct.unpack('>H', w.read(2))[0]
        if got != src:
            raise SystemExit('대상 현재값 0x%04x != 예상 0x%04x — %s'
                             % (got, src, '패치본 아님' if revert else '이미 패치됨?'))
        w.seek(sec * RAW + HDR + pos)
        w.write(struct.pack('>H', want))
        # EDC/ECC
        w.seek(sec * RAW)
        raw = w.read(RAW)
        w.seek(sec * RAW)
        w.write(ecc.fix_sector(raw))
    # 독립 되읽기
    with open(dst, 'rb') as r:
        r.seek(sec * RAW + HDR + pos)
        chk = struct.unpack('>H', r.read(2))[0]
        r.seek(sec * RAW)
        raw = r.read(RAW)
    if chk != want:
        raise SystemExit('되읽기 불일치 0x%04x' % chk)
    if ecc.fix_sector(raw) != raw:
        raise SystemExit('EDC/ECC 무효')
    print('완료·독립검증 통과 (되읽기 0x%04x, EDC/ECC 유효) ->' % chk, dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
