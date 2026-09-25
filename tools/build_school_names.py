# -*- coding: utf-8 -*-
"""사관학교 공군 동료 이름 9종 패치 (세션15-g).

★발견 경위: 사용자가 「공군 동료 이름도 한글화됐나」 물어 확인했더니 **미패치**였고,
  게다가 소형폰트 사본이 **세션5 이후 계속 깨져 있었다**(가나 슬롯을 한글로 재정의했는데
  이 표는 그때 발견되지 않았다). 실기 표시: ヘレナ→**「미결무」**, ブリッツ→**「심덕착다」**.
  세션8의 「쿠폭야폭」(空港) 사고와 같은 유형 — **폰트 소비자 열거 누락**.

구조(/SCHOOL, 실측): 레코드 base `0x07B950`, stride `0x62`, 9명
    +0x0A  16×16 이름 (널 종료, 필드 9글리프분 — 안전하게 ≤8 사용)
    +0x44  소형 8×8 이름 (널 종료, **8바이트**) — 원본은 `<이름>AF` 형식(AF=공군)

방침(사용자 결정): **16×16 = 한글 / 소형 = 로마자**
  소형폰트는 240글리프 중 53칸이 유닛아이콘이라 한글 칸이 없다(세션15 실측 가용 99칸을
  세션5가 이미 소진). 부대명·장군명과 같은 처리다.

빌드: python tools/build_school_names.py            드라이런
      python tools/build_school_names.py --write     F: ISO 기록
      python tools/build_school_names.py --resync    구성 바뀐 재기록
      python tools/build_school_names.py --revert    원상복구
"""
import os
import sys
import csv
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import charmap
from school_charmap import SCHOOL_CHARS
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

REC_BASE, STRIDE, NREC = 0x07AF5C, 0x62, 35   # 실측: 미설정 23 + 캐릭터 12
OFF16, OFFSMALL = 0x0A, 0x44
W16, WSMALL = 8, 8          # 실측 필드 폭

# 원문 : (16×16 한글, 소형 로마자)  — 소형은 원본과 같은 `<이름>AF` 형식 유지
NAMES = {
    'メイショウ':    ('명칭',     'Name'),        # 미설정 슬롯 23칸(원문 「名称」)
    'ヴァルター':    ('발터',     'WalterAF'),
    'フランツ':     ('프란츠',   'FranzAF'),
    'ハウゼン':     ('하우젠',   'HausenAF'),
    'ヘレナ':       ('헬레나',   'HelenaAF'),
    'ルードビッヒ':  ('루트비히', 'LudwigAF'),
    'ガーヴィン':    ('가빈',     'GarvinAF'),
    'ローザリー':    ('로잘리',   'RosaliAF'),   # 사용자 결정(2026-07-26): 로절리→로잘리
    'ドロテーア':    ('도로테아', 'DoroteAF'),
    'ラインリック':  ('라인리히', 'ReinlcAF'),   # 사용자 결정: 라인리히
    'パウル':       ('파울',     'PaulAF'),
    'アルフレッド':  ('알프레트', 'AlfredAF'),
    'ブリッツ':      ('블리츠',   'BlitzAF'),
}


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def tbl16():
    t = dict(charmap.CHARS)
    t.update(SCHOOL_CHARS)
    return t


def small_map():
    """소형폰트 원본 문자표 — smalltext.tsv 의 (jp, hex) 쌍에서 역산."""
    rows = list(csv.reader(open(os.path.join(ROOT, 'work', 'smalltext', 'smalltext.tsv'),
                                encoding='utf-8'), delimiter='\t'))[1:]
    m = {}
    for r in rows:
        jp, hx = r[4], r[5]
        try:
            b = bytes.fromhex(hx)
        except Exception:
            continue
        if len(jp) == len(b):
            for c, x in zip(jp, b):
                m.setdefault(c, x)
    return m


def kr_slots():
    """이름 16×16 필드의 한글 슬롯 = **ASC16CG·SCHOOL 공용 슬롯**.

    🐞세션17: 예전엔 SCHOOL 슬롯(school_slots.json)으로만 인코딩했다. 그런데 이 표는
      **사본이 하나인데 두 화면이 읽는다** — 사관학교 = SCHOOL 폰트 / 전투화면 좌패널·
      유닛 헤더 = ASC16CG. ⇒ 전투화면에서 「로절리」가 **「줄詰입」**으로 떴다
      (사용자 스샷 2026-07-26). 세션15-e 유닛명(`shared_slots`)과 같은 클래스의 함정.
    ⇒ `shared_school_slots` 가 두 폰트에서 동시에 자유로운 인덱스를 배정하고,
      두 폰트 빌더가 그 인덱스에 **같은 글리프**를 그린다.
    """
    import shared_school_slots
    return shared_school_slots.build(verbose=False)


def plan(d):
    t = tbl16()
    rev16 = {}
    for k, v in t.items():
        rev16.setdefault(v, k)
    sm = small_map()
    slot = kr_slots()
    plans = []
    for n in range(NREC):
        o = REC_BASE + n * STRIDE
        # 원문 확인
        jp = ''
        for j in range(W16 + 2):
            v = struct.unpack_from('>H', d, o + OFF16 + j * 2)[0]
            if v in (0, 0xFFFF):
                break
            jp += t.get(v, '?')
        if jp not in NAMES:
            raise SystemExit('rec %d 원문 불일치: %r' % (n, jp))
        kr, latin = NAMES[jp]
        if len(kr) > W16:
            raise SystemExit('%r %d글리프 > %d' % (kr, len(kr), W16))
        if len(latin) > WSMALL:
            raise SystemExit('%r %d바이트 > %d' % (latin, len(latin), WSMALL))
        # 16×16
        nb = b''.join(struct.pack('>H', slot[c] if '가' <= c <= '힣' else rev16[c])
                      for c in kr).ljust(W16 * 2, b'\x00')
        plans.append((o + OFF16, d[o + OFF16:o + OFF16 + W16 * 2], nb, jp, kr))
        # 소형
        sb = bytes(sm[c] if c in sm else ord(c) for c in latin).ljust(WSMALL, b'\x00')
        plans.append((o + OFFSMALL, d[o + OFFSMALL:o + OFFSMALL + WSMALL], sb, jp, latin))
    return plans, slot


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    with open(TRACK1, 'rb') as f:
        hits, _, _, _ = find_dirrec(f, 'SCHOOL')
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
    plans, slot = plan(d)
    print('SCHOOL lba=%d  이름 %d곳 (16×16 %d + 소형 %d)'
          % (lba, len(plans), NREC, NREC))
    for o, old, new, jp, kr in plans:
        print('   0x%06x  %-12s → %s' % (o, jp, kr))
    print('한글 슬롯 %d음절 → 글리프 %d~%d (SCHOOL 폰트, 천장 1024)'
          % (len(slot), min(slot.values()), max(slot.values())))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --resync / --revert).')
        return
    print('\n⚠️ 폰트 글리프 기록은 사관학교 본문 빌더와 함께 해야 한다 — 여기선 텍스트만.')


if __name__ == '__main__':
    main()
