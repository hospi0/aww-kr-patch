"""소형 폰트(8x8) 한글 PoC 빌드 — 무기명 일부를 한글로.

대상 = 8x8 소형 폰트와 그 이름 테이블(고정폭 8바이트). 세션4 발굴분.
  폰트  : GMDT 0x28ef8 / MUSEUM 0x109e8 / SAKUSEN 0x1c9cc / KEKKA 0x17cb8 / INTERM 0x3ab40
  이름표: GMDT 0x74c4 / MUSEUM 0x90210 / SAKUSEN 0x542d8 / KEKKA 0x3af82  (437 x 8B)

설계(이분 실험):
  ★한글은 **원본이 안 쓰는 소문자 슬롯에만** 심는다. 가나·숫자·기호 글리프는 한 바이트도 안 건드리므로
   다른 화면이 깨질 여지가 없다 — 무기 슬롯에 한글이 뜨면 그건 우리가 넣은 것이 확실하다.
  ★레코드는 고정 8바이트라 length-locked. 파일 크기·LBA 불변.
"""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
import ecc
import smallfont as sf
from hangul8comp import glyph8, to_tile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build')
OUT_ISO = r'F:\hospi\roms\ss roms\aww'

FONT_OFF = {'GMDT': 0x28ef8, 'MUSEUM': 0x109e8, 'SAKUSEN': 0x1c9cc,
            'KEKKA': 0x17cb8, 'INTERM': 0x3ab40}
# (오프셋, 레코드 수). ★사본마다 길이가 다르다 — GMDT만 437개(무기181 + 지형11 + 지명245)이고
#  나머지 3벌은 무기명 181개까지만 들고 있다(레코드 181부터 GMDT와 내용이 갈린다).
TABLE_OFF = {'GMDT': (0x74c4, 437), 'MUSEUM': (0x90210, 181),
             'SAKUSEN': (0x542d8, 181), 'KEKKA': (0x3af82, 181)}
STRIDE = 8

# 원본 이름표가 한 번도 안 쓰는 소문자 슬롯 (census 로 재확인한다)
FREE_SLOTS = [38, 39, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52,
              53, 54, 55, 57, 58, 59, 60, 61, 62]

# (레코드 index, 원문, 한글)  — 난이도 스펙트럼을 일부러 섞었다
EDITS = [
    (0,   'ブソウナシ',      '무장없음'),
    (2,   '20㎜キカンホウ',  '20㎜기관포'),
    (3,   '30㎜キカンホウ',  '30㎜기관포'),
    (4,   '37㎜キカンホウ',  '37㎜기관포'),
    (5,   '20㎜ホウL55',    '20㎜포L55'),
    (13,  '75㎜ホウL24',    '75㎜포L24'),
    (27,  '105㎜ホウ',      '105㎜포'),
    (31,  '105㎜ヤホウ',    '105㎜야포'),
    (32,  '150㎜ヤホウ',    '150㎜야포'),
    (37,  'ロケットホウ',    '로켓포'),
    (39,  'ATライフル',     'AT소총'),
    (42,  'サブマシンガン',  '기관단총'),
    (43,  'ライフル',       '소총'),
    (44,  'トツゲキライフル', '돌격소총'),
    (49,  '85㎜AAホウ',     '85㎜대공포'),
    (84,  'バズーカ',       '바주카'),
    (124, '250㎏バクダン',  '250㎏폭탄'),   # ㎏은 합자 글리프 1칸
    (131, 'ショウイダン',    '소이탄'),
    (157, 'マシンガン',      '기관총'),
]


def entries(path):
    out = [(lba, size) for p, lba, size in files(skip_media=False) if p == path]
    if not out:
        raise SystemExit('no file ' + path)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, 'rb')
    mods = {}
    for m in FONT_OFF:
        ents = entries('/' + m)
        lba, size = ents[0]
        mods[m] = dict(lba=lba, size=size, ents=ents, data=bytearray(read_range(f, lba, size)))
        print('%-8s lba=%-7d %8d B  (디렉터리 엔트리 %d벌)' % (m, lba, size, len(ents)))

    # --- 0. 원본 검증: 폰트/테이블 앵커가 맞는가 ---
    for m, off in FONT_OFF.items():
        assert all(v == 0 for v in mods[m]['data'][off:off + 32]), m + ' 폰트0이 공백이 아님'
    for m, (off, _) in TABLE_OFF.items():
        assert sf.decode(mods[m]['data'], off, 8, stop=False).rstrip() == 'ブソウナシ', m + ' 테이블 앵커 불일치'

    # --- 1. 필요한 음절 수집 + 슬롯 배정 ---
    need = []
    for _, _, kr in EDITS:
        for ch in kr:
            if '가' <= ch <= '힣' and ch not in need:
                need.append(ch)
    print('\n필요 고유 음절 %d자: %s' % (len(need), ''.join(need)))
    if len(need) > len(FREE_SLOTS):
        raise SystemExit('슬롯 부족: %d > %d' % (len(need), len(FREE_SLOTS)))

    # ★검출기 자기검증: 고른 슬롯이 4벌 테이블 어디에도 안 쓰이는지 실제로 확인
    for m, (off, nrec) in TABLE_OFF.items():
        tab = mods[m]['data'][off:off + nrec * STRIDE]
        for s in FREE_SLOTS[:len(need)]:
            if s in tab:
                raise SystemExit('슬롯 %d(%s)이 %s 테이블에서 사용중' % (s, sf.CHARS.get(s), m))
    slot = {ch: FREE_SLOTS[i] for i, ch in enumerate(need)}
    print('배정:', ', '.join('%s->%d(%s)' % (c, slot[c], sf.CHARS.get(slot[c])) for c in need))

    # --- 2. 폰트에 한글 글리프 심기 (5벌 전부) ---
    tiles = {ch: to_tile(glyph8(ch)) for ch in need}
    for m, fo in FONT_OFF.items():
        for ch, idx in slot.items():
            mods[m]['data'][fo + idx * 32: fo + idx * 32 + 32] = tiles[ch]

    # --- 3. 이름표 교체 (4벌 전부, length-locked) ---
    def enc(s):
        out = bytearray()
        for ch in s:
            if ch in slot:
                out.append(slot[ch])
            elif ch in sf.REV:
                out.append(sf.REV[ch])
            else:
                raise SystemExit('인코딩 불가 %r in %r' % (ch, s))
        if len(out) > STRIDE:
            raise SystemExit('길이 초과 %r: %d > %d' % (s, len(out), STRIDE))
        return bytes(out).ljust(STRIDE, b'\x00')

    print()
    for ridx, jp, kr in EDITS:
        b = enc(kr)
        for m, (off, nrec) in TABLE_OFF.items():
            if ridx >= nrec:
                continue
            o = off + ridx * STRIDE
            cur = sf.decode(mods[m]['data'], o, 8, stop=False).rstrip()
            if cur != jp:
                raise SystemExit('%s rec%d 원문 불일치: %r != %r' % (m, ridx, cur, jp))
            mods[m]['data'][o:o + STRIDE] = b
        print('  rec%-4d %-16s -> %-10s %s' % (ridx, jp, kr, b.hex()))

    # --- 4. ISO 쓰기 ---
    # ★단일 변수 유지: 항상 원본에서 새로 복사한다. 이전 탐침본 위에 얹으면
    #  실기에서 뭐가 원인인지 못 가른다([[feedback_kr_patch_verification]] 이분 실험).
    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print('\nTrack01 원본에서 새로 복사 중 (610MB)...')
    shutil.copyfile(TRACK1, dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for m, d in mods.items():
            for lba, size in d['ents']:          # 디렉터리 엔트리가 여러 벌이면 전부
                for k in range(0, size, USER):
                    sec = lba + k // USER
                    w.seek(sec * RAW + HDR)
                    w.write(bytes(d['data'][k:k + USER]).ljust(USER, b'\x00')[:USER])
                    touched.add(sec)
        print('\n쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    f.close()

    json.dump({'slots': slot, 'font_off': {k: hex(v) for k, v in FONT_OFF.items()},
               'table_off': {k: [hex(v[0]), v[1]] for k, v in TABLE_OFF.items()},
               'edits': [[i, jp, kr] for i, jp, kr in EDITS]},
              open(os.path.join(OUT, 'small_poc_plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
