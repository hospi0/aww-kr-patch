"""소형 8x8 폰트 확장에 필요한 3종 상수를 각 모듈에서 SH-2 리터럴 역추적으로 확정.

상수:
  1. 폰트 RAM 주소 리터럴 (코드 여러 곳 + 파일끝 디스크립터) — BE32 == ram_base+fo
  2. 크기 상수 (업로드 루틴이 R6로 싣는 u16 롱워드 개수 = 229*32/4 = 1832 = 0x0728)

방법 (docs/05):
  · MOV.L @(disp,PC),Rn = 0xDn dd, target = ((A+4)&~3)+disp*4
  · MOV.W @(disp,PC),Rn = 0x9n dd, target = (A+4)+disp*2
  · 업로드 호출: R4=폰트 src 주소, R5=VRAM dst, R6=롱워드 개수, JSR @R2
  → 폰트주소 리터럴을 R4로 읽는 MOV.L 근처에서 R6로 u16(=1832)을 싣는 MOV.W 를 찾는다.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf

EXTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'extract')

OLD_N = 229
COUNT = OLD_N * 32 // 4   # 1832 = 0x0728
DESC_OFF = OLD_N * 32     # 0x1ca0

# 모듈: (폰트 파일오프셋, RAM 베이스, 상수를 담은 코드 모듈)
MODS = {
    'MUSEUM':  dict(fo=0x109e8, ram_base=0x06060000, code='MUSEUM'),
    'SAKUSEN': dict(fo=0x1c9cc, ram_base=0x06060000, code='SAKUSEN'),
    'KEKKA':   dict(fo=0x17cb8, ram_base=0x06060000, code='KEKKA'),
    'INTERM':  dict(fo=0x3ab40, ram_base=0x06060000, code='INTERM'),
    'GMDT':    dict(fo=0x28ef8, ram_base=0x00208000, code='GAME'),
}


def load(name):
    with open(os.path.join(EXTRACT, name), 'rb') as f:
        return f.read()


def find_be32(buf, val):
    out, target = [], struct.pack('>I', val)
    i = buf.find(target)
    while i != -1:
        out.append(i)
        i = buf.find(target, i + 1)
    return out


def movl_targets(buf):
    """모든 MOV.L @(disp,PC),Rn 을 (addr, reg, target) 로."""
    out = []
    for a in range(0, len(buf) - 1, 2):
        if buf[a] >> 4 == 0xD:
            reg = buf[a] & 0xF
            disp = buf[a + 1]
            tgt = ((a + 4) & ~3) + disp * 4
            out.append((a, reg, tgt))
    return out


def movw_targets(buf):
    out = []
    for a in range(0, len(buf) - 1, 2):
        if buf[a] >> 4 == 0x9:
            reg = buf[a] & 0xF
            disp = buf[a + 1]
            tgt = (a + 4) + disp * 2
            out.append((a, reg, tgt))
    return out


def analyze(name):
    p = MODS[name]
    fo, ram_base = p['fo'], p['ram_base']
    fontbuf = load(name)
    ram_addr = ram_base + fo
    desc = fo + DESC_OFF

    print('=' * 70)
    print('%s  폰트 fo=0x%x  RAM=0x%08x  디스크립터=0x%x  (코드모듈 %s)'
          % (name, fo, ram_addr, desc, p['code']))

    # 폰트 sanity
    g0_blank = all(v == 0 for v in fontbuf[fo:fo + 32])
    tbl_anchor = None
    print('  폰트 글리프0 공백=%s' % g0_blank)
    if desc + 8 <= len(fontbuf):
        dram, dsz = struct.unpack_from('>II', fontbuf, desc)
        print('  디스크립터: RAM=0x%08x  size=0x%x (%s)'
              % (dram, dsz, 'OK' if dsz == DESC_OFF and dram == ram_addr else 'MISMATCH'))

    # 코드 모듈에서 상수 탐색
    codebuf = load(p['code']) if p['code'] != name else fontbuf
    addr_refs = find_be32(codebuf, ram_addr)
    print('  코드모듈에서 폰트주소 BE32 0x%08x 출현: %s'
          % (ram_addr, ', '.join('0x%x' % x for x in addr_refs)))

    # R4 로 폰트주소를 싣는 MOV.L 후보
    movls = movl_targets(codebuf)
    r4loads = [(a, tgt) for (a, reg, tgt) in movls
               if reg == 4 and tgt in addr_refs]
    print('  MOV.L Rn<-폰트주소 (reg별): ', end='')
    by_reg = {}
    for (a, reg, tgt) in movls:
        if tgt in addr_refs:
            by_reg.setdefault(reg, []).append(a)
    print(', '.join('R%d@[%s]' % (r, ','.join('0x%x' % x for x in v))
                    for r, v in sorted(by_reg.items())))

    # 크기 상수: R6 로 u16(=1832)을 싣는 MOV.W, 그 값 위치를 보고
    movws = movw_targets(codebuf)
    size_cands = []
    for (a, reg, tgt) in movws:
        if reg == 6 and tgt + 2 <= len(codebuf):
            val = struct.unpack_from('>H', codebuf, tgt)[0]
            if val == COUNT:
                size_cands.append((a, tgt, val))
    print('  MOV.W R6<-u16(=%d=0x%x) 후보:' % (COUNT, COUNT))
    for (a, tgt, val) in size_cands:
        # 근처에 R4<-폰트주소 로드가 있나?
        near = min((abs(a - ra) for ra, _ in r4loads), default=99999)
        # 같은 창에서 R5(VRAM dst) 로드 찾기
        r5 = None
        for (aa, reg, t5) in movls:
            if reg == 5 and abs(aa - a) <= 24 and t5 + 4 <= len(codebuf):
                r5 = struct.unpack_from('>I', codebuf, t5)[0]
        print('    명령 0x%x -> 크기상수 0x%x (값 0x%04x)  R4거리=%d  VRAM dst=%s'
              % (a, tgt, val, near, '0x%08x' % r5 if r5 else '?'))
    if not size_cands:
        print('    (없음 — R6 외 레지스터 또는 다른 인코딩일 수 있음)')
    return dict(name=name, ram_addr=ram_addr, desc=desc, addr_refs=addr_refs,
                r4loads=r4loads, size_cands=size_cands)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for m in ['MUSEUM', 'SAKUSEN', 'KEKKA', 'INTERM', 'GMDT']:
        analyze(m)
