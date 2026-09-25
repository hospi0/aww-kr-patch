# -*- coding: utf-8 -*-
"""메인메뉴(GMSELDT/ASCGSCG) 한글화 — 폰트 성장 + 텍스트 패치 (세션12).

ASCGSCG 폰트(594글리프, VRAM 0x1E00 로드)를 성장시켜 한글 글리프를 붙이고, GMSELDT의
메뉴 본체 텍스트를 length-locked로 한글 패치한다. build_ui16(ASC16CG/GMDT)의 자매 도구.

구조:
  ① 슬롯: 한글 음절 → 글리프 594.. (menu_kr 수요 126음절 → 594~719, 900천장 여유 큼)
  ② 폰트: 원본 594글리프 + 한글 = 720글리프. 원 할당(38섹터)을 넘어 **트랙꼬리 재배치**
     (NEW_LBA 259353, ASC16CG 재배치 259296~259352 바로 뒤 빈 구간). 디렉터리 1레코드 갱신.
  ③ 텍스트: menu_kr.LABELS + DESC(▶줄바꿈) + 사관학교 5개. 원문 앵커로 찾아 제자리 패치.
     ★가나 입력 그리드는 menu_kr에 없음 = 안 건드림(이름 입력 팔레트 보존).

⚠️드라이런 기본. --write F: 기록 / --revert 원상복구.
연표(0x12D14~)는 제외 — 나중에 축약·의역 + (필요시) 천장돌파.
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import menu_kr as K
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from build_reloc import find_dirrec
from hangul import render_kr

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
GLYPH = 128
OLD_N = 594
RAMP = 'dark'                    # ★세션13 사용자 확정(안 H) — hangul.to_glyph_dark 참조.
#   'raw'(세션12 최초빌드)는 AA 가장자리가 팔레트의 가장 밝은 색이라 빨간 띠에서 흰 후광.
NEW_LBA = 259357                 # F: 트랙꼬리 빈 구간(259357~259438, 82섹터).
#   ⚠️259353~259356은 B빌드가 안 지운 옛 964폰트 잔재(무참조 고아). 그걸 피해 259357부터.
FONTMAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'fontmaps.json')
BR = '▶'

# 사관학교 5개 — 試 미매핑이라 士官学校（ 앵커로 순서 처리(menu_kr LABELS 밖).
SCHOOL_KR = ['사관학교（초급）', '사관학교（중급）', '사관학교（상급）',
             '사관학교（시험A）', '사관학교（시험B）']


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def load_map():
    m = json.load(open(FONTMAP, encoding='utf-8'))['ASCGSCG']
    fwd = {int(k): v for k, v in m.items()}        # glyph -> char
    rev = {v: int(k) for k, v in m.items()}        # char -> glyph
    return fwd, rev


def syllables(s):
    return [c for c in s if '가' <= c <= '힣']


def build_slots():
    """한글 음절 → 글리프 인덱스 594.. (빈도 내림차순, 안정)."""
    from collections import Counter
    freq = Counter()
    for kr in list(K.LABELS.values()) + list(K.DESC.values()) + SCHOOL_KR:
        for c in syllables(kr):
            freq[c] += 1
    syl = [c for c, _ in freq.most_common()]
    slot = {c: OLD_N + i for i, c in enumerate(syl)}
    return slot


def make_enc(rev, slot):
    def enc(s):
        out = bytearray()
        for c in s:
            if '가' <= c <= '힣':
                out += struct.pack('>H', slot[c])
            elif c == ' ':
                out += struct.pack('>H', 0)             # 공백 = 글리프0(빈칸)
            elif c in rev:
                out += struct.pack('>H', rev[c])
            else:
                raise SystemExit('인코딩불가 %r in %r' % (c, s))
        return out
    return enc


def enc_jp(s, rev):
    out = bytearray()
    for c in s:
        if c not in rev:
            return None
        out += struct.pack('>H', rev[c])
    return bytes(out)


WLO, WHI = 0x1279C, 0x12D14      # 메뉴 본체 풀 윈도우(연표 0x12D14~ 제외).
#   ★같은 문자열(カートリッジ 4곳·終了 12곳)이 모듈 여러 곳에 있어 창 밖 사본을 잡으면 안 된다.
#     검색을 이 창으로 제한해 저장선택 화면의 그 사본만 잡는다.


def plan_text(d, rev, slot):
    """[(off, raw, nb, jp, kr)] — GMSELDT 메뉴 텍스트 패치(윈도우 내)."""
    enc = make_enc(rev, slot)
    plans = []
    taken = set()

    def rec_end(j):
        e = j
        while struct.unpack_from('>H', d, e)[0] != 0xFFFF:
            e += 2
        return e

    def cap(j, jlen):
        c = jlen
        e = j + jlen * 2
        while e + 2 <= len(d) and struct.unpack_from('>H', d, e)[0] == 0:
            c += 1
            e += 2
        return c

    # ── DESC 먼저 (레코드 전체 교체) — 설명문 속 ドイツ軍 등이 LABELS 나라명에
    #    잘못 잡히지 않게 이 영역을 taken으로 선점한다. ──
    for key, anchor in (('キャンペーン설명', 'あなたが将軍となり'),
                        ('スタンダード설명', '単独のシナリオを')):
        kr = K.DESC[key]
        ab = enc_jp(anchor, rev)
        j = d.find(ab, WLO, WHI)
        if j < 0:
            raise SystemExit('DESC 앵커 %r 없음' % anchor)
        e = rec_end(j)
        reclen = (e - j) // 2
        if len(kr) > reclen:
            raise SystemExit('DESC %s %d>%d' % (key, len(kr), reclen))
        raw = d[j:e]
        nb = enc(kr).ljust(len(raw), b'\x00')
        taken.update(range(j, e))
        plans.append((j, raw, nb, anchor, kr))

    # ── LABELS (긴 것 먼저 = 부분일치 방지) ──
    for jp in sorted(K.LABELS, key=len, reverse=True):
        kr = K.LABELS[jp]
        jb = enc_jp(jp, rev)
        if jb is None:
            raise SystemExit('LABELS 앵커 인코딩불가: %r' % jp)
        p = WLO
        while True:
            j = d.find(jb, p, WHI)
            if j < 0:
                break
            p = j + 2
            if any(x in taken for x in range(j, j + len(jb))):
                continue
            c = cap(j, len(jp))
            if len(kr) > c:
                raise SystemExit('%r→%r %d>용량%d' % (jp, kr, len(kr), c))
            width = max(len(jp), len(kr))
            raw = d[j:j + width * 2]
            if 0xFFFF in [struct.unpack_from('>H', raw, k)[0] for k in range(0, len(raw), 2)]:
                raise SystemExit('%r 필드에 종료자' % jp)
            nb = enc(kr).ljust(len(raw), b'\x00')
            taken.update(range(j, j + len(raw)))
            plans.append((j, raw, nb, jp, kr))
            break

    # ── 사관학교 5개 (試 미매핑 → 士官学校（ 앵커로 순서 매칭) ──
    school_kr = SCHOOL_KR
    prefix = enc_jp('士官学校（', rev)
    p = WLO
    idx = 0
    while idx < 5:
        j = d.find(prefix, p, WHI)
        if j < 0:
            break
        p = j + 2
        if any(x in taken for x in range(j, j + len(prefix))):
            continue
        e = rec_end(j)
        kr = school_kr[idx]
        if len(kr) > (e - j) // 2:
            raise SystemExit('학교 %s 초과' % kr)
        raw = d[j:e]
        nb = enc(kr).ljust(len(raw), b'\x00')
        taken.update(range(j, e))
        plans.append((j, raw, nb, '士官学校#%d' % idx, kr))
        idx += 1
    if idx != 5:
        raise SystemExit('사관학교 레코드 %d개(5개여야)' % idx)

    # 겹침 검사 — 두 계획이 같은 바이트를 건드리면 즉시 실패
    seen = {}
    for j, raw, nb, jp, kr in plans:
        for k in range(len(raw)):
            if j + k in seen:
                raise SystemExit('계획 겹침 @0x%x (%r vs %r)' % (j + k, seen[j + k], jp))
            seen[j + k] = jp
    return plans


def build_font(f, slot):
    hits, rlba, rsize, _ = find_dirrec(f, 'ASCGSCG')
    if len(hits) != 1:
        raise SystemExit('ASCGSCG 디렉터리 %d개(1개여야)' % len(hits))
    _, lba, size, rec_off = hits[0]
    if size // GLYPH != OLD_N:
        raise SystemExit('ASCGSCG %d글리프(예상 %d)' % (size // GLYPH, OLD_N))
    new_n = OLD_N + len(slot)
    font = bytearray(read_file(f, lba, OLD_N * GLYPH))
    font += bytearray((new_n - OLD_N) * GLYPH)
    inv = {v: k for k, v in slot.items()}
    for gi in range(OLD_N, new_n):
        # ★세션13: ramp='dark' — 밝은 후광 제거(팔레트 1=밝음…15=검정, hangul.to_glyph_dark 주석).
        font[gi * GLYPH:(gi + 1) * GLYPH] = render_kr(inv[gi], ramp=RAMP)
    return hits, rlba, rsize, lba, size, bytes(font)


def main():
    revert = '--revert' in sys.argv
    fontonly = '--font-only' in sys.argv          # ★폰트 블록만 다시 기록(텍스트·디렉터리 불변)
    write = '--write' in sys.argv or revert or fontonly
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))

    fwd, rev = load_map()
    slot = build_slots()
    print('한글 %d음절 → 글리프 %d~%d (ASCGSCG %d→%d)'
          % (len(slot), OLD_N, OLD_N + len(slot) - 1, OLD_N, OLD_N + len(slot)))

    f = open(TRACK1, 'rb')                            # 계획은 원본에서
    gl, gsz = [(l, s) for p, l, s in files(skip_media=False) if p == '/GMSELDT'][0]
    d = read_file(f, gl, gsz)
    plans = plan_text(d, rev, slot)
    hits, rlba, rsize, old_lba, old_size, font = build_font(f, slot)
    nsec = (len(font) + USER - 1) // USER
    print('ASCGSCG lba=%d size=%d → 새 %dB / %d섹터 → lba %d..%d'
          % (old_lba, old_size, len(font), nsec, NEW_LBA, NEW_LBA + nsec - 1))
    print('텍스트 %d곳:' % len(plans))
    for j, raw, nb, jp, kr in plans:
        print('  0x%06x %-22s → %s' % (j + gl * 0, jp, kr))
    f.close()

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --revert / --font-only).')
        return

    if fontonly:
        # ★폰트 블록만 재기록. 텍스트·디렉터리는 이미 맞으므로 손대지 않는다(회귀 사각 최소).
        with open(dst, 'rb') as r:
            fhits, _, _, _ = find_dirrec(r, 'ASCGSCG')
            if [(l, s) for _, l, s, _ in fhits] != [(NEW_LBA, len(font))]:
                raise SystemExit('F: ASCGSCG 디렉터리가 %s — --font-only는 이미 기록된 빌드 전용'
                                 % [(l, s) for _, l, s, _ in fhits])
            cur = read_file(r, NEW_LBA, len(font))
            if cur[:OLD_N * GLYPH] != font[:OLD_N * GLYPH]:
                raise SystemExit('F: 폰트 원본부(594글리프) 불일치 — 다른 빌드일 수 있음')
            gm = read_file(r, gl, max(j + len(nb) for j, raw, nb, jp, kr in plans) + 4)
            for j, raw, nb, jp, kr in plans:
                if gm[j:j + len(nb)] != nb:
                    raise SystemExit('F: GMSELDT 0x%x 텍스트가 계획과 다름 — 텍스트부터 확인' % j)
        chg = sum(1 for gi in range(OLD_N, len(font) // GLYPH)
                  if cur[gi * GLYPH:(gi + 1) * GLYPH] != font[gi * GLYPH:(gi + 1) * GLYPH])
        print('\nF: 폰트 블록만 재기록 — 한글 글리프 %d/%d개 변경'
              % (chg, len(font) // GLYPH - OLD_N))
        touched = set()
        with open(dst, 'r+b') as w:
            for k in range(0, len(font), USER):
                sec = NEW_LBA + k // USER
                w.seek(sec * RAW + HDR)
                w.write(font[k:k + USER].ljust(USER, b'\x00')[:USER])
                touched.add(sec)
            print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
            for sec in sorted(touched):
                w.seek(sec * RAW)
                raw = w.read(RAW)
                w.seek(sec * RAW)
                w.write(ecc.fix_sector(raw))
        print('완료 ->', dst)
        verify(dst, plans, slot, font, gl)
        return

    # ★★루트 디렉터리는 **F:(패치본)** 에서 읽는다 — 원본에서 읽으면 다른 빌드가 바꾼
    #   디렉터리 레코드(ASC16CG 재배치 259296/115200)를 통째로 원상복구시켜 그 폰트가 깨진다.
    #   (세션12 실사고: 원본 rd를 써서 ASC16CG 디렉터리가 원본 825로 되돌아갔다.)
    with open(dst, 'rb') as fd:
        rd = bytearray(read_file(fd, rlba, rsize))

    # 재배치 자리 비었나 (F:)
    if not revert:
        with open(dst, 'rb') as chk:
            for s in range(NEW_LBA, NEW_LBA + nsec):
                if any(read_file(chk, s, USER)):
                    raise SystemExit('★lba %d 비어있지 않음' % s)

    _, _, _, rec_off = hits[0]
    struct.pack_into('<I', rd, rec_off + 2, old_lba if revert else NEW_LBA)
    struct.pack_into('>I', rd, rec_off + 6, old_lba if revert else NEW_LBA)
    struct.pack_into('<I', rd, rec_off + 10, old_size if revert else len(font))
    struct.pack_into('>I', rd, rec_off + 14, old_size if revert else len(font))

    print('\nF: ISO 제자리 %s' % ('원상복구' if revert else '패치'))
    touched = set()
    with open(dst, 'r+b') as w:
        def put(lba, data):
            for k in range(0, len(data), USER):
                sec = lba + k // USER
                w.seek(sec * RAW + HDR)
                w.write(data[k:k + USER].ljust(USER, b'\x00')[:USER])
                touched.add(sec)
        put(NEW_LBA, bytes(nsec * USER) if revert else font)
        put(rlba, bytes(rd))
        for j, raw, nb, jp, kr in plans:
            src, dstb = (nb, raw) if revert else (raw, nb)
            for k in range(len(raw)):
                lo = j + k
                sec = gl + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if w.read(1) != src[k:k + 1]:
                    raise SystemExit('GMSELDT 0x%x 대조실패 — %s'
                                     % (j, '패치본아님' if revert else '이미패치?'))
                w.seek(pos)
                w.write(dstb[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)
    if not revert:
        verify(dst, plans, slot, font, gl)


def verify(dst, plans, slot, font, gl):
    bad = 0
    inv = {v: k for k, v in slot.items()}
    with open(dst, 'rb') as r:
        hits, _, _, _ = find_dirrec(r, 'ASCGSCG')
        for _, lba, size, _ in hits:
            if (lba, size) != (NEW_LBA, len(font)):
                bad += 1
                print('  ❌디렉터리 lba=%d size=%d' % (lba, size))
        if read_file(r, NEW_LBA, len(font)) != font:
            bad += 1
            print('  ❌폰트 되읽기 불일치')
        for j, raw, nb, jp, kr in plans:
            cur = read_file(r, gl, gl and 0 or 0)  # placeholder
        # 텍스트 되읽기
        gm = read_file(r, gl, max(j + len(nb) for j, raw, nb, jp, kr in plans) + 4)
        for j, raw, nb, jp, kr in plans:
            if gm[j:j + len(nb)] != nb:
                bad += 1
                print('  ❌텍스트 0x%x 불일치' % j)
        secs = set()
        for j, raw, nb, jp, kr in plans:
            for k in range(len(nb)):
                secs.add(gl + (j + k) // USER)
        for s in range(NEW_LBA, NEW_LBA + (len(font) + USER - 1) // USER):
            secs.add(s)
        for sec in secs:
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 디렉터리·폰트·텍스트 일치, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
