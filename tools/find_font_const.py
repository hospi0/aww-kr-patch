# -*- coding: utf-8 -*-
"""ASC16CG 업로드 상수 탐색 (세션8) — SH-2 리터럴 역추적.

배경. 세션3 실기로 **ASC16CG 성장 천장 = 정확히 900글리프**가 확정됐다(899=마지막 한글,
900=첫 깨짐). 900은 섹터경계도 헥사도 아닌 딱 떨어지는 10진수라 **로더에 박힌 상수**가 유력하다.
세션3은 "상수 나이브 검색은 노이즈로 실패 → 디스어셈 필요"로 접었는데, 그건 **세션4의
리터럴 역추적 기법을 만들기 전**이었다. 소형폰트를 229→240으로 올린 게 바로 그 기법이다.

★핵심 = 값이 어디 **있나**를 찾지 말고, 그 값을 실제로 **로드하는 명령**이 있나를 찾는다.
  SH-2는 16/32비트 상수를 리터럴 풀에 두고 PC 상대로 읽는다:
      MOV.W @(disp,PC),Rn = 0x9nDD  → target = addr + 4 + disp*2      (부호없는 16비트)
      MOV.L @(disp,PC),Rn = 0xDnDD  → target = ((addr+4) & ~3) + disp*4 (32비트)
  이러면 "우연히 그 바이트가 있는 곳"은 전부 걸러진다.

찾는 값(소형폰트 선례상 **롱워드 개수**가 인자였다 — R6=0x0728=1832=7328/4):
    825글리프 = 105,600 B = 26,400 롱워드 = 0x6720   ← 현재 업로드량 후보
    900글리프 = 115,200 B = 28,800 롱워드 = 0x7080   ← 천장 후보
  바이트 크기(0x19C80 / 0x1C200)와 글리프 수(825=0x339 / 900=0x384)도 같이 본다.

사용: python tools/find_font_const.py
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT = os.path.join(ROOT, 'work', 'extract')

WANT = {
    825: '825글리프', 900: '900글리프',
    26400: '825글리프 롱워드수(0x6720)', 28800: '900글리프 롱워드수(0x7080)',
    105600: '825글리프 바이트(0x19C80)', 115200: '900글리프 바이트(0x1C200)',
    52800: '825글리프 워드수', 57600: '900글리프 워드수',
}


def scan(buf):
    """(주소, 명령, 리터럴주소, 값, 폭) 목록 — 리터럴 값이 WANT에 있는 것만."""
    out = []
    n = len(buf) - 1
    for a in range(0, n, 2):
        op = (buf[a] << 8) | buf[a + 1]
        if (op & 0xF000) == 0x9000:                      # MOV.W @(disp,PC),Rn
            disp = op & 0xFF
            t = a + 4 + disp * 2
            if t + 2 <= len(buf):
                v = (buf[t] << 8) | buf[t + 1]
                if v in WANT:
                    out.append((a, 'MOV.W R%d' % ((op >> 8) & 0xF), t, v, 16))
        elif (op & 0xF000) == 0xD000:                    # MOV.L @(disp,PC),Rn
            disp = op & 0xFF
            t = ((a + 4) & ~3) + disp * 4
            if t + 4 <= len(buf):
                v = struct.unpack_from('>I', buf, t)[0]
                if v in WANT:
                    out.append((a, 'MOV.L R%d' % ((op >> 8) & 0xF), t, v, 32))
    return out


def main():
    files = [f for f in sorted(os.listdir(EXTRACT))
             if not f.endswith('.png') and not os.path.isdir(os.path.join(EXTRACT, f))]
    total = 0
    for f in files:
        buf = open(os.path.join(EXTRACT, f), 'rb').read()
        hits = scan(buf)
        if not hits:
            continue
        print('=== %s (%d B)' % (f, len(buf)))
        for a, ins, t, v, w in hits:
            print('    @0x%06x  %-9s <- 리터럴@0x%06x = %-7d  (%s)'
                  % (a, ins, t, v, WANT[v]))
        total += len(hits)
    print('\n총 %d건' % total)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
