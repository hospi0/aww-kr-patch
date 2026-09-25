# -*- coding: utf-8 -*-
"""ISO 안의 파일 하나를 **원본 그대로** 되돌린다.

왜 필요한가
  빌더의 `--revert` 는 「지금 계획에 있는 셀」만 되돌린다. 문구·박스를 바꿔가며
  여러 번 빌드하면 **이전 빌드에서 건드렸다가 지금 계획엔 없는 셀**이 남는다
  (실제로 /KOUGI 에 113B 잔여가 생겼다).
  이 도구는 파일 전체를 원본과 대조해 다른 바이트를 전부 되돌린다.

사용: python tools/restore_file.py /KOUGI
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER, read_sector, walk, read_range

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    path = sys.argv[1] if len(sys.argv) > 1 else '/KOUGI'
    with open(TRACK1, 'rb') as f:
        pvd = read_sector(f, 16)
        rl = struct.unpack_from('<I', pvd[156:190], 2)[0]
        rs = struct.unpack_from('<I', pvd[156:190], 10)[0]
        ent = {e['path']: e for e in walk(f, rl, rs) if not e['dir']}
        if path not in ent:
            raise SystemExit('없는 파일: %s' % path)
        e = ent[path]
        K = read_range(f, e['lba'], e['size'])

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    with open(dst, 'rb') as r:
        cur = read_range(r, e['lba'], e['size'])
    diff = [i for i in range(len(K)) if K[i] != cur[i]]
    print('%s lba=%d size=%d — 원본과 다른 바이트 %d개' % (path, e['lba'], e['size'], len(diff)))
    if not diff:
        print('이미 원본 상태.')
        return

    touched = set()
    with open(dst, 'r+b') as w:
        for i in diff:
            sec = e['lba'] + i // USER
            w.seek(sec * RAW + HDR + i % USER)
            w.write(bytes([K[i]]))
            touched.add(sec)
        print('쓴 섹터 %d개 — EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    with open(dst, 'rb') as r:
        cur = read_range(r, e['lba'], e['size'])
    bad = sum(1 for i in range(len(K)) if K[i] != cur[i])
    print('완료 — 잔여 차이 %d바이트 %s' % (bad, '✅' if bad == 0 else '❌'))


if __name__ == '__main__':
    main()
