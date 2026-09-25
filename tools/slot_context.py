# -*- coding: utf-8 -*-
"""자유 슬롯 후보를 **문맥 판독**으로 최종 검증한다.

창(window) 기반 느슨 검출기는 노이즈가 커서 판정이 창 크기에 따라 흔들린다(실측:
창 16→103칸, 64→56칸). 그래서 후보 하나하나에 대해 디스크에서 그 인덱스가 나오는
자리를 찾아 **앞뒤를 일본어로 디코드**해 본다. 진짜 텍스트면 주변이 문장으로 읽히고,
유닛 스탯 같은 바이너리면 아무 말도 안 된다.

판정: 주변 8워드 중 유효 글리프가 6개 이상이고 그중 가나·한자가 3개 이상이면 '텍스트 의심'.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import free_slots as FS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTX = 8


def load_map():
    m = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    return {int(k): v for k, v in m.items()}


def is_jp(ch):
    if not ch:
        return False
    o = ord(ch)
    return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF


def check(cands, verbose=True):
    """{idx: [(파일, 오프셋, 디코드문자열)]} — 텍스트로 의심되는 자리만."""
    cm = load_map()
    want = set(cands)
    hits = {i: [] for i in cands}
    with open(TRACK1, 'rb') as f:
        for p, lba, size in files():
            if size < 32 or size > 3_000_000:
                continue
            if any(p.startswith(x) for x in FS.OTHER_FONT):
                continue
            d = read_range(f, lba, size)
            n = len(d) // 2
            for k in range(n):
                v = (d[2 * k] << 8) | d[2 * k + 1]
                if v not in want:
                    continue
                lo, hi = max(0, k - CTX // 2), min(n, k + CTX // 2 + 1)
                ws = [(d[2 * j] << 8) | d[2 * j + 1] for j in range(lo, hi)]
                chars = [cm.get(w) if 1 <= w <= 824 else None for w in ws]
                valid = sum(1 for c in chars if c)
                jp = sum(1 for c in chars if is_jp(c))
                if valid >= 6 and jp >= 3:
                    hits[v].append((p, k * 2, ''.join(c or '·' for c in chars)))
    if verbose:
        for i in cands:
            h = hits[i]
            tag = '❌텍스트 의심 %d곳' % len(h) if h else '✅깨끗'
            print('%4d %-2s %s  %s' % (i, cm.get(i, '?'), tag,
                                       ' | '.join('%s@0x%x %s' % x for x in h[:3])))
    return hits


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 70
    ranked = FS.load()
    check(ranked[:n])
