"""RetroArch/Mednafen Saturn 세이브스테이트 블롭에서 섹션을 잘라낸다.

세션3-b에서 확립한 절차의 도구화. 블롭은 work/aww_state1.bin(RZIP 해제본).
Mednafen 변수 레코드 = <u8 namelen><name><u32le size><data>.
Work RAM은 swap16 저장이라 BE로 읽으려면 2바이트 스왑이 필요하다.
"""
import sys, os, struct

BLOB = os.path.join(os.path.dirname(__file__), '..', 'work', 'aww_state1.bin')

# (섹션명, 블롭 내 name 오프셋) — 같은 이름이 여러 번 나오므로 오프셋으로 구분
SECTIONS = {
    'vdp1_vram': 0x07b81d,
    'vdp2_vram': 0x2fc7f7,
    'cram':      0x37c800,
    'workraml':  0x47f3be,
    'workramh':  0x57f3cb,
}


def read_section(data, name_off):
    nlen = data[name_off - 1]
    name = data[name_off:name_off + nlen].decode('ascii')
    p = name_off + nlen
    size = struct.unpack_from('<I', data, p)[0]
    return name, data[p + 4:p + 4 + size]


def swap16(b):
    a = bytearray(b)
    a[0::2], a[1::2] = b[1::2], b[0::2]
    return bytes(a)


def main():
    data = open(BLOB, 'rb').read()
    outdir = os.path.join(os.path.dirname(__file__), '..', 'work', 'state')
    os.makedirs(outdir, exist_ok=True)
    for key, off in SECTIONS.items():
        name, blob = read_section(data, off)
        path = os.path.join(outdir, key + '.bin')
        open(path, 'wb').write(blob)
        print(f'{key:10s} name={name:10s} size={len(blob):8d} -> {path}')
        if key.startswith('workram'):
            open(path[:-4] + '_be.bin', 'wb').write(swap16(blob))


if __name__ == '__main__':
    main()
