# -*- coding: utf-8 -*-
"""「〈이름〉配下」 → 「〈이름〉휘하」 (세션8).

발견 경위. 전투 유닛 패널의 `配下`가 16×16 폰트 텍스트인지 그래픽인지 정적으로 안 갈렸다
(디스크 전체에 독립 「配下」 문자열 0개 = 그래픽 신호 / 픽셀은 폰트 글리프와 일치 = 텍스트 신호).
**글리프 막기 이분실험**(`exp_haika.py`, 配·下 비트맵을 디스크 전수검색해 사본 14곳 전부 표식으로
치환)으로 실기 확인 → **다른 곳은 전부 표식, 그 패널만 한자 그대로** ⇒ 16×16 폰트가 아님.

★★진짜 정체 = **소형 8×8 폰트의 글리프 172·173·174.**
   172 = 配의 왼쪽 절반, 173 = 配의 오른쪽 절반, 174 = 下.  즉 `配下`는 8×8 셀 **3칸**짜리다.
   VDP2 레지스터에서 화면이 352×224임을 확인하고 화면상 글자 크기를 역산해보니 문자당 ~8px이라
   16×16일 수 없었던 게 결정적 단서였다.
   ⚠️세션4가 「176~228 = 유닛 아이콘 그래픽」이라 분류하면서 **바로 앞 172~175를 같이 그래픽으로
     묶어** 넘겼고, 세션5는 UI풀에서 이 바이트를 보고도 「레이아웃 마커 `<ac><ad><ae>`」로 적어뒀다.
     ⇒ **이미 추출해 둔 필드를 「의미 불명」으로 방치하면 나중에 미해결 과제로 되돌아온다.**

저장 위치 = GMDT UI풀 `0x24809`, `0x24814` (각 3바이트). 앞의 `ヒナミ`/`セイミヤ`는
**런타임에 로스터 이름으로 덮이는 자리표시자**다(그래서 화면엔 `Reichnau`가 뜬다).
`smalltext.tsv` 전체 2011필드 중 글리프 172/173을 쓰는 건 이 둘뿐 — 전수 확인함.

★★1차 시도(글리프 172만 휘로 + UI풀 필드를 `AC 76 00`으로)는 **반만 먹었다** — 실기에서
  첫 칸만 「휘」로 바뀌고 뒤 두 칸은 `配`오른쪽+`下` 그대로였다. ⇒ **화면이 읽는 문자열은 UI풀이
  아니다**(사본은 GMDT 2곳뿐이고 둘 다 고쳤는데도 안 바뀜) = **코드가 글리프 인덱스 172·173·174를
  직접 찍는다**. ★교훈: 폰트 변경은 먹었는데 텍스트만 안 바뀌면 = **그 문자열은 데이터가 아니라 코드다**.
  ⇒ 문자열을 찾을 필요 없이 **글리프 3칸을 전부 다시 그리면** 출처가 어디든 화면이 맞는다.

패치 내용 (글리프만 교체 — 텍스트는 한 바이트도 안 건드린다):
  · 172 → 「휘」 (손으로 그린 리터럴 비트맵, 안 C)
    ★가로는 7픽셀만 쓴다(col7=자간). ㅣ는 col6, ㅎ·ㅜ의 가로획은 5폭으로 넓혀 3폭 ㅇ과 구분.
  · 173 → 「하」 (기존 슬롯 118의 글리프를 그대로 복사)
  · 174 → 공백
  ⇒ **신규 음절 0 · 예산 소모 0 · 폰트 슬롯 추가 0 · 텍스트 변경 0.**
  글리프 172~174는 `smalltext.tsv` 2011필드 전수조사에서 이 라벨 외에 쓰이는 곳이 없다.

폰트는 **GMDT만** 건드린다. 같은 UI풀의 `GND:` 라벨이 세션5 실기에서 GMDT 확장 폰트로 정상
렌더된 것이 확인됐으므로 이 풀을 그리는 폰트 = GMDT로 확정. 172는 기본 범위(0~228)라
확장 슬롯 리스크도 없다.

빌드: python tools/build_haika.py           드라이런
      python tools/build_haika.py --write   F: ISO 제자리 기록
      python tools/build_haika.py --revert  원상복구
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
import build_smalltext as B
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
EXTRACT = os.path.join(ROOT, 'work', 'extract')

FONT_FO = 0x28ef8            # GMDT 소형폰트
G_HUI = 172                  # 配 왼쪽 절반 자리 → 휘
FIELDS = [0x24809, 0x24814]  # UI풀의 「配下」 필드 (각 3B)
OLD = bytes([172, 173, 174])

# 안 C — ㅣ=col6, ㅎ/ㅜ 가로획 5폭, ㅇ 3폭. col7은 자간으로 비운다.
HUI = [
    '..#...#.',
    '#####.#.',
    '......#.',
    '.###..#.',
    '#...#.#.',
    '.###..#.',
    '#####.#.',
    '..#...#.',
]


def pack8(rows):
    """8x8 값행렬 -> 소형폰트 32바이트 (4bpp, ★상위 니블 = 왼쪽)."""
    out = bytearray(32)
    for y in range(8):
        for x in range(4):
            l = 15 if rows[y][x * 2] == '#' else 0
            r = 15 if rows[y][x * 2 + 1] == '#' else 0
            out[y * 4 + x] = (l << 4) | r
    return bytes(out)


def plan():
    """글리프 172·173·174 를 휘 / 하 / 공백 으로. 텍스트는 안 건드린다."""
    from hangul8comp import glyph8, to_tile
    _, rows = B.load_tsv()
    slot, _ = B.assign_slots(rows)
    if '하' not in slot:
        raise SystemExit("'하' 슬롯 없음 — 배정표가 바뀌었다")
    orig = open(os.path.join(EXTRACT, 'GMDT'), 'rb').read()

    new = {172: pack8(HUI),                    # 휘 (손으로 그림)
           173: to_tile(glyph8('하')),          # 하 (기존 조합기 — 슬롯 118과 동일 모양)
           174: bytes(32)}                     # 공백
    p = []
    for gi in (172, 173, 174):
        off = FONT_FO + gi * 32
        p.append(('glyph%d' % gi, off, orig[off:off + 32], new[gi]))
    return p, slot


def render(g32):
    out = []
    for y in range(8):
        r = ''
        for x in range(4):
            v = g32[y * 4 + x]
            r += ('#' if v >> 4 else '.') + ('#' if v & 0xF else '.')
        out.append(r)
    return out


def rw(dst, p, revert=False):
    import ecc
    hits, _, _, _ = find_dirrec(open(dst, 'rb'), 'GMDT')
    if len(hits) != 1:
        raise SystemExit('GMDT 디렉터리 %d개' % len(hits))
    lba = hits[0][1]
    print('GMDT lba=%d' % lba)
    touched = set()
    with open(dst, 'r+b') as w:
        for name, off, old, new in p:
            src, dstb = (new, old) if revert else (old, new)
            for k in range(len(old)):
                lo = off + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                if w.read(1) != src[k:k + 1]:
                    raise SystemExit('%s @0x%x 대조 실패 (%s)'
                                     % (name, off, '패치본 아님' if revert else '이미 패치됨?'))
                w.seek(pos)
                w.write(dstb[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    return lba


def verify_iso(dst, p, lba, revert):
    with open(dst, 'rb') as r:
        for name, off, old, new in p:
            want = old if revert else new
            got = bytearray()
            for k in range(len(want)):
                lo = off + k
                r.seek((lba + lo // USER) * RAW + HDR + (lo % USER))
                got += r.read(1)
            if bytes(got) != want:
                raise SystemExit('되읽기 불일치 %s' % name)
    print('독립 되읽기 통과.')


def main():
    p, slot = plan()
    print('\n글리프 172 (配 왼쪽) -> 휘')
    for a, b in zip(render(p[0][2]), render(p[0][3])):
        print('   %s   ->   %s' % (a, b))
    print('\n패치 항목 %d개' % len(p))
    for name, off, old, new in p:
        print('   %-14s @0x%06x  %s -> %s' % (name, off, old.hex(' ')[:23], new.hex(' ')[:23]))

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    rev = '--revert' in sys.argv
    if not rev and '--write' not in sys.argv:
        print('\n드라이런 — 미기록 (--write / --revert).')
        return
    lba = rw(dst, p, revert=rev)
    verify_iso(dst, p, lba, rev)
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
