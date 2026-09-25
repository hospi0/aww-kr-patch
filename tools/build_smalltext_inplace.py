# -*- coding: utf-8 -*-
"""소형폰트 한글 **제자리(in-place) 재빌드** — 확장슬롯 제거판 (세션11).

왜 새로 만들었나 — ⚠️**`build_smalltext.py --write`는 지금 쓰면 안 된다.**
  그 도구의 `write_iso()`는 `shutil.copyfile(TRACK1, dst)`로 **원본 ISO를 F:에 통째로 덮어쓴 뒤**
  소형폰트 모듈만 다시 쓴다. 세션5 당시엔 다른 패치가 없어 괜찮았지만, 지금 실행하면
  세션6~11의 모든 작업(map-move·names16·gamepool·ui16·missions16·typevals·第·버튼 코드주입 등)이
  **전부 소멸한다.** ⇒ 이 도구는 **현재 F: ISO에서 모듈을 읽어** 폰트·텍스트만 고치고
  **바뀐 바이트만 제자리 기록**하므로 기존 패치가 보존된다.

무엇을 고치나 — **확장슬롯(230~239) 완전 제거**:
  세션5는 한글 89음절이라 8개를 확장슬롯에 넣고 크기상수를 240글리프(1920)로 올렸는데,
  **모듈은 229글리프분(175,008B)뿐**이라 업로드가 뒤 352B를 **GMDT 뒤 RAM 쓰레기**에서 읽었다.
  그 쓰레기가 **맵마다 달라서** 1번맵은 멀쩡하고 다른 맵은 HUD 위아래로 쓰레기 띠가 떴다.
  (정상/깨짐 세이브스테이트 VRAM 대조로 글리프 229~239만 다름을 확인 — 16×16 폰트는 차이 0.)
  ⇒ 단어 6개를 재작성해 **81음절**로 줄여 가나슬롯(63~143)만 쓰고,
     **크기상수·디스크립터를 229로 복원**해 모듈 밖을 안 읽게 한다.

재작성(사용자 확정): 착륙→착지 · 하늘→상공 · 더미→없음 · 만안도로→항구도로 ·
                    작전도→지도 · 보충→충원   (설원·바다·호수·대하는 유지)

빌드: python tools/build_smalltext_inplace.py            드라이런(검증만)
      python tools/build_smalltext_inplace.py --write     F: ISO 제자리 기록
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import build_smalltext as S
import smallfont as sf
from hangul8comp import glyph8, to_tile
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
MODS = ['GMDT', 'MUSEUM', 'SAKUSEN', 'KEKKA']
SIZE_CODE = [('GAME', 0x18930), ('GAME', 0x6e3b4)]   # 세션5가 1920으로 올린 곳 → 1832로 복원


def patch_text_inplace(mod, d, byrow, enc):
    """`S.patch_text`와 동일하되 **원문 JP assert를 뺀다** — F: ISO엔 이미 한글(옛 배정)이 들어있다.

    ★슬롯 재배정이라 글자 수는 그대로이고 바이트 값만 바뀌므로 span 계산은 원본과 동일하다
      (span = max(원문 바이트수, 새 인코딩 길이)). 유일하게 짧아진 작전도(3)→지도(2)도
      원문 サクセンズ가 5바이트라 span 5로 같아 잔재가 남지 않는다.
    """
    widths = S.field_widths(byrow)
    n = 0
    for i, r in enumerate(byrow):
        _, kind, off, ln, jp, hx, idx, kr = r
        if not kr:
            continue
        off = int(off, 16)
        b = enc(kr)
        if len(b) > widths[i]:
            raise SystemExit('%s %s@0x%x 초과 %d>%d (%r->%r)'
                             % (mod, kind, off, len(b), widths[i], jp, kr))
        raw = bytes.fromhex(hx)
        span = max(len(raw), len(b))
        d[off:off + span] = b.ljust(span, b'\x00')
        n += 1
    return n


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytearray(out)


def main():
    write = '--write' in sys.argv
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    header, rows = S.load_tsv()
    slot, n_exp = S.assign_slots(rows)
    if n_exp:
        raise SystemExit('★확장슬롯 %d개 필요 — 81음절 초과. 단어 재작성이 덜 됨.' % n_exp)
    if max(slot.values()) >= S.OLD_N:
        raise SystemExit('★슬롯 %d >= %d — 확장영역 침범' % (max(slot.values()), S.OLD_N))
    print('한글 %d음절 → 가나슬롯 %d~%d (확장슬롯 미사용 ✓)'
          % (len(slot), min(slot.values()), max(slot.values())))

    enc = S.make_encoder(slot)
    tiles = {c: to_tile(glyph8(c)) for c in slot}

    from collections import defaultdict
    bymod = defaultdict(list)
    for r in rows:
        bymod[r[0]].append(r)

    # GMDT도 inplace로 — 확장/파일확대 금지
    for m in MODS:
        S.FONT[m] = dict(mode='inplace')

    f = open(dst, 'rb')
    plans = []          # (mod, lba, [(off, old, new)])
    for mod in MODS:
        hits, _, _, _ = find_dirrec(f, mod)
        _, lba, size, _ = hits[0]
        cur = read_file(f, lba, size)
        d = bytearray(cur)
        d, log, gp = S.patch_font(mod, d, slot, tiles)
        n = patch_text_inplace(mod, d, bymod.get(mod, []), enc)
        if len(d) != len(cur):
            raise SystemExit('%s 크기 변동 %d→%d — inplace 위반' % (mod, len(cur), len(d)))
        # GMDT 디스크립터 size 복원 (240*32 → 229*32)
        if mod == 'GMDT':
            desc = S.FONT_FO[mod] + S.OLD_N * 32
            struct.pack_into('>I', d, desc + 4, S.OLD_N * 32)
        diffs = [(i, bytes(cur[i:i + 1]), bytes(d[i:i + 1]))
                 for i in range(len(cur)) if cur[i] != d[i]]
        plans.append((mod, lba, diffs))
        print('  %-8s 텍스트 %3d필드, 바뀐 바이트 %d' % (mod, n, len(diffs)))

    # GAME 크기상수 복원 1920 → 1832
    hits, _, _, _ = find_dirrec(f, 'GAME')
    _, glba, gsize, _ = hits[0]
    gcur = read_file(f, glba, gsize)
    gdiffs = []
    for _, off in SIZE_CODE:
        v = struct.unpack_from('>H', gcur, off)[0]
        want = S.OLD_N * 32 // 4
        if v != want:
            nb = struct.pack('>H', want)
            for k in range(2):
                gdiffs.append((off + k, bytes(gcur[off + k:off + k + 1]), nb[k:k + 1]))
        print('  GAME 크기상수 0x%06x: %d → %d' % (off, v, want))
    plans.append(('GAME', glba, gdiffs))
    f.close()

    total = sum(len(p[2]) for p in plans)
    print('\n합계 %d바이트 제자리 변경' % total)
    if not write:
        print('드라이런 — ISO 미기록 (--write).')
        return

    touched = set()
    with open(dst, 'r+b') as w:
        for mod, lba, diffs in plans:
            for off, old, new in diffs:
                sec = lba + off // USER
                pos = sec * RAW + HDR + off % USER
                w.seek(pos)
                if w.read(1) != old:
                    raise SystemExit('%s @0x%x 대조 실패' % (mod, off))
                w.seek(pos)
                w.write(new)
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    verify(dst, slot, rows, enc, tiles)


def verify(dst, slot, rows, enc, tiles):
    """독립 되읽기 — 텍스트 라운드트립 + 폰트 글리프 + 크기상수 + EDC/ECC."""
    rev = {v: k for k, v in slot.items()}
    bad = 0
    with open(dst, 'rb') as r:
        mods = {}
        for mod in MODS + ['GAME']:
            hits, _, _, _ = find_dirrec(r, mod)
            _, lba, size, _ = hits[0]
            mods[mod] = (lba, read_file(r, lba, size))
        # 폰트 글리프
        for mod in MODS:
            lba, d = mods[mod]
            fo = S.FONT_FO[mod]
            for c, i in slot.items():
                if bytes(d[fo + i * 32:fo + i * 32 + 32]) != tiles[c]:
                    bad += 1
                    print('  ❌%s 글리프 %s(slot%d) 불일치' % (mod, c, i))
                    break
        # 크기상수 · 디스크립터
        _, g = mods['GAME']
        for _, off in SIZE_CODE:
            if struct.unpack_from('>H', g, off)[0] != S.OLD_N * 32 // 4:
                bad += 1
                print('  ❌GAME 크기상수 0x%x' % off)
        _, gm = mods['GMDT']
        desc = S.FONT_FO['GMDT'] + S.OLD_N * 32
        if struct.unpack_from('>I', gm, desc + 4)[0] != S.OLD_N * 32:
            bad += 1
            print('  ❌GMDT 디스크립터 size')
        # 텍스트 라운드트립
        n = 0
        for rw in rows:
            if not rw[7] or rw[0] not in mods:
                continue
            lba, d = mods[rw[0]]
            off = int(rw[2], 16)
            want = enc(rw[7])
            got = bytes(d[off:off + len(want)])
            if got != want:
                bad += 1
                if bad <= 6:
                    print('  ❌%s 0x%s 텍스트 불일치' % (rw[0], rw[2]))
            n += 1
        print('  텍스트 %d필드 되읽기 검사' % n)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 폰트·크기상수·디스크립터·텍스트 일치.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
