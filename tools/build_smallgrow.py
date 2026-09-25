"""실험 — 소형 8x8 폰트를 229 -> 256 글리프로 늘릴 수 있는가.

배경: VRAM에 올라오는 소형 폰트는 정확히 229글리프였고, 그 근거로 폰트 데이터 **바로 뒤**에
      `(u32 RAM주소, u32 크기=0x1ca0=229x32)` 디스크립터가 있는 걸 찾았다(5개 모듈 전부).
      크기 필드를 키우면 인덱스 상한 256까지 27칸을 **기존 글리프를 하나도 안 건드리고** 얻는다.
      = 슬롯 재활용(다른 화면 파괴)을 아예 안 해도 된다.

1차 실험(GMDT만)은 **판독 불가**로 끝났다 — 실기에서 대조군조차 안 바뀌었다.
⇒ **병기도감(PSW222) 화면은 GMDT 표가 아니라 MUSEUM 표를 읽는다**가 확인됐다(부수 소득).
  크래시는 없었으므로 GMDT 확장 자체는 무해.

이번 빌드 = 두 모듈:
  GMDT   : 폰트가 파일 맨 끝 → **파일 확장**(+856 B, 마지막 섹터 슬랙 안, 섹터 수 불변)
           229는 디스크립터 8B를 물어 쓰레기 → 신규는 230부터.
  MUSEUM : 폰트가 파일 중간 → **모듈 내 제로런(0x8ea8~0x10768, 30,912 B)으로 재배치** 후 확장.
           디스크립터 RAM 주소도 갱신. 파일 크기·LBA 불변.

판독 (병기도감 → PSW222 상세, 무기 슬롯 4줄):
  1줄 rec2 `20㎜기관포`  = **실험군**(신규 인덱스 230~)
  2줄 rec1 `7.92㎜AA`   = **대조군**(기존 글리프만) — 이게 바뀌면 표 패치는 실렸다는 뜻
  3·4줄 rec0 `무장없음`  = 실험군
  → 대조군만 바뀌고 한글 자리가 빈칸 = 229가 코드 하드코딩(확장 불가) ❌
  → 둘 다 바뀜 = 확장 성공 ✅ (+26칸)
  → 전부 원문/깨짐 = 재배치 실패(폰트 주소를 코드가 따로 들고 있음) ❌
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

OLD_N, NEW_N = 229, 256
FIRST_NEW = 230          # 229는 GMDT에서 디스크립터를 물어 쓸 수 없다 → 두 모듈 모두 230부터
STRIDE = 8

PLANS = {
    'GMDT': dict(fo=0x28ef8, mode='extend', ram_base=0x208000,
                 table=0x74c4, nrec=437),
    'MUSEUM': dict(fo=0x109e8, mode='reloc', ram_base=0x06060000, new_fo=0xE760,
                   zero_run=(0x8ea8, 0x10768), table=0x90210, nrec=181),
}

# (레코드, 원문, 새 문자열, 대조군 여부)
EDITS = [
    (1,   '7.92㎜MG',      '7.92㎜AA',   True),    # 대조군: 기존 글리프만
    (2,   '20㎜キカンホウ',  '20㎜기관포',  False),
    (0,   'ブソウナシ',      '무장없음',    False),
    (3,   '30㎜キカンホウ',  '30㎜기관포',  False),
    (4,   '37㎜キカンホウ',  '37㎜기관포',  False),
    (5,   '20㎜ホウL55',    '20㎜포L55',  False),
    (13,  '75㎜ホウL24',    '75㎜포L24',  False),
    (27,  '105㎜ホウ',      '105㎜포',    False),
    (31,  '105㎜ヤホウ',    '105㎜야포',   False),
    (32,  '150㎜ヤホウ',    '150㎜야포',   False),
    (37,  'ロケットホウ',    '로켓포',      False),
    (39,  'ATライフル',     'AT소총',     False),
    (42,  'サブマシンガン',  '기관단총',    False),
    (43,  'ライフル',       '소총',       False),
    (44,  'トツゲキライフル', '돌격소총',    False),
    (49,  '85㎜AAホウ',     '85㎜대공포',  False),
    (84,  'バズーカ',       '바주카',      False),
    (124, '250㎏バクダン',  '250㎏폭탄',   False),
    (131, 'ショウイダン',    '소이탄',      False),
    (157, 'マシンガン',      '기관총',      False),
]


def slots():
    need = []
    for _, _, kr, _ in EDITS:
        for ch in kr:
            if '가' <= ch <= '힣' and ch not in need:
                need.append(ch)
    if FIRST_NEW + len(need) > NEW_N:
        raise SystemExit('신규 슬롯 부족: %d자 > %d칸' % (len(need), NEW_N - FIRST_NEW))
    return need, {ch: FIRST_NEW + i for i, ch in enumerate(need)}


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, 'rb')
    need, slot = slots()
    print('한글 %d자 -> 신규 인덱스 %d~%d' % (len(need), FIRST_NEW, FIRST_NEW + len(need) - 1))
    tiles = {ch: to_tile(glyph8(ch)) for ch in need}

    def enc(s):
        out = bytearray(slot[c] if c in slot else sf.REV[c] for c in s)
        if len(out) > STRIDE:
            raise SystemExit('길이 초과 %r' % s)
        return bytes(out).ljust(STRIDE, b'\x00')

    mods = {}
    dirpatch = []
    for m, p in PLANS.items():
        hits, rlba, rsize, _ = find_dirrec(f, m)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 레코드 %d개' % (m, len(hits)))
        _, lba, size, rec_off = hits[0]
        d = bytearray(read_range(f, lba, size))
        fo, desc = p['fo'], p['fo'] + OLD_N * 32
        ram, sz = struct.unpack_from('>II', d, desc)
        assert sz == OLD_N * 32, '%s 크기 필드 불일치' % m
        assert ram - fo == p['ram_base'], '%s RAM 베이스 불일치 (0x%x)' % (m, ram - fo)
        assert all(v == 0 for v in d[fo:fo + 32]), '%s 폰트0 공백 아님' % m
        assert sf.decode(d, p['table'], 8, stop=False).rstrip() == 'ブソウナシ', '%s 표 앵커' % m
        print('\n%-7s lba=%-6d %7d B  폰트 0x%x  디스크립터 0x%x (RAM 0x%08x)'
              % (m, lba, size, fo, desc, ram))

        new_size = size
        if p['mode'] == 'extend':
            assert desc + 8 == size, '%s 폰트+디스크립터가 파일 끝이 아님' % m
            new_size = fo + NEW_N * 32
            assert (size + USER - 1) // USER == (new_size + USER - 1) // USER, '%s 섹터 수 변동' % m
            d += bytearray(new_size - size)
            for ch, i in slot.items():
                d[fo + i * 32: fo + i * 32 + 32] = tiles[ch]
            struct.pack_into('>I', d, desc + 4, NEW_N * 32)
            print('        파일 확장 %d -> %d B, 크기 필드 -> 0x%x' % (size, new_size, NEW_N * 32))
            dirpatch.append((rlba, rsize, rec_off, None, new_size))
        else:
            nfo = p['new_fo']
            z0, z1 = p['zero_run']
            assert nfo % 32 == 0 and z0 <= nfo and nfo + NEW_N * 32 <= z1, '%s 재배치 자리 부적합' % m
            assert all(v == 0 for v in d[nfo:nfo + NEW_N * 32]), '%s 대상 구간이 0이 아님' % m
            d[nfo:nfo + OLD_N * 32] = d[fo:fo + OLD_N * 32]
            for ch, i in slot.items():
                d[nfo + i * 32: nfo + i * 32 + 32] = tiles[ch]
            struct.pack_into('>II', d, desc, p['ram_base'] + nfo, NEW_N * 32)
            print('        폰트 재배치 0x%x -> 0x%x, RAM 0x%08x, 크기 0x%x'
                  % (fo, nfo, p['ram_base'] + nfo, NEW_N * 32))

        for ridx, jp, kr, ctl in EDITS:
            if ridx >= p['nrec']:
                continue
            o = p['table'] + ridx * STRIDE
            cur = sf.decode(d, o, 8, stop=False).rstrip()
            if cur != jp:
                raise SystemExit('%s rec%d 원문 불일치 %r != %r' % (m, ridx, cur, jp))
            d[o:o + STRIDE] = enc(kr)
        print('        이름표 %d 레코드 교체' % sum(1 for e in EDITS if e[0] < p['nrec']))
        mods[m] = dict(lba=lba, data=d)

    # 루트 디렉터리 크기 필드
    rlba, rsize = dirpatch[0][0], dirpatch[0][1]
    rd = bytearray(read_range(f, rlba, rsize))
    for _, _, rec_off, _, ns in dirpatch:
        struct.pack_into('<I', rd, rec_off + 10, ns)
        struct.pack_into('>I', rd, rec_off + 14, ns)
    f.close()

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print('\nTrack01 원본에서 새로 복사 중 (610MB)...')
    shutil.copyfile(TRACK1, dst)
    touched = set()
    with open(dst, 'r+b') as w:
        blobs = [(v['lba'], v['data']) for v in mods.values()] + [(rlba, rd)]
        for lba_, data in blobs:
            for k in range(0, len(data), USER):
                sec = lba_ + k // USER
                w.seek(sec * RAW + HDR)
                w.write(bytes(data[k:k + USER]).ljust(USER, b'\x00')[:USER])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    json.dump({'plans': {k: {kk: (hex(vv) if isinstance(vv, int) else vv)
                             for kk, vv in v.items()} for k, v in PLANS.items()},
               'slots': slot, 'edits': [list(e) for e in EDITS]},
              open(os.path.join(OUT, 'smallgrow_plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
