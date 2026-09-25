# -*- coding: utf-8 -*-
"""UPK 유닛 레코드의 **소형폰트 이름(+0x10)** 로마자화 — 전투화면 깨짐 수리 (세션13-f).

★증상(사용자 스샷 「소형글자버그.png/2.png」): 전투 예측 패널의 유닛명이 깨진 한글로 나온다
  (`침진ー평D7`·`격미탄`). ★★원인 = **원본 가나 바이트가 그대로 남은 미패치 필드**다.
  우리가 가나 글리프(63~143)를 한글로 재정의했으므로, 안 고친 텍스트는 전부 저렇게 보인다.
  ⇒ 「소형폰트가 적용 안 됨」이 아니라 **그 화면이 읽는 사본을 우리가 안 고쳤다**([[세션8 교훈]]).

★어디였나 = **UPK(미션 파일)의 유닛 레코드 `+0x10` 8바이트**(소형폰트 이름).
  세션5는 MUSEUM 사본(`0x7e3c2` stride 0x52)만, 세션8은 UPK의 **16×16 이름(+0x00)** 만 고쳤다.
  UPK 전 파일을 「가나(63~143) 런」으로 스캔하니 남은 소형폰트 필드는 +0x10 하나뿐이었다.

★방법 = **원본 바이트로 매칭해 MUSEUM의 패치본을 그대로 옮긴다**(내용 기준 매핑).
  · 매핑 = 원본 ISO의 MUSEUM 이름 8B → **현재 F: ISO의** 같은 위치 8B (세션5가 이미 쓴 로마자)
  · UPK 레코드는 **8바이트가 원본과 완전일치할 때만** 교체 — 격자에는 이름이 아닌 데이터도 있다
    (세션8이 16×16에서 쓴 것과 같은 안전규칙: 「ソビ」·「ヨヨ8」 같은 바이너리 오탐 차단)
  ⇒ 어휘가 MUSEUM/병기도감/부대정보와 자동으로 일치한다(따로 표를 만들지 않는다).

빌드: python tools/build_unit8_upk.py            드라이런
      python tools/build_unit8_upk.py --write     F: ISO 기록
      python tools/build_unit8_upk.py --revert    원상복구
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import smallfont as sf
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
MUSEUM_BASE, STRIDE, MUSEUM_N = 0x7E3C2, 0x52, 645
UPK_BASE, NAME_OFF, NAME_LEN = 0x1A, 0x10, 8
KANA = range(63, 144)                     # 우리가 한글로 재정의한 슬롯


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def upk_files():
    return [(p, l, s) for p, l, s in files(skip_media=False)
            if p.rsplit('/', 1)[-1].startswith('UPK')]


def mapping(dst):
    """원본 MUSEUM 소형이름 8B → F: 의 패치본 8B."""
    with open(TRACK1, 'rb') as o, open(dst, 'rb') as p:
        ml, ms = [(l, s) for q, l, s in files(skip_media=False) if q == '/MUSEUM'][0]
        mo = read_file(o, ml, ms)
        mp = read_file(p, ml, ms)
    m = {}
    for i in range(MUSEUM_N):
        a = mo[MUSEUM_BASE + i * STRIDE:MUSEUM_BASE + i * STRIDE + NAME_LEN]
        b = mp[MUSEUM_BASE + i * STRIDE:MUSEUM_BASE + i * STRIDE + NAME_LEN]
        if a != b and any(x in KANA for x in a):
            m.setdefault(bytes(a), bytes(b))
    if not m:
        raise SystemExit('★MUSEUM 매핑이 비었다 — 세션5 소형폰트 패치가 F:에 없나?')
    for b in m.values():                            # 패치본에 가나가 남아있으면 안 된다
        if any(x in KANA for x in b):
            raise SystemExit('★매핑 대상에 가나 잔존: %s' % b.hex())
    return m


def plan(dst, m):
    """[(path, lba, off, orig8, new8)] — 원본 8B 완전일치만."""
    out = []
    skipped = collections.Counter()
    with open(TRACK1, 'rb') as o:
        for p, l, s in upk_files():
            d = read_file(o, l, s)
            for rec in range((s - UPK_BASE) // STRIDE):
                off = UPK_BASE + rec * STRIDE + NAME_OFF
                nm = bytes(d[off:off + NAME_LEN])
                if not any(x in KANA for x in nm):
                    continue                        # 가나 없음 = 라틴/숫자 이름이거나 데이터
                if nm in m:
                    out.append((p, l, off, nm, m[nm]))
                else:
                    skipped[nm] += 1
    return out, skipped


def main():
    revert = '--revert' in sys.argv
    write = '--write' in sys.argv or revert
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    m = mapping(dst)
    plans, skipped = plan(dst, m)
    files_n = len({p for p, _, _, _, _ in plans})
    print('MUSEUM 매핑 %d종 → UPK %d파일 %d레코드 교체 예정' % (len(m), files_n, len(plans)))
    print('교체 안 함(이름 아닌 데이터 추정) 고유 %d종 / %d레코드'
          % (len(skipped), sum(skipped.values())))
    ex = collections.Counter()
    for p, l, off, a, b in plans:
        ex[(a, b)] += 1
    for (a, b), c in ex.most_common(10):
        print('  ×%-4d 「%s」 → 「%s」'
              % (c, ''.join(sf.CHARS.get(x, '·') if x else ' ' for x in a),
                 ''.join(sf.CHARS.get(x, '·') if x else ' ' for x in b)))
    for k, c in skipped.most_common(5):
        print('  (건너뜀) %s ×%d 「%s」'
              % (k.hex(), c, ''.join(sf.CHARS.get(x, '·') if x else ' ' for x in k)))
    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --revert).')
        return

    touched = set()
    with open(dst, 'r+b') as w:
        for p, l, off, a, b in plans:
            src, dstb = (b, a) if revert else (a, b)
            for k in range(NAME_LEN):
                lo = off + k
                sec = l + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if w.read(1) != src[k:k + 1]:
                    raise SystemExit('%s 0x%x 대조실패 — %s'
                                     % (p, lo, '패치본아님' if revert else '이미패치?'))
                w.seek(pos)
                w.write(dstb[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)
    if not revert:
        verify(dst, plans, touched)


def verify(dst, plans, touched):
    bad = 0
    with open(dst, 'rb') as r:
        byfile = collections.defaultdict(list)
        for p, l, off, a, b in plans:
            byfile[(p, l)].append((off, b))
        for (p, l), items in byfile.items():
            end = max(off for off, _ in items) + NAME_LEN
            d = read_file(r, l, end)
            for off, b in items:
                if d[off:off + NAME_LEN] != b:
                    bad += 1
                    print('  ❌%s 0x%x' % (p, off))
            # 그 파일에 가나 남은 이름 필드가 있나(교체 대상만)
        for sec in sorted(touched):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 전 레코드 일치, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
