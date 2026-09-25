# -*- coding: utf-8 -*-
"""이름입력 가나 팔레트 제거 — /GMSELDT (세션15-g).

★사용자 결정: 이름입력은 전부 영문으로 간다 ⇒ 가나 페이지를 없앤다.

★★발견 경위 = 1차 빌드 실패. `/SCHOOL` 팔레트만 비웠더니 실기에서 가나가 그대로 남았다.
  `アイウエオ` 글리프 인덱스 런을 전 파일 검색하니 **사본이 4벌**이었다:
      /GMSELDT 0x012866  ← ★실제 이름입력 화면(8행×8, 스크린샷과 셀 배치 일치)
      /SCHOOL  0x003ef8  ← 사관학교 캐릭터 작성(페이지가 아니라 평면 문자표)
      /MUSEUM  0x05f454 / /SAKUSEN 0x02f8ec  ← 42칸 탁음 변환표(표시용 아님, 손대지 않는다)
  ⇒ 교훈: **팔레트·문자표도 「같은 이름 여러 사본」 함정을 탄다.**

구조(/GMSELDT): `0xFFFF` 로 구분된 문자열 풀. 네 페이지 모두 **64칸으로 동일**하다.
    0x0127E4 히라가나 / 0x012866 가타카나 / 0x0128E8 대문자 / 0x01296A 소문자
    0x0129EC `A`  0x0129F0 `a`  0x0129F4 `ア`  0x0129F8 `あ`  0x0129FC `終了`  ← 모드 버튼 줄

이 빌더가 하는 일:
  ① 가타카나 페이지 ← **대문자 페이지 복사**, 히라가나 페이지 ← **소문자 페이지 복사**
  ② 모드 버튼 `ア`·`あ` 를 0x0000 으로

★★그냥 비우지 않고 **복사**하는 이유: 게임이 **가타카나 페이지에서 시작**한다(실기 확인).
  비워두면 첫 화면이 통째로 빈칸이라 허전하다. 알파벳을 복사해 두면 시작 화면이 A~Z 가 되고,
  `ア`·`あ` 버튼을 눌러도 같은 알파벳이 나와 **아무 일도 안 일어난다** — 커서를 막는 것과
  같은 효과를 **코드 한 줄 없이** 낸다. (팔레트 칸이 곧 글리프 인덱스이고 이름 버퍼도
  글리프 인덱스로 저장되므로, 화면에 보이는 글자가 그대로 입력된다.)

⚠️커서가 그 버튼 위에 **멈추는 것 자체**는 여전히 못 막는다 — 버튼 개수는 데이터가 아니라
  코드의 상수/좌표표다(풀에는 개수 필드가 없다). 다만 위 복사로 실질 피해가 사라진다.

빌드: python tools/build_kana_palette.py            드라이런
      python tools/build_kana_palette.py --write     F: ISO 기록
      python tools/build_kana_palette.py --resync    재기록(대조 생략)
      python tools/build_kana_palette.py --revert    원상복구
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import charmap
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
PAGE = 64
KANA_LO, KANA_HI = 0x3040, 0x30FF
EXTRA = 'ー゛゜・-？上図'      # 표에서 가나 페이지에 섞여 있는 기호(上図 = ゛゜ 오독)

# (파일, 대상, 원본|None, 칸수, 설명) — 원본이 None 이면 0x0000 으로 비운다
PLAN = [
    ('GMSELDT', 0x012866, 0x0128E8, PAGE, '가타카나 ← 대문자'),
    ('GMSELDT', 0x0127E4, 0x01296A, PAGE, '히라가나 ← 소문자'),
    ('GMSELDT', 0x0129F4, None, 1, '모드버튼 ア 제거'),
    ('GMSELDT', 0x0129F8, None, 1, '모드버튼 あ 제거'),
]


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def check(d, off, n, t, kana=True):
    """관문 — 덮어쓸 구간은 **가나만**, 복사 원본은 **영숫자만** 이어야 한다.
    페이지 범위를 한 칸이라도 잘못 잡으면 옆 페이지를 파괴하므로 양쪽 다 검사한다."""
    for i in range(off, off + n * 2, 2):
        v = struct.unpack_from('>H', d, i)[0]
        if v == 0:
            continue
        ch = t.get(v)
        if ch is None or len(ch) != 1:
            raise SystemExit('★0x%06x 셀%d 값%d 미지 글리프' % (off, (i - off) // 2, v))
        ok = (KANA_LO <= ord(ch) <= KANA_HI or ch in EXTRA) if kana \
            else ((ord(ch) < 0x80 and ch.isalnum()) or ch == '-')
        if not ok:
            raise SystemExit('★0x%06x 셀%d %r 이 %s 가 아니다 — 범위 오지정'
                             % (off, (i - off) // 2, ch, '가나' if kana else '영숫자'))


def show(d, off, n, t):
    out = ''
    for k in range(n):
        v = struct.unpack_from('>H', d, off + k * 2)[0]
        out += '␀' if v == 0 else t.get(v, '?')
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync

    t = dict(charmap.CHARS)
    src = {}
    with open(TRACK1, 'rb') as f:
        for name in sorted({p[0] for p in PLAN}):
            hits, _, _, _ = find_dirrec(f, name)
            _, lba, size, _ = hits[0]
            src[name] = (lba, size, read_file(f, lba, size))

    plans = []
    for name, off, frm, n, desc in PLAN:
        lba, size, d = src[name]
        check(d, off, n, t, kana=True)
        if frm is None:
            new = b'\x00' * (n * 2)
        else:
            check(d, frm, n, t, kana=False)
            new = d[frm:frm + n * 2]
        old = d[off:off + n * 2]
        print('/%-8s 0x%06x %3d칸  %-16s' % (name, off, n, desc))
        print('     전: %s' % show(d, off, n, t))
        print('     후: %s' % (show(new + b'\x00' * 2, 0, n, t) if frm else '␀' * n))
        plans.append((name, lba, off, old, old if revert else new, desc))

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for name, lba, off, old, new, desc in plans:
            for k in range(len(new)):
                lo = off + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                if not (resync or revert) and w.read(1) != old[k:k + 1]:
                    raise SystemExit('%s @0x%x 대조 실패 — 이미 패치됨?' % (desc, off))
                w.seek(pos)
                w.write(new[k:k + 1])
                touched.add(sec)
        print('\n쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    bad = 0
    with open(dst, 'rb') as r:
        for name in src:
            lba, size, _ = src[name]
            cur = read_file(r, lba, size)
            for nm, _l, off, old, new, desc in plans:
                if nm == name and cur[off:off + len(new)] != new:
                    bad += 1
                    print('  ❌%s @0x%06x 되읽기 불일치' % (desc, off))
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 되읽기 일치, EDC/ECC 유효.')
    print('완료 ->', dst)


if __name__ == '__main__':
    main()
