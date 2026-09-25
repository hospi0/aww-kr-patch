# -*- coding: utf-8 -*-
"""BPE **사전 직렬화 규칙**을 원본 스트림으로 증명한다.

세션21 인코더는 사전을 디코더 규칙과 다르게 써서 순환 참조를 만들었다. 추정으로
고치지 말고, **게임이 만든 사전 바이트를 다시 만들어 그대로 나오는지** 본다
(JPN↔KOR 바이트diff 와 같은 「정답지 대조」 기법).

usage:
  python tools/bpe_verify.py parse      원본 254개 사전 파싱 + 재직렬화 대조
  python tools/bpe_verify.py tiny       몇십 바이트 합성 입력 왕복 검증
  python tools/bpe_verify.py round [N]  실제 파일 N개 왕복 검증(작은 것부터)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpe
from isoread import TRACK1, read_sector, walk, read_range


def entries():
    f = open(TRACK1, 'rb')
    pvd = read_sector(f, 16)
    rl = struct.unpack_from('<I', pvd[156:190], 2)[0]
    rs = struct.unpack_from('<I', pvd[156:190], 10)[0]
    return f, [e for e in walk(f, rl, rs)
               if not e['dir'] and e['path'].startswith('/ITMSN/')]


def parse_blocks(data):
    """스트림을 블록으로 쪼개 (사전바이트, left, right, 페이로드) 를 돌려준다."""
    p, n = 0, len(data)
    blocks = []
    while p < n:
        d0 = p
        left = list(range(256))
        right = [0] * 256
        count = data[p]
        p += 1
        c = 0
        while True:
            if count > 127:
                c += count - 127
                count = 0
            if c >= 256:
                break
            for _ in range(count + 1):
                if c >= 256:
                    break
                left[c] = data[p]
                p += 1
                if c != left[c]:
                    right[c] = data[p]
                    p += 1
                c += 1
            if c >= 256 or p >= n:
                break
            count = data[p]
            p += 1
        if p + 1 >= n:
            break
        dict_bytes = data[d0:p]
        size = (data[p] << 8) | data[p + 1]
        p += 2
        payload = data[p:p + size]
        p += size
        blocks.append((dict_bytes, left, right, payload))
    return blocks


def cmd_parse():
    f, ent = entries()
    tot = ok = 0
    bad = []
    for e in sorted(ent, key=lambda x: x['size']):
        raw = read_range(f, e['lba'], e['size'])
        try:
            blocks = parse_blocks(raw)
        except IndexError:
            continue
        for db, left, right, _ in blocks:
            tot += 1
            mine = bpe.serialize_dict(left, right)
            if mine == db:
                ok += 1
            elif len(bad) < 6:
                bad.append((e['path'], len(db), len(mine), db[:24].hex(),
                            mine[:24].hex()))
    print('사전 블록 %d개 중 **바이트 동일 %d개** (%.1f%%)'
          % (tot, ok, 100.0 * ok / max(tot, 1)))
    for p_, a, b, x, y in bad:
        print('  ✗ %s 원본 %dB / 내것 %dB\n     원본 %s\n     내것 %s'
              % (p_, a, b, x, y))


def cmd_tiny():
    """★78KB 지도로 바로 던지지 말 것 — 몇십 바이트로 먼저 통과시킨다."""
    cases = [
        b'', b'A', b'AB', b'AAAA', b'ABABABABABAB',
        b'ABCABCABCABCABCABC', bytes(range(256)),
        bytes(range(256)) * 2, b'\x00' * 300,
        (b'the quick brown fox jumps over the lazy dog ' * 4),
        bytes((i * 7 + i // 5) & 0xFF for i in range(1000)),
    ]
    bad = 0
    for i, raw in enumerate(cases):
        try:
            c = bpe.compress(raw)
            back = bpe.decompress(c)
        except bpe.BpeError as ex:
            print('  ✗ #%d %dB → BpeError: %s' % (i, len(raw), ex))
            bad += 1
            continue
        st = '✅' if back == raw else '❌'
        if back != raw:
            bad += 1
        print('  %s #%-2d 원본 %5dB → 압축 %5dB → 복원 %5dB'
              % (st, i, len(raw), len(c), len(back)))
    print('실패 %d건' % bad)


def cmd_round(limit=8):
    f, ent = entries()
    bad = 0
    for e in sorted(ent, key=lambda x: x['size'])[:limit]:
        raw = read_range(f, e['lba'], e['size'])
        try:
            dec = bpe.decompress(raw)
        except bpe.BpeError as ex:
            print('  -- %s 전개 실패: %s' % (e['path'], ex))
            continue
        c = bpe.compress(dec)
        try:
            back = bpe.decompress(c)
        except bpe.BpeError as ex:
            print('  ✗ %s 재압축본 전개 실패: %s' % (e['path'], ex))
            bad += 1
            continue
        st = '✅' if back == dec else '❌'
        if back != dec:
            bad += 1
        print('  %s %-20s 전개 %6dB  원본 %6dB → 내것 %6dB (%+d)'
              % (st, e['path'], len(dec), e['size'], len(c), len(c) - e['size']))
    print('왕복 실패 %d건' % bad)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'parse'
    if cmd == 'parse':
        cmd_parse()
    elif cmd == 'tiny':
        cmd_tiny()
    else:
        cmd_round(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
