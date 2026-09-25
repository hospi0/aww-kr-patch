# -*- coding: utf-8 -*-
"""구조화된 소형폰트 텍스트 테이블/풀의 경계·구조 정밀 매핑.

앵커로 찾은 각 지형 텍스트 위치의 주변을 덤프해 구조를 파악한다.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf

EXTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'extract')


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return f.read()


def dump_region(buf, start, end, label):
    """구분자(00/fd/fe/ff)로 분할해 문자열 나열."""
    print('--- %s  0x%x~0x%x (%d B) ---' % (label, start, end, end - start))
    i = start
    cur = bytearray()
    cs = start
    out = []
    while i < end:
        b = buf[i]
        if b in (0, 0xfd, 0xfe, 0xff):
            if cur:
                out.append((cs, bytes(cur)))
            cur = bytearray()
            cs = i + 1
        else:
            if not cur:
                cs = i
            cur.append(b)
        i += 1
    if cur:
        out.append((cs, bytes(cur)))
    for o, s in out:
        txt = sf.decode(s, 0, len(s), stop=False)
        # 가나 포함한 것만
        if any(63 <= b <= 143 for b in s) and len(s) >= 2:
            print('  0x%06x  %-16s %s' % (o, txt[:20], s.hex()))


def dump_stride(buf, start, stride, count, label, namelen=8):
    print('--- %s  0x%x stride=0x%x ×%d ---' % (label, start, stride, count))
    for k in range(count):
        o = start + k * stride
        nm = sf.decode(buf, o, namelen, stop=False).rstrip('\x00 ').replace('\x00', '')
        print('  %3d 0x%06x  %s' % (k, o, nm))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('module')
    ap.add_argument('start', type=lambda x: int(x, 0))
    ap.add_argument('end', type=lambda x: int(x, 0))
    ap.add_argument('--stride', type=lambda x: int(x, 0), default=None)
    ap.add_argument('--count', type=int, default=None)
    args = ap.parse_args()
    buf = load(args.module)
    if args.stride:
        dump_stride(buf, args.start, args.stride, args.count or 20, args.module)
    else:
        dump_region(buf, args.start, args.end, args.module)
