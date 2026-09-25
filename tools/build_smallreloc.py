"""실험 3 — 소형 8x8 폰트를 **재배치**할 수 있는가 (+ 크기 필드가 업로드량을 지배하는가).

실험 2가 실패한 이유: 폰트 주소 상수가 MUSEUM에 **두 곳**(0x2460 리터럴 풀, 0x12688) 있는데
디스크립터 한 곳만 고쳤다. 0x2460 주변은 `0x25E0xxxx`(VDP2 VRAM) 주소가 즐비한 SH-2 리터럴 풀 =
업로드 루틴이 실제로 읽는 상수. 그래서 재배치가 아예 일어나지 않았다.
또 하나: 원래 자리 폰트를 그대로 둬서 **재배치본과 원본의 기존 글리프가 동일** → 화면만 봐선
「재배치 실패」와 「크기 무시」가 구분이 안 됐다.

이번 설계 (MUSEUM 단독, 변수 하나):
  · 폰트를 모듈 내 제로런(0x8ea8~0x10768)의 0xE760으로 복사.
  · **주소 상수 두 곳 모두** 새 RAM 주소로 갱신. 크기 필드도 0x2000으로.
  · ★**재배치본에만 표식 글리프** — 슬롯 11('A')을 알아볼 수 없는 무늬로 바꾼다.
    원래 자리(0x109e8)는 **원본 그대로** 둔다 → 화면의 'A'가 무늬면 재배치본을 읽은 것.
  · 한글 23자는 신규 인덱스 230~252 (재배치본에만).
  · GMDT 포함 나머지 모듈은 전부 원본.

판독 (병기도감 → PSW222 상세, 무기 슬롯 2줄 `7.92㎜AA`):
  `7.92㎜▨▨` + 1·3·4줄 한글 = 재배치 ✅ · 크기 필드 ✅  → 26칸 확보
  `7.92㎜▨▨` + 한글 자리 빈칸 = 재배치 ✅ · 크기는 코드 어딘가 ❌ → SH-2 디스어셈 필요
  `7.92㎜AA`                  = 재배치 ❌ (주소를 또 다른 곳에서 들고 있음)
  글자 전체가 깨짐/크래시       = 재배치 자리가 잘못됨(제로런이 런타임 작업영역)
  ※ 유닛명 리스트의 `PzKwⅠA` 등 'A'도 함께 무늬로 바뀌므로 판독면이 넓다.
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from build_reloc import find_dirrec
import ecc
import smallfont as sf
from hangul8comp import glyph8, to_tile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build')
OUT_ISO = r'F:\hospi\roms\ss roms\aww'

MOD = 'MUSEUM'
RAM_BASE = 0x06060000
FO, NFO = 0x109e8, 0xE760
ZERO_RUN = (0x8ea8, 0x10768)
ADDR_REFS = [0x2460, 0x12688]      # BE32 0x060709e8 이 들어있는 두 곳
SIZE_REF = 0x1268c                 # BE32 0x1ca0 (파일 끝 디스크립터 — 업로드량과 무관함이 실기로 확인됨)
# ★진짜 크기 상수: 0x2396 의 JSR(R4=src, R5=VRAM dst, R6=롱워드 개수) 에서
#   R6 은 0x238e `MOV.W @(0x35*2,PC),R6` 로 **0x23FC 의 u16** 에서 온다. 값 0x0728 = 1832 = 7328/4.
SIZE_CODE = 0x23FC
# ⚠️VRAM 타일 229~243 은 비어 있으나 **244부터는 다른 것이 쓰고 있다**(세이브스테이트 확인).
#   그래서 240글리프(=VRAM 0x1e00)까지만 늘린다 → 신규 슬롯 229~239, 11칸.
OLD_N, NEW_N, FIRST_NEW = 229, 240, 229
TABLE, NREC, STRIDE = 0x90210, 181, 8

MARKER_SLOT = 11                   # 'A'
MARKER = ['########',
          '#......#',
          '#.####.#',
          '#.#..#.#',
          '#.####.#',
          '#......#',
          '########',
          '........']

# 신규 슬롯이 11칸뿐이라 **고유 음절 11자**(무장없음기관포소총대공)로만 조합했다.
EDITS = [
    (1,   '7.92㎜MG',      '7.92㎜AA'),    # 대조군: 기존 글리프만 (여기의 A가 표식이 된다)
    (2,   '20㎜キカンホウ',  '20㎜기관포'),
    (0,   'ブソウナシ',      '무장없음'),
    (3,   '30㎜キカンホウ',  '30㎜기관포'),
    (4,   '37㎜キカンホウ',  '37㎜기관포'),
    (5,   '20㎜ホウL55',    '20㎜포L55'),
    (13,  '75㎜ホウL24',    '75㎜포L24'),
    (27,  '105㎜ホウ',      '105㎜포'),
    (39,  'ATライフル',     'AT소총'),
    (43,  'ライフル',       '소총'),
    (49,  '85㎜AAホウ',     '85㎜대공포'),
    (157, 'マシンガン',      '기관총'),
]


def slots():
    need = []
    for _, _, kr in EDITS:
        for ch in kr:
            if '가' <= ch <= '힣' and ch not in need:
                need.append(ch)
    if FIRST_NEW + len(need) > NEW_N:
        raise SystemExit('신규 슬롯 부족')
    return need, {ch: FIRST_NEW + i for i, ch in enumerate(need)}


def marker_tile():
    return to_tile([[1 if c == '#' else 0 for c in row] for row in MARKER])


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, 'rb')
    hits, rlba, rsize, _ = find_dirrec(f, MOD)
    if len(hits) != 1:
        raise SystemExit('%s 디렉터리 레코드 %d개' % (MOD, len(hits)))
    _, lba, size, _ = hits[0]
    d = bytearray(read_range(f, lba, size))
    f.close()
    print('%s lba=%d %d B' % (MOD, lba, size))

    old_addr = RAM_BASE + FO
    new_addr = RAM_BASE + NFO
    for off in ADDR_REFS:
        got = struct.unpack_from('>I', d, off)[0]
        assert got == old_addr, '0x%x 에 폰트주소가 없다 (0x%08x)' % (off, got)
    assert struct.unpack_from('>I', d, SIZE_REF)[0] == OLD_N * 32, '크기 필드 불일치'
    assert struct.unpack_from('>H', d, SIZE_CODE)[0] == OLD_N * 32 // 4, \
        '코드 크기 상수 불일치 (0x%04x)' % struct.unpack_from('>H', d, SIZE_CODE)[0]
    assert all(v == 0 for v in d[FO:FO + 32]), '폰트0 공백 아님'
    assert sf.decode(d, TABLE, 8, stop=False).rstrip() == 'ブソウナシ', '표 앵커 불일치'
    z0, z1 = ZERO_RUN
    assert NFO % 32 == 0 and z0 <= NFO and NFO + NEW_N * 32 <= z1, '재배치 자리 부적합'
    assert all(v == 0 for v in d[NFO:NFO + NEW_N * 32]), '대상 구간이 0이 아님'

    # --- 재배치본 만들기 (원래 자리는 손대지 않는다) ---
    d[NFO:NFO + OLD_N * 32] = d[FO:FO + OLD_N * 32]
    d[NFO + MARKER_SLOT * 32: NFO + MARKER_SLOT * 32 + 32] = marker_tile()
    need, slot = slots()
    for ch, i in slot.items():
        d[NFO + i * 32: NFO + i * 32 + 32] = to_tile(glyph8(ch))
    print('폰트 0x%x -> 0x%x 복사, 표식 슬롯 %d(%s), 한글 %d자 -> %d~%d'
          % (FO, NFO, MARKER_SLOT, sf.CHARS[MARKER_SLOT], len(need), FIRST_NEW,
             FIRST_NEW + len(need) - 1))

    for off in ADDR_REFS:
        struct.pack_into('>I', d, off, new_addr)
    struct.pack_into('>I', d, SIZE_REF, NEW_N * 32)
    print('주소 상수 0x%08x -> 0x%08x (%d곳: %s)'
          % (old_addr, new_addr, len(ADDR_REFS), ', '.join(hex(o) for o in ADDR_REFS)))
    struct.pack_into('>H', d, SIZE_CODE, NEW_N * 32 // 4)
    print('크기 필드(디스크립터) 0x%x -> 0x%x' % (OLD_N * 32, NEW_N * 32))
    print('★크기 상수(코드 0x%x) 0x%04x -> 0x%04x  (롱워드, 글리프 %d -> %d)'
          % (SIZE_CODE, OLD_N * 32 // 4, NEW_N * 32 // 4, OLD_N, NEW_N))

    def enc(s):
        out = bytearray(slot[c] if c in slot else sf.REV[c] for c in s)
        if len(out) > STRIDE:
            raise SystemExit('길이 초과 %r' % s)
        return bytes(out).ljust(STRIDE, b'\x00')

    print()
    for ridx, jp, kr in EDITS:
        if ridx >= NREC:
            continue
        o = TABLE + ridx * STRIDE
        cur = sf.decode(d, o, 8, stop=False).rstrip()
        if cur != jp:
            raise SystemExit('rec%d 원문 불일치 %r != %r' % (ridx, cur, jp))
        d[o:o + STRIDE] = enc(kr)
        print('  rec%-4d %-16s -> %-10s %s' % (ridx, jp, kr, d[o:o + STRIDE].hex()))

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print('\nTrack01 원본에서 새로 복사 중 (610MB)...')
    shutil.copyfile(TRACK1, dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for k in range(0, len(d), USER):
            sec = lba + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(d[k:k + USER]).ljust(USER, b'\x00')[:USER])
            touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    json.dump({'module': MOD, 'old_addr': hex(old_addr), 'new_addr': hex(new_addr),
               'addr_refs': [hex(o) for o in ADDR_REFS], 'size_ref': hex(SIZE_REF),
               'marker_slot': MARKER_SLOT, 'slots': slot,
               'edits': [list(e) for e in EDITS]},
              open(os.path.join(OUT, 'smallreloc_plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
