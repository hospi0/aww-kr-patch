# -*- coding: utf-8 -*-
"""강의 화면의 셀별 「잉크 / 쓸 수 있는가」를 ASCII 맵으로 찍는다.

기호:  .=배경·빈칸   #=잉크 있고 쓸 수 있음   x=잉크 있으나 공유타일(못 씀)
       o=빈칸이지만 쓸 수 있음                 -=빈칸이고 공유타일

사용: python tools/kougi_map.py <화면번호>
"""
import os
import sys
import struct
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_sector, walk, read_range
from kougi_view import load_state, cells_of, CW, CH
from build_kougi import derive_delta


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1])
    S = load_state(n)
    v2 = S['vdp2']
    cells = cells_of(v2)
    use = collections.Counter(a for a, _ in cells.values())

    with open(TRACK1, 'rb') as f:
        pvd = read_sector(f, 16)
        rl = struct.unpack_from('<I', pvd[156:190], 2)[0]
        rs = struct.unpack_from('<I', pvd[156:190], 10)[0]
        ent = {e['path']: e for e in walk(f, rl, rs) if not e['dir']}
        KE = ent['/KOUGI']
        K = read_range(f, KE['lba'], KE['size'])
    DELTA = derive_delta(K, v2, cells, use)   # ★화면마다 다르다
    print('보정 = %s' % hex(DELTA))

    # 화면 전체 최빈값 = 배경
    hall = collections.Counter()
    for (cx, cy), (addr, w) in cells.items():
        for k in range(64):
            hall[v2[addr + k]] += 1
    BG = hall.most_common(1)[0][0]

    print('    ' + ''.join(str(cx // 10 or ' ') for cx in range(CW)))
    print('    ' + ''.join(str(cx % 10) for cx in range(CW)))
    for cy in range(CH):
        row = ''
        for cx in range(CW):
            addr, w = cells[(cx, cy)]
            ko = addr + DELTA
            wr = use[addr] == 1 and 0 <= ko and ko + 64 <= len(K)
            ink = any(v2[addr + k] != BG for k in range(64))
            row += ('#' if wr else 'x') if ink else ('o' if wr else '-')
        print('%3d %s' % (cy, row))
    print('\nBG=0x%02x' % BG)


if __name__ == '__main__':
    main()
