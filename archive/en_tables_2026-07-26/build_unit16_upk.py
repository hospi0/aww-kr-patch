# -*- coding: utf-8 -*-
"""전투 화면 16×16 유닛명 — 미션 UPK 파일 패치 (세션8).

`build_unit16.py`로 MUSEUM 유닛 DB를 고쳤더니 **병기도감만 바뀌고 전투 화면은 그대로**였다.
⇒ 전투 화면은 MUSEUM을 안 읽는다. 세션2에 이미 단서가 있었다 —
   「M00/UPK~M64/UPK(미션 로스터 80파일)... 고정길이 유닛레코드(이름 `1号戦車A型` @M00/UPK 0x2fc)」.
★★교훈: **같은 이름이 여러 파일에 사본으로 있고 화면마다 다른 사본을 읽는다.**
  세션4에도 「병기도감=MUSEUM표 / 인게임=GMDT표」로 같은 함정이 기록돼 있었다.
  한 곳 고치고 "됐다" 하지 말고 **화면별로 어느 사본을 읽는지 확인**할 것.

UPK 구조(측정): **base `0x1A`, stride `0x52`, 이름 = 레코드 +0의 8글리프(16B)**.
  MUSEUM 유닛 DB와 stride가 같고 순서도 같다 — **UPK rec n = MUSEUM rec n+3**
  (UPK 0x1A='NOT'=MUSEUM rec3, UPK 0x2fc='1号戦車A型'=MUSEUM rec12).
  ⚠️격자 372슬롯 중 이름이 유효한 건 279뿐 — 나머지는 다른 데이터다. 그래서 슬롯을
    **원본 16바이트가 정확히 일치할 때만** 교체한다(문자열 디코드 일치만으로는 부족).
  ⚠️세션6이 같은 파일의 **로스터(stride 0x62, 소형폰트 1B/자)** 를 이미 패치했다. 필드가
    달라 충돌하지 않지만, 원문 대조로 한 번 더 막는다.

대상 = 미션 65개 디렉터리의 UPK* 파일 **80개**(전부 30,508 B).

빌드: python tools/build_unit16_upk.py           드라이런
      python tools/build_unit16_upk.py --write   F: ISO 제자리 기록
      python tools/build_unit16_upk.py --revert  원상복구
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_unit16 as U
from isoread import TRACK1, RAW, HDR, USER, read_sector, read_range

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
UPK_BASE, UPK_STRIDE, WIDTH = 0x1A, 0x52, 8


def list_upk(f):
    pvd = read_sector(f, 16)
    rl = struct.unpack_from('<I', pvd, 156 + 2)[0]
    rs = struct.unpack_from('<I', pvd, 156 + 10)[0]

    def ls(lba, size):
        d = read_range(f, lba, size)
        out, off = [], 0
        while off < len(d):
            ln = d[off]
            if ln == 0:
                off = (off // USER + 1) * USER
                if off >= len(d):
                    break
                continue
            nl = d[off + 32]
            nm = d[off + 33:off + 33 + nl].split(b';')[0].decode('latin1')
            out.append((nm, struct.unpack_from('<I', d, off + 2)[0],
                        struct.unpack_from('<I', d, off + 10)[0], d[off + 25]))
            off += ln
        return out

    files = []
    for nm, lba, size, fl in ls(rl, rs):
        if not (fl & 2) or not (nm.startswith('M') and nm[1:].isdigit()):
            continue
        for n2, l2, s2, f2 in ls(lba, size):
            if n2.startswith('UPK'):
                files.append(('%s/%s' % (nm, n2), l2, s2))
    return files


def name_map():
    """원본 16B 블롭 -> 새 16B 블롭 (build_unit16 과 같은 규칙)."""
    p, stats, cm = U.plan()
    return {old: new for _, _, old, new, _, _ in p}, {old: (jp, en) for _, _, old, new, jp, en in p}, cm


def build(f, files, blob):
    plans = []
    for path, lba, size in files:
        d = read_range(f, lba, size)
        hits = []
        o = UPK_BASE
        while o + WIDTH * 2 <= len(d):
            cur = d[o:o + WIDTH * 2]
            if cur in blob:
                hits.append((o, cur, blob[cur]))
            o += UPK_STRIDE
        if hits:
            plans.append((path, lba, hits))
    return plans


def rw(dst, plans, revert=False):
    import ecc
    touched = set()
    with open(dst, 'r+b') as w:
        for path, lba, hits in plans:
            for o, old, new in hits:
                src, dstb = (new, old) if revert else (old, new)
                for k in range(len(old)):
                    lo = o + k
                    sec = lba + lo // USER
                    pos = sec * RAW + HDR + (lo % USER)
                    w.seek(pos)
                    if w.read(1) != src[k:k + 1]:
                        raise SystemExit('%s @0x%x 대조 실패 (%s)'
                                         % (path, o, '패치본 아님' if revert else '이미 패치됨?'))
                    w.seek(pos)
                    w.write(dstb[k:k + 1])
                    touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))


def verify(dst, plans, revert):
    bad = 0
    with open(dst, 'rb') as r:
        for path, lba, hits in plans:
            for o, old, new in hits:
                want = old if revert else new
                got = bytearray()
                for k in range(len(want)):
                    lo = o + k
                    r.seek((lba + lo // USER) * RAW + HDR + (lo % USER))
                    got += r.read(1)
                if bytes(got) != want:
                    bad += 1
                    print('  ❌%s @0x%x 되읽기 불일치' % (path, o))
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립 되읽기 통과.')


def main():
    blob, info, cm = name_map()
    print('이름 매핑 %d종 (build_unit16 과 동일)' % len(blob))
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    rev = '--revert' in sys.argv
    with open(dst, 'rb') as f:
        files = list_upk(f)
        print('UPK 파일 %d개' % len(files))
        if rev:                      # 복구 시에는 이미 새 블롭이 들어있다
            inv = {v: k for k, v in blob.items()}
            plans = build(f, files, inv)
            plans = [(p, l, [(o, a, b) for o, a, b in h]) for p, l, h in plans]
        else:
            plans = build(f, files, blob)
    n = sum(len(h) for _, _, h in plans)
    print('패치 대상 %d파일 / %d레코드' % (len(plans), n))
    if plans:
        p0 = plans[0]
        for o, old, new in p0[2][:6]:
            jp, en = info.get(old, ('?', '?')) if not rev else ('(복구)', '(원문)')
            print('   %s @0x%05x  %-13s -> %s' % (p0[0], o, jp, en))
    if not rev and '--write' not in sys.argv:
        print('\n드라이런 — 미기록 (--write / --revert).')
        return
    rw(dst, plans, revert=rev)
    verify(dst, plans, rev)
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
