# -*- coding: utf-8 -*-
"""세션7 훅으로 우회했던 텍스처들의 **디스크 원본**을 다시 찾는다 (세션17).

세션6-d는 「攻撃 텍스처를 디스크에서 못 찾았다 ⇒ 압축」으로 판정하고 코드주입으로 우회했다.
그런데 세션17에 승리화면 배너가 **같은 이유로 못 찾은 줄 알았다가 swap16 을 풀자 그대로 나왔다.**
⇒ 스테이트 섹션(VDP1 VRAM·WorkRAM)은 **swap16 저장**이다. 그 상태의 바이트로 디스크를 뒤지면
   당연히 0건이 나온다. 세션6-d 판정도 같은 함정일 수 있으므로 재검한다.

원본이 나오면 트램폴린·스텁·마스크(코드주입 일체)를 걷어내고 **제자리 패치**로 갈 수 있고,
세션13-g의 노이즈(주입 자리가 그래픽 꼬리였던 문제)도 근본적으로 사라진다.

사용: python tools/find_btn_src.py <해제된 state blob .bin>
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_analyze import swap16
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
import btn_data as bd

CAND = ['/GMDT', '/GAME', '/0', '/SAKUSEN', '/MUSEUM', '/KEKKA',
        '/INTERM', '/GMSELDT', '/SCHOOL']


def sections(blob):
    out = {}
    i, n = 0, len(blob)
    while i < n - 8:
        L = blob[i]
        if 2 <= L <= 16:
            nm = blob[i + 1:i + 1 + L]
            if all(32 <= c < 127 for c in nm):
                sz = struct.unpack_from('<I', blob, i + 1 + L)[0]
                if 64 <= sz <= 2 * 1024 * 1024 and i + 1 + L + 4 + sz <= n:
                    out.setdefault(nm.decode(), []).append((i + 1 + L + 4, sz))
                    i = i + 1 + L + 4 + sz
                    continue
        i += 1
    return out


def read_file(path):
    m = {q: (l, s) for q, l, s in files(skip_media=False)}
    lba, size = m[path]
    out = bytearray()
    with open(TRACK1, 'rb') as f:
        for k in range(0, size, USER):
            f.seek((lba + k // USER) * RAW + HDR)
            out += f.read(min(USER, size - k))
    return bytes(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    blob = open(sys.argv[1], 'rb').read()
    sec = sections(blob)
    if 'WorkRAML' not in sec:
        print('WorkRAML 섹션 없음 — 섹션:', list(sec))
        return
    wo, ws = sec['WorkRAML'][0]
    WL = {'raw': blob[wo:wo + ws]}
    WL['swap'] = swap16(WL['raw'])
    disks = {p: read_file(p) for p in CAND}

    total = 0
    # 버튼 풀 42개 (0x100 stride)
    for i in range(bd.COUNT):
        off = 0x0AD780 + i * 0x100
        for tag, buf in WL.items():
            tex = buf[off:off + 0x100]
            if len(set(tex)) < 4:
                continue
            for p, d in disks.items():
                j = d.find(tex)
                if j >= 0:
                    print('  버튼#%-2d %-5s → %s@0x%06X' % (i, tag, p, j))
                    total += 1
    # 設定変更 타이틀 (0x2B01E8, 104x32 4bpp = 0x680)
    for tag, buf in WL.items():
        tex = buf[0x0B01E8:0x0B01E8 + 0x680]
        if len(set(tex)) < 4:
            continue
        for p, d in disks.items():
            j = d.find(tex)
            if j >= 0:
                print('  타이틀  %-5s → %s@0x%06X' % (tag, p, j))
                total += 1
    print('일치 %d건' % total)


if __name__ == '__main__':
    main()
