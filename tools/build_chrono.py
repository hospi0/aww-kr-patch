# -*- coding: utf-8 -*-
"""연표 + 캠페인 상황문 한글화 — ASCGSCG 폰트 성장 + **원본 슬롯 회수** (세션14).

대상 = GMSELDT `0x12D14~0x14360` 162레코드 2,562셀.
    연표(레코드 0~81, 1914~1935년) + 상황문(93~161) 을 번역하고,
    **개발자 이스터에그(82~92)는 손대지 않는다**(가나 그리드가 어차피 가나를 잡아둔다).

★예산 (세션14의 「슬롯 회수」 발견 덕에 가능해졌다)
    수요 261음절 중 **184개는 이미 메뉴·브리핑 슬롯에 있다** → 신규는 **77칸**뿐.
    공급 = ①브리핑 죽은 슬롯(미션명 영문화로 무참조가 된 것) ②855~899 성장 45칸
           ③**회수 슬롯** = ASCGSCG 원본 594글리프 중 무참조 인덱스.
    ⇒ ①②로 대부분을 덮고 **③은 모자란 만큼만** 쓴다(회수는 정적 판정이라 적게 쓸수록 안전).

★왜 회수가 성립하나 — ASCGSCG 텍스트 풀은 `0x126C8~0x157A8` **단 하나의 연속 구간**이다
  (텍스트 5,715셀·360레코드로 실측. 그 밖에서 잡히는 런은 전부 바이너리 노이즈).
  ⇒ **완전 열거가 가능**하므로 「패치 후에도 일본어로 남는 텍스트」가 참조하는 인덱스를
    빠짐없이 셀 수 있다. (ASC16CG는 소비자가 여러 모듈에 흩어져 있어 추정이었다 —
    같은 세션의 asc16_reclaim.py 주석 참조. 여기가 훨씬 확실하다.)

★슬롯 배정 원칙 = **기존 배정 불가침.** 메뉴 594~719, 브리핑 720~854는 그대로 둔다.
  (세션12 실사고: 슬롯 재배정은 「그 폰트로 인코딩된 모든 텍스트 재기록」을 부른다.)

★구분자 = `0xFFFF`. `0x0000`은 **공백**이지 종료자가 아니다 —
  F: 브리핑 텍스트가 레코드 중간에 0000을 쓰고 실기에서 정상 렌더되는 것이 실증(세션13-d).
  그래도 원본이 `0xFFFF`인 자리는 **절대 덮지 않는다**(세션8-a 세이브화면 사고).

빌드: python tools/build_chrono.py            드라이런
      python tools/build_chrono.py --write     F: ISO 기록
      python tools/build_chrono.py --revert    원상복구
      python tools/build_chrono.py --resync    번역 수정 후 재기록
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import chrono_kr as K
import build_menu as BM
import brief_kr as BK
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from build_reloc import find_dirrec
from game_pool_kr import MISSIONS
from hangul import render_kr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
GLYPH = 128
LBA = BM.NEW_LBA                  # 259357 — build_menu이 정한 ASCGSCG 자리
BASE_N = 855                      # 현재 F:에 기록된 글리프 수(594 원본 + 메뉴126 + 브리핑135)
NEW_N = 900                       # ASCGSCG 천장(텍스트 맵이 0x1E000: 0x1E00+900*128)
TRACK_END = 259438                # 원본 트랙 마지막 유효 MODE1 섹터(세션13-b 실사고)
ORIG_N = 594                      # 원본 글리프 수 = 회수 후보 범위 1..593
POOL_LO, POOL_HI = 0x126C8, 0x157A8      # ASCGSCG 텍스트 풀 전체(완전 열거의 근거)
LO, HI = 0x12D14, 0x14360                # 이번 대상 구간
SLOTS = os.path.join(ROOT, 'work', 'chrono_slots.json')
FONTMAP = os.path.join(ROOT, 'work', 'fontmaps.json')
RAMP = 'dark'                     # 세션13 사용자 확정(안 H)


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def load_map():
    m = json.load(open(FONTMAP, encoding='utf-8'))['ASCGSCG']
    fwd = {int(k): v for k, v in m.items()}
    fwd.update(K.UNMAPPED)                    # 526=布 527=告 (문맥 확정)
    return fwd, {v: k for k, v in fwd.items()}


def gmseldt():
    with open(TRACK1, 'rb') as f:
        lba, size = [(l, s) for p, l, s in files(skip_media=False) if p == '/GMSELDT'][0]
        return lba, size, read_file(f, lba, size)


def records(d, lo, hi, fwd):
    """[(off, [글리프], 원문)] — 구분자(0xFFFF/0x0000)로 끊는다."""
    out, cur, start = [], [], lo
    for off in range(lo, hi, 2):
        w = struct.unpack_from('>H', d, off)[0]
        if w in (0xFFFF, 0x0000):
            if cur:
                out.append((start, cur, ''.join(fwd.get(x, '{%d}' % x) for x in cur)))
                cur = []
            start = off + 2
        else:
            cur.append(w)
    if cur:
        out.append((start, cur, ''.join(fwd.get(x, '{%d}' % x) for x in cur)))
    return out


def translations(d, fwd):
    """[(off, cap, jp, kr)] — 번역표에 있는 레코드만. 이스터에그는 자동으로 빠진다."""
    out = []
    for off, cells, jp in records(d, LO, HI, fwd):
        kr = K.CHRONO.get(jp)
        if kr is None:
            kr = K.SITUATION.get(jp.replace('▶', ''))
            if kr is not None:
                kr = K.wrap(kr)
        if kr is None:
            continue                       # 이스터에그 등 — 일본어 유지
        out.append((off, len(cells), jp, kr))
    return out


def dead_brief_slots(need):
    """브리핑 슬롯 중 **아무도 안 쓰는** 것(미션명 영문화로 죽은 자리). 재사용 가능."""
    brief = json.load(open(os.path.join(ROOT, 'work', 'brief_slots.json'), encoding='utf-8'))
    live = set()
    for jp, kr in BK.DESC.items():
        live |= {c for c in BK.wrap(kr) if '가' <= c <= '힣'}
    for i in range(len(MISSIONS) + 1):
        kr = BK.NAMES.get(i) or (MISSIONS[i][1] if i < len(MISSIONS) else None)
        if kr:
            live |= {c for c in BK.wrap(kr) if '가' <= c <= '힣'}
    return brief, sorted(brief[c] for c in brief if c not in live and c not in need)


def reclaimable(d, fwd, plan_bytes):
    """ASCGSCG 원본 슬롯 1..593 중 **패치 후 아무도 참조하지 않는** 인덱스.

    풀 전체(POOL_LO..POOL_HI)에서 **우리가 쓸 바이트 범위를 뺀** 자리의 인덱스를 센다.
    ⇒ 남는 일본어(가나 그리드·이스터에그·브리핑 잔여 등)가 쓰는 건 전부 보존된다.
    ★기준 데이터는 **F: 현재본**이다(메뉴·브리핑이 이미 한글이라 그만큼 한자가 풀렸다).
    """
    keep = set()
    for off in range(POOL_LO, POOL_HI, 2):
        if off in plan_bytes:
            continue
        w = struct.unpack_from('>H', d, off)[0]
        if 0 < w < ORIG_N:
            keep.add(w)
    return sorted(set(range(1, ORIG_N)) - keep), keep


def build_slots(need, dead, recl):
    """음절 → 글리프. 기존(메뉴·브리핑) 배정은 건드리지 않는다."""
    base = dict(BM.build_slots())                       # 594~719
    base.update(json.load(open(os.path.join(ROOT, 'work', 'brief_slots.json'),
                               encoding='utf-8')))      # 720~854
    new = sorted(need - set(base))
    pool = list(range(BASE_N, NEW_N)) + dead + recl     # 성장 → 죽은슬롯 → 회수 순
    if len(new) > len(pool):
        raise SystemExit('신규 %d음절 > 공급 %d칸' % (len(new), len(pool)))
    if os.path.exists(SLOTS):                           # 배정 고정(재빌드 안정성)
        extra = json.load(open(SLOTS, encoding='utf-8'))
        taken = set(extra.values())
        free = [g for g in pool if g not in taken]
        for c in new:
            if c not in extra:
                extra[c] = free.pop(0)
    else:
        extra = {c: pool[i] for i, c in enumerate(new)}
    json.dump(extra, open(SLOTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    slot = dict(base)
    slot.update(extra)
    return base, extra, slot


def make_enc(rev, slot):
    def enc(s):
        b = bytearray()
        for c in s:
            if '가' <= c <= '힣':
                b += struct.pack('>H', slot[c])
            elif c == ' ':
                b += struct.pack('>H', 0)          # 공백 = 글리프0(종료자 아님)
            elif c in rev:
                b += struct.pack('>H', rev[c])
            else:
                raise SystemExit('인코딩불가 %r in %r' % (c, s))
        return bytes(b)
    return enc


def plan(d, fwd, rev, slot, trans):
    enc = make_enc(rev, slot)
    plans, seen = [], {}
    for off, cap, jp, kr in trans:
        if len(kr) > cap:
            raise SystemExit('%r → %r %d>용량%d' % (jp[:14], kr, len(kr), cap))
        raw = d[off:off + cap * 2]
        for k in range(0, len(raw), 2):
            if struct.unpack_from('>H', raw, k)[0] == 0xFFFF:
                raise SystemExit('0x%06x 계획에 종료자 포함 — 중단' % (off + k))
        nb = enc(kr).ljust(len(raw), b'\x00')
        for k in range(len(raw)):
            if off + k in seen:
                raise SystemExit('계획 겹침 @0x%x' % (off + k))
            seen[off + k] = 1
        plans.append((off, raw, nb, jp, kr))
    return plans, seen


def build_font(dst, extra):
    """F:의 현재 855글리프 폰트를 900으로 키우고 신규 음절을 렌더해 넣는다."""
    with open(dst, 'rb') as r:
        hits, rlba, rsize, _ = find_dirrec(r, 'ASCGSCG')
        cur = [(l, s) for _, l, s, _ in hits]
        if cur not in ([(LBA, BASE_N * GLYPH)], [(LBA, NEW_N * GLYPH)]):
            raise SystemExit('★F: ASCGSCG가 %s — 브리핑 기록본도, 이 빌드본도 아니다' % cur)
        font = bytearray(read_file(r, LBA, BASE_N * GLYPH))
    font += bytearray((NEW_N - BASE_N) * GLYPH)
    for c, gi in extra.items():
        font[gi * GLYPH:(gi + 1) * GLYPH] = render_kr(c, ramp=RAMP)
    return hits, rlba, rsize, bytes(font)


def guard(dst, nsec, check_empty=True):
    n = os.path.getsize(dst) // RAW
    SY = b'\x00' + b'\xff' * 10 + b'\x00'
    with open(dst, 'rb') as r:
        for sec in range(LBA, LBA + nsec):
            if sec > TRACK_END:
                raise SystemExit('★섹터 %d > 원본 트랙 끝 %d' % (sec, TRACK_END))
            if sec >= n:
                raise SystemExit('★섹터 %d 파일 범위 밖' % sec)
            r.seek(sec * RAW)
            h = r.read(16)
            if h[:12] != SY or h[15] != 1:
                raise SystemExit('★섹터 %d MODE1 아님' % sec)
        if check_empty:
            for sec in range(LBA + (BASE_N * GLYPH + USER - 1) // USER, LBA + nsec):
                if any(read_file(r, sec, USER)):
                    raise SystemExit('★확장 섹터 %d 가 비어있지 않다' % sec)
    print('관문 통과 — lba %d..%d (트랙 끝 %d 이내), 전부 MODE1.' % (LBA, LBA + nsec - 1, TRACK_END))


def verify_slots(dp, slot_vals, plan_bytes):
    """패치 후 풀에서 **우리가 쓴 자리 밖**이 재정의 슬롯을 참조하는지 (핵심 관문)."""
    bad = []
    tgt = set(slot_vals)
    for off in range(POOL_LO, POOL_HI, 2):
        if off in plan_bytes:
            continue
        w = struct.unpack_from('>H', dp, off)[0]
        if w in tgt:
            bad.append((off, w))
    return bad


def main():
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    fwd, rev = load_map()
    gl, gsz, d_orig = gmseldt()                       # 계획은 **원본**에서
    with open(dst, 'rb') as r:
        d_cur = read_file(r, gl, gsz)                 # 회수 판정은 **F: 현재본**에서

    trans = translations(d_orig, fwd)
    plan_bytes = set()
    for off, cap, jp, kr in trans:
        plan_bytes.update(range(off, off + cap * 2))

    need = {c for _, _, _, kr in trans for c in kr if '가' <= c <= '힣'}
    brief, dead = dead_brief_slots(need)
    recl, keep = reclaimable(d_cur, fwd, plan_bytes)
    base, extra, slot = build_slots(need, dead, recl)

    print('대상 %d레코드 (연표 %d + 상황문 %d), 이스터에그 등 %d개는 유지'
          % (len(trans), sum(1 for t in trans if t[2] in K.CHRONO),
             sum(1 for t in trans if t[2] not in K.CHRONO),
             len(records(d_orig, LO, HI, fwd)) - len(trans)))
    print('수요 %d음절 — 기존 슬롯 %d / 신규 %d'
          % (len(need), len(need & set(base)), len(extra)))
    print('공급: 성장 %d(855~899) + 브리핑 죽은슬롯 %d + 회수 %d = %d칸'
          % (NEW_N - BASE_N, len(dead), len(recl), NEW_N - BASE_N + len(dead) + len(recl)))
    used_recl = sorted(g for g in extra.values() if g < ORIG_N)
    print('  ★실제로 재정의하는 원본 글리프 %d칸: %s'
          % (len(used_recl), ''.join(fwd.get(g, '?') for g in used_recl)))

    plans, seen = plan(d_orig, fwd, rev, slot, trans)
    hits, rlba, rsize, font = build_font(dst, extra)
    nsec = (len(font) + USER - 1) // USER
    print('ASCGSCG %d→%d글리프 (%dB / %d섹터, lba %d..%d)'
          % (BASE_N, NEW_N, len(font), nsec, LBA, LBA + nsec - 1))

    # ── 핵심 관문: 패치 후 풀에서 재정의 슬롯이 남의 텍스트에 안 쓰이는가 ──
    dp = bytearray(d_cur)
    for off, raw, nb, jp, kr in plans:
        dp[off:off + len(nb)] = nb
    bad = verify_slots(dp, set(extra.values()), plan_bytes)
    if bad:
        for off, w in bad[:12]:
            ctx = ''.join(fwd.get(struct.unpack_from('>H', dp, k)[0], '·')
                          for k in range(max(POOL_LO, off - 16), min(POOL_HI, off + 18), 2))
            print('  ❌0x%06x 글리프 %d(%s) …%s…' % (off, w, fwd.get(w, '?'), ctx))
        raise SystemExit('★슬롯 안전 검증 실패 %d건 — 그 인덱스를 배정에서 빼야 한다' % len(bad))
    print('✅슬롯 안전 검증 통과 — 풀 전체(0x%X~0x%X)에서 재정의 슬롯 참조 0'
          % (POOL_LO, POOL_HI))

    if not write:
        print('\n샘플:')
        for off, raw, nb, jp, kr in plans[:6] + plans[-4:]:
            print('  0x%06x %-22s → %s' % (off, jp[:20], kr))
        print('\n드라이런 — ISO 미기록 (--write / --revert / --resync).')
        return

    if not revert:
        guard(dst, nsec, check_empty=not resync)

    with open(dst, 'rb') as r:
        rd = bytearray(read_file(r, rlba, rsize))
    _, _, _, rec_off = hits[0]
    size = BASE_N * GLYPH if revert else len(font)
    struct.pack_into('<I', rd, rec_off + 10, size)
    struct.pack_into('>I', rd, rec_off + 14, size)

    print('\nF: ISO %s' % ('원상복구' if revert else '패치'))
    touched = set()
    with open(dst, 'r+b') as w:
        def put(lba, data):
            for k in range(0, len(data), USER):
                sec = lba + k // USER
                w.seek(sec * RAW + HDR)
                w.write(data[k:k + USER].ljust(USER, b'\x00')[:USER])
                touched.add(sec)
        if revert:
            put(LBA, font[:BASE_N * GLYPH])
            put(LBA + (BASE_N * GLYPH) // USER,
                bytes((nsec - (BASE_N * GLYPH) // USER) * USER))
        else:
            put(LBA, font)
        put(rlba, bytes(rd))
        for off, raw, nb, jp, kr in plans:
            src, dstb = (nb, raw) if revert else (raw, nb)
            for k in range(len(raw)):
                lo = off + k
                sec = gl + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if not resync and w.read(1) != src[k:k + 1]:
                    raise SystemExit('GMSELDT 0x%x 대조실패 — %s'
                                     % (lo, '패치본아님' if revert else '이미패치?'))
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
        verify(dst, plans, font, gl, gsz, set(extra.values()), plan_bytes, fwd)


def verify(dst, plans, font, gl, gsz, slot_vals, plan_bytes, fwd):
    bad = 0
    with open(dst, 'rb') as r:
        hits, _, _, _ = find_dirrec(r, 'ASCGSCG')
        for _, lba, size, _ in hits:
            if (lba, size) != (LBA, len(font)):
                bad += 1
                print('  ❌디렉터리 lba=%d size=%d' % (lba, size))
        if read_file(r, LBA, len(font)) != font:
            bad += 1
            print('  ❌폰트 되읽기 불일치')
        g = read_file(r, gl, gsz)
        for off, raw, nb, jp, kr in plans:
            if g[off:off + len(nb)] != nb:
                bad += 1
                print('  ❌텍스트 0x%x (%s)' % (off, jp[:12]))
        for off, w in verify_slots(g, slot_vals, plan_bytes):
            bad += 1
            print('  ❌기록 후 0x%06x 가 재정의 슬롯 %d 참조' % (off, w))
        secs = {gl + (off + i) // USER for off, raw, nb, j, k in plans for i in range(len(nb))}
        secs |= set(range(LBA, LBA + (len(font) + USER - 1) // USER))
        for sec in secs:
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 디렉터리·폰트·텍스트 일치, 슬롯 참조 0, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
