# -*- coding: utf-8 -*-
"""소형폰트 한글화 본 빌더 (세션5).

smalltext.tsv(마스터) → 5모듈 폰트 240확장 + 한글 글리프 재정의 + 텍스트 재삽입.

슬롯: 한글 90음절 → 가나(63~143, 81) + 확장(230~239, 10). GMDT는 229가 디스크립터라
      확장 실질 10칸(230~239)이므로 전 모듈 공통으로 230~239만 사용. 기호는 안 씀(위험 회피).
      확장은 최소화(가장 드문 음절만) → 미검증 확장이 일부 모듈서 실패해도 피해 최소.

폰트 확장:
  GMDT   = extend (폰트가 파일끝) — 크기상수는 GAME 모듈 0x18930·0x6e3b4, 글리프는 GMDT.
  나머지 = reloc (폰트 중간) — 제로런으로 복사 후 주소상수·크기상수 갱신.

텍스트: 전부 length-locked. 고정표=제자리 8B(초과0, fit8 완료). 델리미터풀=필드 제자리+널패딩.

⚠️드라이런(기본)은 work/extract/ 모듈로 메모리 검증만. --write 로 ISO 기록.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
from hangul8comp import glyph8, to_tile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT = os.path.join(ROOT, 'work', 'extract')
TSV = os.path.join(ROOT, 'work', 'smalltext', 'smalltext.tsv')

OLD_N, NEW_N = 229, 240
FONT_BASE = {'GMDT': 0x208000, 'MUSEUM': 0x06060000, 'SAKUSEN': 0x06060000,
             'KEKKA': 0x06060000, 'INTERM': 0x06060000}
FONT_FO = {'GMDT': 0x28ef8, 'MUSEUM': 0x109e8, 'SAKUSEN': 0x1c9cc,
           'KEKKA': 0x17cb8, 'INTERM': 0x3ab40}

# 폰트 확장 설정
# ★재배치(reloc) 폐기: 제로런은 런타임 작업버퍼라 어느 위치든 폰트를 놓으면 깨지거나 크래시.
#   (실기: MUSEUM 0x8ec0=스크램블, 0xE760=검은화면). 대신:
#   GMDT = extend(파일끝 제자리, 실기성공) — 확장 8음절(GMDT만 사용).
#   MUSEUM/SAKUSEN/KEKKA = inplace(가나슬롯만 제자리 덮어쓰기, 확장·재배치 없음).
#     이들은 확장슬롯 음절을 안 쓴다(SAKUSEN 가설교→가설다리로 '교' 제거해 확정).
FONT = {
    'GMDT': dict(mode='extend', size_code=[('GAME', 0x18930), ('GAME', 0x6e3b4)]),
    'MUSEUM': dict(mode='inplace'),
    'SAKUSEN': dict(mode='inplace'),
    'KEKKA': dict(mode='inplace'),
}

# 텍스트 구조 (kind, offset, stride, count) — 고정폭. 풀은 별도.
STRIDE_TABLES = {
    'GMDT': [('names', 0x74c4, 8, 437)],
    'MUSEUM': [('weapons', 0x90210, 8, 181), ('units', 0x7e3c2, 0x52, 645)],
    'SAKUSEN': [('weapons', 0x542d8, 8, 181), ('places', 0x4eb96, 8, 270)],
    'KEKKA': [('weapons', 0x3af82, 8, 181)],
}


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return bytearray(f.read())


def load_tsv():
    rows = [l.rstrip('\n').split('\t') for l in open(TSV, encoding='utf-8')]
    return rows[0], rows[1:]


def assign_slots(rows):
    """한글 음절 빈도 집계 → 흔한 것=가나슬롯, 드문 것=확장(230~239, 최대10)."""
    from collections import Counter
    freq = Counter()
    for r in rows:
        if r[7]:
            for c in r[7]:
                if '가' <= c <= '힣':
                    freq[c] += 1
    syls = [c for c, _ in freq.most_common()]   # 빈도 내림차순
    kana_slots = list(range(63, 144))            # 81
    exp_slots = list(range(230, 240))            # 10
    if len(syls) > len(kana_slots) + len(exp_slots):
        raise SystemExit('한글 %d > 슬롯 %d' % (len(syls), len(kana_slots) + len(exp_slots)))
    slot = {}
    # 흔한 것부터 가나, 넘치면 드문 것을 확장
    n_exp = max(0, len(syls) - len(kana_slots))   # 확장 필요 개수
    common, rare = syls[:len(syls) - n_exp], syls[len(syls) - n_exp:]
    for i, c in enumerate(common):
        slot[c] = kana_slots[i]
    for i, c in enumerate(rare):
        slot[c] = exp_slots[i]
    return slot, n_exp


def make_encoder(slot):
    # 폰트에 없는 ASCII 대체: '-'→'ー'(154, 장음 대시), 공백은 0(빈 글리프)
    ALT = {'-': 'ー', ' ': None}
    def enc(s):
        out = bytearray()
        for c in s:
            if '가' <= c <= '힣':
                out.append(slot[c])
            elif c in sf.REV:
                out.append(sf.REV[c])
            elif c in ALT:
                out.append(0 if ALT[c] is None else sf.REV[ALT[c]])
            else:
                raise SystemExit('인코딩불가 문자 %r in %r' % (c, s))
        return bytes(out)
    return enc


def patch_font(mod, d, slot, tiles):
    """폰트 240확장 + 한글 글리프 삽입. 반환: (새 module bytes, 확장/재배치 로그, size_code 패치 for GAME)."""
    fo = FONT_FO[mod]
    cfg = FONT[mod]
    desc = fo + OLD_N * 32
    log = []
    game_patches = []   # [(off, val)] for GAME size codes

    def write_hangul(buf, base, kana_only=False):
        for c, i in slot.items():
            if kana_only and i >= OLD_N:   # 확장슬롯(230+)은 제자리 모드에서 쓰지 않음(폰트 뒤 데이터 보호)
                continue
            buf[base + i * 32: base + i * 32 + 32] = tiles[c]

    if cfg['mode'] == 'inplace':     # MUSEUM/SAKUSEN/KEKKA — 재배치·확장 없이 가나슬롯만 제자리
        write_hangul(d, fo, kana_only=True)
        log.append('inplace 가나슬롯 덮어쓰기 (재배치·확장 없음)')
    elif cfg['mode'] == 'extend':    # GMDT
        new_end = fo + NEW_N * 32
        if len(d) < new_end:
            d += bytearray(new_end - len(d))
        write_hangul(d, fo)          # 가나슬롯 덮어쓰기 + 230~239 신규 (229는 디스크립터라 slot에 없음)
        # 디스크립터 size 필드 (desc+4) → 240*32
        struct.pack_into('>I', d, desc + 4, NEW_N * 32)
        # size_code는 GAME 모듈 → 별도 반환
        for m, off in cfg['size_code']:
            game_patches.append((off, NEW_N * 32 // 4))
        log.append('extend %d글리프, GAME 크기상수 %d곳 갱신' % (NEW_N, len(cfg['size_code'])))
    else:                            # reloc
        nfo = cfg['zero']
        assert all(v == 0 for v in d[nfo:nfo + NEW_N * 32]), '%s 재배치 자리 0아님' % mod
        d[nfo:nfo + OLD_N * 32] = d[fo:fo + OLD_N * 32]   # 229글리프 복사
        write_hangul(d, nfo)                              # 한글 삽입(가나+230~239)
        new_addr = FONT_BASE[mod] + nfo
        for off in cfg['addr']:
            got = struct.unpack_from('>I', d, off)[0]
            assert got == FONT_BASE[mod] + fo, '%s 0x%x 폰트주소 아님(0x%08x)' % (mod, off, got)
            struct.pack_into('>I', d, off, new_addr)
        struct.pack_into('>I', d, cfg['size_ref'], NEW_N * 32)
        for m, off in cfg['size_code']:
            assert struct.unpack_from('>H', d, off)[0] == OLD_N * 32 // 4, \
                '%s 크기상수 0x%x 불일치' % (mod, off)
            struct.pack_into('>H', d, off, NEW_N * 32 // 4)
        log.append('reloc 0x%x->0x%x, 주소%d곳·크기상수%d곳' %
                   (fo, nfo, len(cfg['addr']), len(cfg['size_code'])))
    return d, log, game_patches


SEP = {0, 0xfd, 0xfe, 0xff}


POOL_KINDS = {'ui', 'terrain'}


def field_widths(byrow):
    """각 행의 재삽입 가능 폭. 고정표=ln(8/8). 델리미터풀=다음 필드까지 간격-1(널1 보존)."""
    widths = {}
    # 풀은 (mod,kind)별로 오프셋 정렬해 간격 계산
    from collections import defaultdict
    pools = defaultdict(list)
    for i, r in enumerate(byrow):
        if r[1] in POOL_KINDS:
            pools[r[1]].append((int(r[2], 16), i, int(r[3])))
        else:
            widths[i] = int(r[3])           # 고정표: ln (8)
    for kind, lst in pools.items():
        lst.sort()
        for j, (off, i, ln) in enumerate(lst):
            if j + 1 < len(lst):
                widths[i] = lst[j + 1][0] - off - 1   # 다음 필드까지 -1 (널 최소1)
            else:
                widths[i] = ln                        # 마지막 필드: 원본 길이(확장 안함)
    return widths


def patch_text(mod, d, byrow, enc):
    """length-locked 재삽입. 고정표=제자리 8B, 풀=필드~다음필드 간격 내 널패딩."""
    widths = field_widths(byrow)
    n = 0
    for i, r in enumerate(byrow):
        _, kind, off, ln, jp, hx, idx, kr = r
        if not kr:
            continue
        off = int(off, 16)
        width = widths[i]
        b = enc(kr)
        if len(b) > width:
            raise SystemExit('%s %s@0x%x 초과 %d>%d (%r->%r)' % (mod, kind, off, len(b), width, jp, kr))
        raw = bytes.fromhex(hx)
        assert d[off:off + len(raw)] == raw, '%s @0x%x 원문 불일치' % (mod, off)
        # 원본 필드 길이(len(raw))만큼은 반드시 덮고, 남는 폭은 널로(널런 연장)
        span = max(len(raw), len(b))
        d[off:off + span] = b.ljust(span, b'\x00')
        n += 1
    return n


def build(write=False):
    header, rows = load_tsv()
    slot, n_exp = assign_slots(rows)
    enc = make_encoder(slot)
    tiles = {c: to_tile(glyph8(c)) for c in slot}
    print('한글 %d음절 → 가나 %d + 확장 %d(230~%d)' %
          (len(slot), len(slot) - n_exp, n_exp, 229 + n_exp))

    # 모듈별 행 그룹
    from collections import defaultdict
    bymod = defaultdict(list)
    for r in rows:
        bymod[r[0]].append(r)

    modules = {}
    game_patches = []
    # INTERM 제외: 소형폰트 텍스트 0 → 폰트 안 건드림(미발견 텍스트 있어도 가나 유지=안전)
    for mod in ['GMDT', 'MUSEUM', 'SAKUSEN', 'KEKKA']:
        d = load(mod)
        d, log, gp = patch_font(mod, d, slot, tiles)
        game_patches += gp
        n = patch_text(mod, d, bymod.get(mod, []), enc)
        modules[mod] = d
        print('  %-8s 폰트[%s] 텍스트 %d필드' % (mod, '; '.join(log), n))

    # GAME 모듈 크기상수 (GMDT 확장용)
    if game_patches:
        g = load('GAME')
        for off, val in game_patches:
            assert struct.unpack_from('>H', g, off)[0] == OLD_N * 32 // 4, 'GAME 크기상수 0x%x 불일치' % off
            struct.pack_into('>H', g, off, val)
        modules['GAME'] = g
        print('  GAME     크기상수 %d곳 갱신 (GMDT 확장)' % len(game_patches))

    # 검증: 재삽입 텍스트 되읽기(패치된 코드표로), 폰트 글리프 되읽기
    verify(modules, slot, rows, enc)
    print('\n검증 통과.')
    if not write:
        print('드라이런 — ISO 미기록 (--write 로 기록).')
        return modules, slot
    write_iso(modules)
    return modules, slot


def verify(modules, slot, rows, enc):
    # 코드표 역: 슬롯→한글, 0=공백(고정폭 읽기라 종료 아님)
    rev = {v: k for k, v in slot.items()}
    def dec(b):
        return ''.join(rev.get(x, sf.CHARS.get(x, '<%02x>' % x)) for x in b)
    from collections import defaultdict
    bymod = defaultdict(list)
    for r in rows:
        bymod[r[0]].append(r)
    bad = 0
    for r in rows:
        if not r[7]:
            continue
        # kr 라운드트립: enc→dec 가 kr 과 같아야 ('-'→ー, ' '→공백 정규화 반영)
        norm = r[7].replace('-', 'ー')
        rt = dec(enc(r[7])).rstrip()
        if rt != norm.rstrip():
            bad += 1
            if bad <= 8:
                print('  ❌라운드트립 %s %r -> %r' % (r[1], r[7], rt))
    if bad:
        raise SystemExit('라운드트립 불일치 %d개' % bad)
    # 폰트 글리프: 각 모듈 폰트에 한글 타일이 들어갔나 (reloc은 zero, extend는 fo)
    for mod, d in modules.items():
        if mod == 'GAME':
            continue
        inplace = FONT[mod]['mode'] == 'inplace'
        base = FONT[mod].get('zero', FONT_FO[mod])
        for c, i in slot.items():
            if inplace and i >= OLD_N:     # inplace는 확장슬롯 미기록
                continue
            g = d[base + i * 32: base + i * 32 + 32]
            if g != to_tile(glyph8(c)):
                raise SystemExit('%s 글리프 슬롯%d(%s) 불일치' % (mod, i, c))


def write_iso(modules):
    import shutil
    from isoread import TRACK1, RAW, HDR, USER, read_range
    from build_reloc import find_dirrec
    import ecc
    OUT_ISO = r'F:\hospi\roms\ss roms\aww'
    f = open(TRACK1, 'rb')
    plan = []          # (lba, data), dir updates
    dirpatch = []
    for mod, d in modules.items():
        hits, rlba, rsize, _ = find_dirrec(f, mod)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 %d개' % (mod, len(hits)))
        _, lba, size, rec_off = hits[0]
        orig = read_range(f, lba, size)
        if len(d) != len(orig):
            # 파일 확장(GMDT) — 섹터 수 검사 + 디렉터리 size 갱신
            assert (size + USER - 1) // USER == (len(d) + USER - 1) // USER, '%s 섹터수 변동' % mod
            dirpatch.append((rlba, rsize, rec_off, len(d)))
        plan.append((mod, lba, bytes(d)))
    # 루트 디렉터리 size 필드
    rd = None
    if dirpatch:
        rlba, rsize = dirpatch[0][0], dirpatch[0][1]
        rd = bytearray(read_range(f, rlba, rsize))
        for _, _, rec_off, ns in dirpatch:
            struct.pack_into('<I', rd, rec_off + 10, ns)
            struct.pack_into('>I', rd, rec_off + 14, ns)
    f.close()

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print('\nTrack01 복사 중 (610MB)...')
    shutil.copyfile(TRACK1, dst)
    touched = set()
    with open(dst, 'r+b') as w:
        blobs = [(lba, data) for _, lba, data in plan]
        if rd is not None:
            blobs.append((dirpatch[0][0], bytes(rd)))
        for lba, data in blobs:
            for k in range(0, len(data), USER):
                sec = lba + k // USER
                w.seek(sec * RAW + HDR)
                w.write(bytes(data[k:k + USER]).ljust(USER, b'\x00')[:USER])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build(write='--write' in sys.argv)
