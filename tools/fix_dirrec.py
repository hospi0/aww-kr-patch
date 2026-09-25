# -*- coding: utf-8 -*-
"""루트 디렉터리 레코드 복구 — 재배치·성장한 파일이 원본 값으로 되돌려졌을 때 (세션14).

왜 필요했나 — `build_ui16.main()`이 루트 디렉터리를 **원본 TRACK1에서 통째로 읽어**
ASC16CG 레코드만 고친 뒤 F:에 되쓴다. 그래서 그 도구를 돌릴 때마다
**다른 도구가 재배치해 둔 항목(ASCGSCG·ASCMSCG)이 전부 원본 값으로 리셋**된다.
폰트 데이터는 트랙 꼬리에 그대로 남지만 아무도 참조하지 않게 되고,
더 나쁘게는 **원본 자리에 다른 폰트가 이미 얹혀 있어** 그 화면이 깨진다
(ASCMSCG를 3434에 놓았는데 ASCGSCG 레코드가 3434를 가리키게 된 상태가 실제로 났다).

⇒ build_ui16은 세션14에 「디렉터리를 **대상 ISO**에서 읽도록」 고쳤다. 이 도구는
   이미 망가진 F:를 되돌리기 위한 것이고, 앞으로도 **점검용**으로 쓸 수 있다.

의도 레이아웃은 **각 빌더의 상수에서 가져온다**(하드코딩 금지 원칙).
    ASCGSCG = build_brief.LBA / BASE_N              (메뉴+브리핑 한글, 855글리프)
    ASCMSCG = build_museum.NEW_LBA / 실제 글리프 수   (병기도감 한글, 941글리프)
    ASC16CG = build_ui16.NEW_LBA / NEW_N            (시스템메시지 한글, 900글리프)

사용:  python tools/fix_dirrec.py            점검만(차이 보고)
       python tools/fix_dirrec.py --write    F: 디렉터리 복구
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import build_brief as BB
import build_museum as BMU
import build_ui16 as BU
from isoread import TRACK1, RAW, HDR, USER, read_range, read_sector

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
GLYPH = 128


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def want():
    """[(이름, lba, size)] — 각 빌더가 의도한 최종 배치.

    ⚠️`build_brief.BASE_N`(720)은 브리핑의 **입력** 글리프 수(=build_menu 결과)다.
      최종은 거기에 브리핑 신규 슬롯(work/brief_slots.json)을 더한 855.
    ⚠️연표(build_chrono)를 기록한 뒤에는 900이 된다 — 그 도구가 디렉터리를
      **대상 ISO에서 읽어** 자기 값으로 갱신하므로, 여기 855는 「연표 이전」 기준이다.
      연표 기록 후 이 도구를 점검용으로 돌리면 ASCGSCG만 차이로 뜬다(정상).
    """
    import json
    brief = json.load(open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'work', 'brief_slots.json'), encoding='utf-8'))
    # ★★세션15 개정: 「OLD_N + 음절수」는 더 이상 폰트 크기가 아니다.
    #   전면 한글화 방침에서 신규 음절 일부는 **회수 슬롯**(원본 가나·한자, 낮은 인덱스)으로
    #   가므로 폰트가 그만큼 안 커진다. ⇒ 크기는 **배정된 최대 인덱스 + 1** 로 계산한다.
    #   (옛 식으로 두면 점검이 「수정필요」 거짓경보를 내고, --write 하면 오히려 파손된다.)
    gscg_n = max([BB.BASE_N] + [v + 1 for v in brief.values()])
    # 연표(build_chrono)가 855~899를 쓰며 폰트를 더 키운다 — 그 슬롯도 반영해야
    #   「연표 기록 후엔 ASCGSCG만 차이로 뜬다」는 거짓경보가 사라진다.
    _chrono = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'work', 'chrono_slots.json')
    if os.path.exists(_chrono):
        gscg_n = max([gscg_n] + [v + 1 for v in
                                 json.load(open(_chrono, encoding='utf-8')).values()])
    mus_n = max([BMU.OLD_N] + [v + 1 for v in BMU.build_slots().values()])
    return [
        ('ASCGSCG', BB.LBA,      gscg_n * GLYPH),
        ('ASCMSCG', BMU.NEW_LBA, mus_n * GLYPH),
        ('ASC16CG', BU.NEW_LBA,  BU.NEW_N * GLYPH),
    ]


def root(f):
    pvd = read_sector(f, 16)
    rlba = struct.unpack_from('<I', pvd, 156 + 2)[0]
    rsize = struct.unpack_from('<I', pvd, 156 + 10)[0]
    return rlba, rsize, bytearray(read_range(f, rlba, rsize))


def recs(data, name):
    out, off = [], 0
    while off < len(data):
        ln = data[off]
        if ln == 0:
            off = (off // USER + 1) * USER
            if off >= len(data):
                break
            continue
        nlen = data[off + 32]
        if data[off + 33:off + 33 + nlen].split(b';')[0] == name.encode():
            out.append((off,
                        struct.unpack_from('<I', data, off + 2)[0],
                        struct.unpack_from('<I', data, off + 10)[0]))
        off += ln
    return out


def main():
    write = '--write' in sys.argv
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    with open(dst, 'rb') as f:
        rlba, rsize, data = root(f)
        fixes = []
        for name, lba, size in want():
            rs = recs(data, name)
            if not rs:
                raise SystemExit('%s 레코드를 못 찾음' % name)
            # 목적지에 실제 데이터가 있는지 확인 — 빈 자리를 가리키게 만들지 않는다
            blob = read_file(f, lba, size)
            if not any(blob):
                raise SystemExit('★%s 목적지 lba %d 가 비어 있다 — 폰트를 먼저 기록할 것' % (name, lba))
            nz = sum(1 for k in range(0, len(blob), USER) if any(blob[k:k + USER]))
            for off, cl, cs in rs:
                mark = '' if (cl, cs) == (lba, size) else '  ★수정필요'
                print('%-8s off=%-5d 현재 %8d,%7d → 의도 %8d,%7d  (데이터 %d/%d섹터)%s'
                      % (name, off, cl, cs, lba, size, nz,
                         (size + USER - 1) // USER, mark))
                if (cl, cs) != (lba, size):
                    fixes.append((off, lba, size, name))

    if not fixes:
        print('\n디렉터리 정상 — 고칠 것 없음.')
        return
    print('\n수정 대상 %d레코드' % len(fixes))
    if not write:
        print('점검만 — 기록하려면 --write')
        return

    for off, lba, size, name in fixes:
        struct.pack_into('<I', data, off + 2, lba)
        struct.pack_into('>I', data, off + 6, lba)
        struct.pack_into('<I', data, off + 10, size)
        struct.pack_into('>I', data, off + 14, size)

    touched = set()
    with open(dst, 'r+b') as w:
        for k in range(0, len(data), USER):
            sec = rlba + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(data[k:k + USER]).ljust(USER, b'\x00')[:USER])
            touched.add(sec)
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('루트 디렉터리 %d섹터 기록, EDC/ECC 재계산 완료.' % len(touched))

    # 독립 되읽기
    bad = 0
    with open(dst, 'rb') as f:
        _, _, d2 = root(f)
        for name, lba, size in want():
            for off, cl, cs in recs(d2, name):
                if (cl, cs) != (lba, size):
                    bad += 1
                    print('  ❌%s off=%d 여전히 %d,%d' % (name, off, cl, cs))
        for sec in sorted(touched):
            f.seek(sec * RAW)
            raw = f.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('복구 검증 실패 %d건' % bad)
    print('독립검증 통과 — 세 폰트 디렉터리 레코드 전부 의도값, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
