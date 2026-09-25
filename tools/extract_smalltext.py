# -*- coding: utf-8 -*-
"""소형폰트 텍스트 전 구조 가역 추출 → work/smalltext/*.tsv (세션5 확정 인벤토리).

구조:
  고정 stride 표:
    GMDT 이름표    0x74c4  stride 8  ×437 (무기0~180·지형181~191·지명192~436)
    무기표 사본    MUSEUM 0x90210 / SAKUSEN 0x542d8 / KEKKA 0x3af82  stride 8 ×181
    MUSEUM 유닛표  0x7e3c2 stride 0x52 ×645 (이름=선두 8B)
  델리미터 풀 (구분자 00/fd/fe/ff):
    GMDT UI풀           0x24745~0x24c1c
    SAKUSEN 지형리스트    0x492ec~0x49350
    SAKUSEN 지명+지형풀   0x4eb96~0x4f390

TSV 컬럼: module  kind  offset  len  jp  hex  (kr는 빌드 시 채움)
가역성: offset+len+hex 로 원본 바이트 완전 복원 가능.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT = os.path.join(ROOT, 'work', 'extract')
OUT = os.path.join(ROOT, 'work', 'smalltext')
SEP = {0, 0xfd, 0xfe, 0xff}


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return f.read()


def dec(b):
    return sf.decode(b, 0, len(b), stop=False)


def emit_stride(rows, mod, buf, kind, off, stride, count, namelen=8):
    for k in range(count):
        o = off + k * stride
        fb = buf[o:o + namelen]
        jp = dec(fb).rstrip('\x00 ').replace('\x00', '')
        rows.append((mod, kind, o, namelen, jp, fb.hex(), k))


def emit_pool(rows, mod, buf, kind, lo, hi):
    i = lo
    idx = 0
    while i < hi:
        while i < hi and buf[i] in SEP:
            i += 1
        s = i
        while i < hi and buf[i] not in SEP:
            i += 1
        if i > s:
            fb = buf[s:i]
            rows.append((mod, kind, s, len(fb), dec(fb), fb.hex(), idx))
            idx += 1


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []

    gmdt = load('GMDT')
    museum = load('MUSEUM')
    sakusen = load('SAKUSEN')
    kekka = load('KEKKA')

    # 고정 stride 표
    emit_stride(rows, 'GMDT', gmdt, 'names', 0x74c4, 8, 437)          # 무기/지형/지명
    emit_stride(rows, 'MUSEUM', museum, 'weapons', 0x90210, 8, 181)
    emit_stride(rows, 'SAKUSEN', sakusen, 'weapons', 0x542d8, 8, 181)
    emit_stride(rows, 'KEKKA', kekka, 'weapons', 0x3af82, 8, 181)
    emit_stride(rows, 'MUSEUM', museum, 'units', 0x7e3c2, 0x52, 645)

    # 델리미터 풀 (한글이 더 짧아 length-lock 널패딩 가능)
    emit_pool(rows, 'GMDT', gmdt, 'ui', 0x24745, 0x24c1c)
    emit_pool(rows, 'SAKUSEN', sakusen, 'terrain', 0x492ec, 0x49350)
    # SAKUSEN 지명풀 = 실제 고정 8바이트 270레코드 (지형copy+지명, 지명리스트 2회반복)
    emit_stride(rows, 'SAKUSEN', sakusen, 'places', 0x4eb96, 8, 270)

    path = os.path.join(OUT, 'smalltext.tsv')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('module\tkind\toffset\tlen\tjp\thex\tidx\tkr\n')
        for mod, kind, o, ln, jp, hx, idx in rows:
            f.write('%s\t%s\t0x%x\t%d\t%s\t%s\t%d\t\n' % (mod, kind, o, ln, jp, hx, idx))

    # 요약
    from collections import Counter
    c = Counter((r[0], r[1]) for r in rows)
    print('추출 완료 -> %s' % path)
    print('총 %d행' % len(rows))
    for (mod, kind), n in sorted(c.items()):
        print('  %-8s %-8s %d' % (mod, kind, n))

    # 무기표 4벌 동일성 검사
    def wt(mod, buf, off):
        return [buf[off + k * 8:off + k * 8 + 8] for k in range(181)]
    g = wt('GMDT', gmdt, 0x74c4)
    for mod, buf, off in [('MUSEUM', museum, 0x90210), ('SAKUSEN', sakusen, 0x542d8),
                          ('KEKKA', kekka, 0x3af82)]:
        w = wt(mod, buf, off)
        diff = sum(1 for a, b in zip(g, w) if a != b)
        print('  무기표 GMDT vs %-8s 불일치 레코드 %d/181' % (mod, diff))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
