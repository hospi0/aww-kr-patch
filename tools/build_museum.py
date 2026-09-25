# -*- coding: utf-8 -*-
"""병기도감(MUSEUM/ASCMSCG) 한글화 — 폰트 성장 + 텍스트 패치 (세션13).

구조 (build_menu/build_ui16의 자매 도구):
  ① 슬롯: 한글 음절 → 글리프 830.. (빈도 내림차순, `work/museum_slots.json`에 **고정**)
     ★고정 이유 = 슬롯 재배정이 곧 「이미 기록한 텍스트 전부 재인코딩」이다(세션12 실사고).
  ② 폰트: ASCMSCG 830글리프 + 한글 = N글리프. 원 할당(52섹터)을 넘어 **트랙꼬리 재배치**
     (NEW_LBA, ASCGSCG 재배치 259357~259401 바로 뒤). 디렉터리 1레코드 both-endian 갱신.
     ★천장 = charnum 12비트 → **964글리프**(세션9). 병기도감 화면 VDP2 VRAM 0x1C000~0x22000이
     비어 있음을 state2·state3에서 실측했으므로 964까지 물리적으로 안전.
  ③ 텍스트: MUSEUM UI 풀 `0x92000~0x926C0`을 레코드 단위로 파싱해 원문키로 매칭, length-locked.
     ★★「トーチカ／要塞兵器図鑑」은 **한 레코드에 라벨 2개가 겹쳐** 있다(그리드 타이틀이 8번째
     글자부터 시작) → museum_kr.SPLIT으로 앞 7글자 자리를 보존하며 각각 채운다.

⚠️드라이런 기본. --write F: 기록 / --revert 원상복구 / --font-only 폰트 블록만 재기록.
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import museum_kr as K
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from build_reloc import find_dirrec
from hangul import render_kr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
GLYPH = 128
OLD_N = 830                      # ASCMSCG 원본 글리프 수 (106240B)
CEIL = 964                       # charnum 12비트 하드 상한
#   ★★배치 = **옛 ASCGSCG 자리(3434~3471) + ASCMSCG 자기 자리(3472~3523) = 연속 90섹터.**
#     ASCGSCG는 세션12에 트랙꼬리(259357)로 재배치돼 이 구간이 무참조로 비었다.
#     ⚠️트랙꼬리는 쓸 수 없다 — **원본 트랙은 259438에서 끝나고**(0..259438) 259402부터
#       유효 MODE1 섹터가 37개뿐이라 59섹터가 안 들어간다. 꼬리 총 여유도 48섹터가 한계.
#       (세션13 실사고: 259402에 쓰려다 헤더 없는 259439에서 ECC 단계가 멈췄다.
#        F: 파일이 259460섹터인 건 세션9 옛 964폰트가 헤더 없이 덧붙인 잔재다.)
NEW_LBA = 3434
GUARD_LO, GUARD_HI = 3434, 3523   # 이 밖으로는 절대 쓰지 않는다(라이브 파일 침범 방지)
RAMP = 'dark'                    # 세션13 안 M3 (밝은 후광 회피)
POOL_LO, POOL_HI = 0x92000, 0x926C0
SLOTS = os.path.join(ROOT, 'work', 'museum_slots.json')
FONTMAP = os.path.join(ROOT, 'work', 'fontmaps.json')


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def load_map():
    m = json.load(open(FONTMAP, encoding='utf-8'))['ASCMSCG']
    fwd = {int(k): v for k, v in m.items()}
    fwd.update(K.EXTRA_GLYPHS)                     # 미매핑 글리프 보강(세션13)
    rev = {v: k for k, v in fwd.items()}
    return fwd, rev


def build_slots():
    """한글 음절 → 글리프 인덱스. work/museum_slots.json 에 고정 저장(추가는 append)."""
    from collections import Counter
    freq = Counter()
    for kr in (list(K.all_tables().values()) + list(K.JOINED.values())
               + [a + b for a, b in K.SPLIT.values()]):
        for c in kr:
            if '가' <= c <= '힣':
                freq[c] += 1
    order = [c for c, _ in sorted(freq.items(), key=lambda t: (-t[1], t[0]))]
    # ★★세션15: 확장(OLD_N~CEIL)이 차면 **원본 글리프 슬롯을 회수**해 이어 쓴다.
    #   전면 한글화 기준이므로 가나·한자 칸은 전부 우리 것이다
    #   ([[feedback_aww_full_kr_budget]]). 라틴·숫자·로마숫자·기호는 남긴다 —
    #   유닛명 로마자와 타입값 안의 （）·숫자가 그 인덱스를 그대로 쓴다.
    import charmap

    def spare():
        keep = set()
        for kr in (list(K.all_tables().values()) + list(K.JOINED.values())
                   + [a + b for a, b in K.SPLIT.values()]):
            for c in kr:
                if not ('가' <= c <= '힣'):
                    keep.add(c)
        out = []
        for i in range(1, OLD_N):
            ch = charmap.CHARS.get(i)
            if ch is None or len(ch) != 1 or ch in keep:
                continue
            o = ord(ch)
            if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF:
                out.append(i)
        return out

    pool = list(range(OLD_N, CEIL)) + spare()
    if os.path.exists(SLOTS):
        slot = {k: v for k, v in json.load(open(SLOTS, encoding='utf-8')).items()}
        # ★★세션15-e: 유닛명 음절은 ASC16CG와 **같은 인덱스**여야 한다(공용 표 참조).
        import shared_slots
        for _c, _g in shared_slots.build(verbose=False).items():
            slot[_c] = _g
        used = set(slot.values())
        free = [i for i in pool if i not in used]
        for c in order:
            if c not in slot:                       # 신규는 남은 칸에 (기존 배정 불변)
                if not free:
                    raise SystemExit('★슬롯 고갈: 확장 %d + 회수 %d칸 소진'
                                     % (CEIL - OLD_N, len(pool) - (CEIL - OLD_N)))
                slot[c] = free.pop(0)
    else:
        if len(order) > len(pool):
            raise SystemExit('★슬롯 부족: %d음절 > %d칸' % (len(order), len(pool)))
        slot = {c: pool[i] for i, c in enumerate(order)}
    nrec = sum(1 for v in slot.values() if v < OLD_N)
    print('  슬롯 %d음절 = 확장 %d + 회수 %d (회수 가능 총 %d칸)'
          % (len(slot), len(slot) - nrec, nrec, len(pool) - (CEIL - OLD_N)))
    json.dump(slot, open(SLOTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return slot


def parse_pool(d, fwd):
    """UI 풀을 레코드 단위로 파싱 → [(off, key, nchars, delim)]  (구분자 0xFFFF/0x0000)."""
    recs = []
    off = POOL_LO
    start = off
    chars = []
    while off < POOL_HI:
        w = struct.unpack_from('>H', d, off)[0]
        if w in (0xFFFF, 0x0000):
            if chars:
                recs.append((start, ''.join(chars), len(chars), w))
                chars = []
            start = off + 2
        else:
            chars.append(fwd.get(w, '{%d}' % w))
        off += 2
    if chars:
        recs.append((start, ''.join(chars), len(chars), None))
    # 널이 문자열 안에 낀 레코드(museum_kr.JOINED) — 바로 붙은 두 레코드를 'A|B'로 병합 제공
    merged = []
    for i in range(len(recs) - 1):
        o1, k1, n1, d1 = recs[i]
        o2, k2, n2, d2 = recs[i + 1]
        if d1 == 0x0000 and o2 == o1 + n1 * 2 + 2:
            merged.append((o1, '%s|%s' % (k1, k2), n1 + 1 + n2, d2))
    return recs + merged


def make_enc(rev, slot):
    def enc(s):
        out = bytearray()
        for c in s:
            if '가' <= c <= '힣':
                out += struct.pack('>H', slot[c])
            elif c == ' ':
                out += struct.pack('>H', 0)         # 공백 = 글리프0
            elif c in rev:
                out += struct.pack('>H', rev[c])
            else:
                raise SystemExit('인코딩불가 %r in %r' % (c, s))
        return out
    return enc


def plan_text(d, rev, slot, fwd):
    """[(off, raw, nb, key, kr)] — length-locked."""
    enc = make_enc(rev, slot)
    recs = parse_pool(d, fwd)
    table = dict(K.all_tables())
    table.update(K.JOINED)
    plans = []
    used = set()
    for off, key, n, delim in recs:
        if key in K.SPLIT:                          # 겹친 레코드: 앞 7글자 + 뒤 4글자
            head, tail = K.SPLIT[key]
            jp_head = key[:len(key) - 4]
            hb = enc(head).ljust(len(jp_head) * 2, b'\x00')
            tb = enc(tail)
            if len(hb) != len(jp_head) * 2 or len(tb) != 8:
                raise SystemExit('SPLIT 길이 오류 %r' % key)
            raw = d[off:off + n * 2]
            plans.append((off, raw, bytes(hb + tb), key, head + '/' + tail))
            used.add(key)
            continue
        if key not in table:
            continue
        kr = table[key]
        cap = n
        for lo, hi, c in K.CAPS:                    # 널 패딩까지 허용되는 구역
            if lo <= off < hi:
                cap = max(n, c)
        if len(kr) > cap:
            raise SystemExit('%r→%r %d>용량%d @0x%x' % (key, kr, len(kr), cap, off))
        width = max(n, len(kr))
        # ★원문 길이를 넘겨 쓸 땐 그 워드들이 **전부 0x0000**이어야 한다(0xFFFF 침범 금지)
        for k in range(n, width):
            w = struct.unpack_from('>H', d, off + k * 2)[0]
            if w != 0x0000:
                raise SystemExit('%r 확장 위치 0x%x 가 널 아님(%04x)' % (key, off + k * 2, w))
        raw = d[off:off + width * 2]
        nb = enc(kr).ljust(len(raw), b'\x00')
        plans.append((off, raw, nb, key, kr))
        used.add(key)
    miss = [k for k in list(table) + list(K.SPLIT) if k not in used]
    if miss:
        print('⚠️풀에서 못 찾은 원문 %d개: %s' % (len(miss), ' '.join(miss)))
    # 겹침 검사
    seen = {}
    for off, raw, nb, key, kr in plans:
        for k in range(len(raw)):
            if off + k in seen:
                raise SystemExit('계획 겹침 @0x%x (%r vs %r)' % (off + k, seen[off + k], key))
            seen[off + k] = key
    return plans


def build_font(f, slot):
    hits, rlba, rsize, _ = find_dirrec(f, 'ASCMSCG')
    if len(hits) != 1:
        raise SystemExit('ASCMSCG 디렉터리 %d개(1개여야)' % len(hits))
    _, lba, size, rec_off = hits[0]
    if size // GLYPH != OLD_N:
        raise SystemExit('ASCMSCG %d글리프(예상 %d)' % (size // GLYPH, OLD_N))
    new_n = max(slot.values()) + 1
    font = bytearray(read_file(f, lba, size))
    font += bytearray((new_n - OLD_N) * GLYPH)
    # ★★세션15 버그수정: 예전엔 `range(OLD_N, new_n)` 만 렌더했다. 회수 슬롯(원본 가나·한자
    #   자리, 830 미만)에 배정된 음절은 글리프가 안 그려져 **원본 가나가 그대로 남았다**
    #   — 실기에서 「장갑차」가 「장か차」, 「반궤도형」이 「반궤도い형」으로 떴다.
    #   ⇒ 배정된 **모든** 슬롯을 렌더한다.
    for ch, gi in slot.items():
        font[gi * GLYPH:(gi + 1) * GLYPH] = render_kr(ch, ramp=RAMP)
    return hits, rlba, rsize, lba, size, bytes(font)


SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def guard(dst, nsec):
    """기록 전 관문 — 자리·섹터형식·무참조 확인. 하나라도 어긋나면 아무것도 쓰지 않는다."""
    if NEW_LBA < GUARD_LO or NEW_LBA + nsec - 1 > GUARD_HI:
        raise SystemExit('★자리 초과: %d..%d 는 허용범위 %d..%d 밖'
                         % (NEW_LBA, NEW_LBA + nsec - 1, GUARD_LO, GUARD_HI))
    with open(dst, 'rb') as r:
        # ① ASCGSCG가 정말 딴 곳으로 재배치돼 이 자리가 무참조인가
        gs = [(l, s) for _, l, s, _ in find_dirrec(r, 'ASCGSCG')[0]]
        if any(l < GUARD_HI for l, s in gs):
            raise SystemExit('★ASCGSCG가 아직 %s — 이 자리를 쓸 수 없다' % gs)
        # ② 대상 섹터가 전부 존재하고 유효 MODE1 인가 (원본 트랙 끝 문제 재발 방지)
        n = os.path.getsize(dst) // RAW
        for sec in range(NEW_LBA, NEW_LBA + nsec):
            if sec >= n:
                raise SystemExit('★섹터 %d 는 파일 범위(%d) 밖' % (sec, n))
            r.seek(sec * RAW)
            h = r.read(16)
            if h[:12] != SYNC or h[15] != 1:
                raise SystemExit('★섹터 %d 가 MODE1 아님(헤더 없음)' % sec)
    # ③ 옛 ASCGSCG 구간(3434~3471)이 **비어 있거나 원본 그대로**인가 = 아무도 안 쓴 자리
    #   ★세션15 개정: ASCGSCG 가 259357 로 이사하면서 이 구간을 **0으로 비웠다**.
    #     「원본과 동일」만 통과시키면 그 정상 상태를 거부한다(실제로 막혔다).
    #     0 = 해방된 자리이므로 통과, 그 외 원본과 다른 값 = 다른 빌드가 쓴 것이므로 차단.
    #   ★--resync 는 **우리가 이미 쓴 자리**를 다시 쓰는 것이므로 이 검사를 건너뛴다.
    if '--resync' not in sys.argv:
      with open(TRACK1, 'rb') as o, open(dst, 'rb') as r:
        for sec in range(NEW_LBA, min(NEW_LBA + nsec, 3472)):
            cur = read_file(r, sec, USER)
            if not any(cur):
                continue
            if cur != read_file(o, sec, USER):
                raise SystemExit('★섹터 %d 가 원본과 다름 — 다른 빌드가 쓴 자리일 수 있다' % sec)
    print('관문 통과 — lba %d..%d (허용 %d..%d), 전부 MODE1, 무참조 확인.'
          % (NEW_LBA, NEW_LBA + nsec - 1, GUARD_LO, GUARD_HI))


def main():
    revert = '--revert' in sys.argv
    fontonly = '--font-only' in sys.argv
    write = '--write' in sys.argv or revert or fontonly or '--resync' in sys.argv
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))

    fwd, rev = load_map()
    slot = build_slots()
    print('한글 %d음절 → 글리프 %d~%d (ASCMSCG %d→%d, 천장 %d, 여유 %d)'
          % (len(slot), OLD_N, max(slot.values()), OLD_N, max(slot.values()) + 1,
             CEIL, CEIL - (max(slot.values()) + 1)))

    f = open(TRACK1, 'rb')                            # 계획은 원본에서
    ml, msz = [(l, s) for p, l, s in files(skip_media=False) if p == '/MUSEUM'][0]
    d = read_file(f, ml, msz)
    plans = plan_text(d, rev, slot, fwd)
    hits, rlba, rsize, old_lba, old_size, font = build_font(f, slot)
    nsec = (len(font) + USER - 1) // USER
    print('ASCMSCG lba=%d size=%d → 새 %dB / %d섹터 → lba %d..%d'
          % (old_lba, old_size, len(font), nsec, NEW_LBA, NEW_LBA + nsec - 1))
    print('텍스트 %d곳:' % len(plans))
    for off, raw, nb, key, kr in plans:
        print('  0x%06x %-26s → %s' % (off, key, kr))
    f.close()

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --revert / --font-only).')
        return

    if fontonly:
        with open(dst, 'rb') as r:
            fh, _, _, _ = find_dirrec(r, 'ASCMSCG')
            if [(l, s) for _, l, s, _ in fh] != [(NEW_LBA, len(font))]:
                raise SystemExit('F: ASCMSCG 디렉터리가 %s — --font-only는 기록된 빌드 전용'
                                 % [(l, s) for _, l, s, _ in fh])
            cur = read_file(r, NEW_LBA, len(font))
            if cur[:OLD_N * GLYPH] != font[:OLD_N * GLYPH]:
                raise SystemExit('F: 폰트 원본부(%d글리프) 불일치' % OLD_N)
        touched = set()
        with open(dst, 'r+b') as w:
            for k in range(0, len(font), USER):
                sec = NEW_LBA + k // USER
                w.seek(sec * RAW + HDR)
                w.write(font[k:k + USER].ljust(USER, b'\x00')[:USER])
                touched.add(sec)
            for sec in sorted(touched):
                w.seek(sec * RAW)
                raw = w.read(RAW)
                w.seek(sec * RAW)
                w.write(ecc.fix_sector(raw))
        print('폰트 블록만 재기록: %d섹터' % len(touched))
        verify(dst, plans, font, ml)
        return

    # ★★루트 디렉터리는 F:(패치본)에서 읽는다 — 원본에서 읽으면 ASC16CG/ASCGSCG 재배치
    #   디렉터리를 통째로 되돌린다(세션12 실사고).
    with open(dst, 'rb') as fd:
        rd = bytearray(read_file(fd, rlba, rsize))
    if not revert:
        guard(dst, nsec)

    _, _, _, rec_off = hits[0]
    struct.pack_into('<I', rd, rec_off + 2, old_lba if revert else NEW_LBA)
    struct.pack_into('>I', rd, rec_off + 6, old_lba if revert else NEW_LBA)
    struct.pack_into('<I', rd, rec_off + 10, old_size if revert else len(font))
    struct.pack_into('>I', rd, rec_off + 14, old_size if revert else len(font))

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
            # ★새 자리(3434~)가 **자기 원래 자리(3472~3523)와 겹친다** → 단순 제로화면
            #   원본 폰트 파일이 사라진다. 겹치는 부분은 원본 바이트로 되살릴 것.
            with open(TRACK1, 'rb') as o:
                orig = read_file(o, old_lba, old_size)
            put(NEW_LBA, bytes((old_lba - NEW_LBA) * USER))     # 3434~3471 제로화
            put(old_lba, orig)                                   # 3472~3523 원본 복원
            tail = NEW_LBA + nsec - (old_lba + (old_size + USER - 1) // USER)
            if tail > 0:                                         # 원본 뒤로 넘친 부분 제로화
                put(old_lba + (old_size + USER - 1) // USER, bytes(tail * USER))
        else:
            put(NEW_LBA, font)
        put(rlba, bytes(rd))
        for off, raw, nb, key, kr in plans:
            src, dstb = (nb, raw) if revert else (raw, nb)
            for k in range(len(raw)):
                lo = off + k
                sec = ml + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if w.read(1) != src[k:k + 1] and '--resync' not in sys.argv:
                    raise SystemExit('MUSEUM 0x%x 대조실패 — %s'
                                     % (off, '패치본아님' if revert else '이미패치?'))
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
        verify(dst, plans, font, ml)


def verify(dst, plans, font, ml):
    bad = 0
    with open(dst, 'rb') as r:
        hits, _, _, _ = find_dirrec(r, 'ASCMSCG')
        for _, lba, size, _ in hits:
            if (lba, size) != (NEW_LBA, len(font)):
                bad += 1
                print('  ❌디렉터리 lba=%d size=%d' % (lba, size))
        if read_file(r, NEW_LBA, len(font)) != font:
            bad += 1
            print('  ❌폰트 되읽기 불일치')
        end = max(off + len(nb) for off, raw, nb, key, kr in plans) + 4
        mu = read_file(r, ml, end)
        for off, raw, nb, key, kr in plans:
            if mu[off:off + len(nb)] != nb:
                bad += 1
                print('  ❌텍스트 0x%x 불일치 (%s)' % (off, key))
        secs = set()
        for off, raw, nb, key, kr in plans:
            for k in range(len(nb)):
                secs.add(ml + (off + k) // USER)
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
