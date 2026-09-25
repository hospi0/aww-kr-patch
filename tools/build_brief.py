# -*- coding: utf-8 -*-
"""스탠다드 맵 브리핑 한글화 — ASCGSCG 폰트 **증분 성장** + GMSELDT 텍스트 패치 (세션13-d).

★build_menu(메뉴 본체)와 **같은 폰트 파일 ASCGSCG를 공유**한다. 그래서 이 도구는
  **기존 126음절의 슬롯을 절대 건드리지 않고**(594~719 고정) 새 음절만 720.. 에 덧붙인다.
  ⇒ 이미 F:에 기록된 메뉴 텍스트 42곳은 재인코딩이 필요 없다.
  ★★교훈 반영: 슬롯 재배정은 「그 폰트로 인코딩된 모든 텍스트 재기록」을 부른다(세션12 실사고).

★배치: ASCGSCG는 세션12에 트랙꼬리 lba 259357로 재배치됐다(720글리프=45섹터).
  855글리프 = 109,440B = 54섹터 → **259357..259410** (원본 트랙 끝 259438 이내, 뒤 259402~는 빈 구간).

★텍스트: 설명문 `0x14360~0x15368`(원문 앵커로 매칭) + 미션명 `0x15368~`(세션8 표와 순서 1:1).
  줄바꿈 `▶`는 `brief_kr.wrap()`이 폭 8칸에 맞춰 자동 삽입. length-locked.

빌드: python tools/build_brief.py            드라이런
      python tools/build_brief.py --write     F: ISO 기록
      python tools/build_brief.py --revert    원상복구
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import brief_kr as K
import build_menu as BM
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files
from build_reloc import find_dirrec
from game_pool_kr import MISSIONS
from hangul import render_kr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
GLYPH = 128
LBA = BM.NEW_LBA                  # 259357 (build_menu이 정한 ASCGSCG 자리)
BASE_N = 720                      # build_menu이 기록한 글리프 수(594 원본 + 126 메뉴 한글)
CHRONO_LO = 855                   # 855~899 는 build_chrono(연표·상황문) 영역 — 침범 금지
TRACK_END = 259438                # ★원본 트랙 마지막 유효 MODE1 섹터(세션13 실사고)
DESC_LO, DESC_HI = 0x14360, 0x15368
NAME_LO, NAME_HI = 0x15368, 0x157A8
SLOTS = os.path.join(ROOT, 'work', 'brief_slots.json')
FONTMAP = os.path.join(ROOT, 'work', 'fontmaps.json')
RAMP = 'dark'                     # 세션13 안 M3


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def load_map():
    m = json.load(open(FONTMAP, encoding='utf-8'))['ASCGSCG']
    fwd = {int(k): v for k, v in m.items()}
    rev = {v: k for k, v in fwd.items()}
    return fwd, rev


def texts():
    """[(kind, key_or_index, kr_wrapped)] — 계획에 쓸 최종 문자열."""
    out = []
    for jp, kr in K.DESC.items():
        out.append(('desc', jp, K.wrap(kr)))
    for i in range(len(MISSIONS) + 1):
        kr = K.NAMES.get(i) or (MISSIONS[i][1] if i < len(MISSIONS) else None)
        if kr:
            out.append(('name', i, K.wrap(kr).rstrip('▶')))   # 미션명은 끝 ▶ 없음
    return out


def build_slots():
    """기존 126음절(build_menu) 고정 + 신규는 720.. 에 append(work/brief_slots.json)."""
    base = BM.build_slots()                       # {음절: 594..719}
    if max(base.values()) + 1 != BASE_N:
        raise SystemExit('★메뉴 슬롯이 %d글리프까지다(예상 %d) — menu_kr가 바뀌었나?'
                         % (max(base.values()) + 1, BASE_N))
    need = set()
    for _, _, kr in texts():
        need |= {c for c in kr if '가' <= c <= '힣'}
    new = sorted(need - set(base))
    # ★★세션15: 시나리오 제목 한글화로 신규 음절이 늘었다. 855~899 는 **연표(build_chrono)**
    #   가 이미 쓰고 있으므로 거기로 밀면 충돌한다. ⇒ 신규는 **회수 슬롯**(원본 가나·한자)으로.
    #   전면 한글화 기준이라 원본 칸은 우리 것이다([[feedback_aww_full_kr_budget]]).
    #   ⚠️라틴·숫자·기호는 남긴다 — 브리핑 본문이 Paris·Kiev 같은 라틴을 그대로 쓴다.
    import charmap

    def reclaim_pool():
        keep = set()
        for _, _, kr in texts():
            keep |= {c for c in kr if not ('가' <= c <= '힣')}
        out = []
        for i in range(1, BASE_N):
            ch = charmap.CHARS.get(i)
            if ch is None or len(ch) != 1 or ch in keep:
                continue
            o = ord(ch)
            if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF:
                out.append(i)
        return out

    if os.path.exists(SLOTS):
        extra = json.load(open(SLOTS, encoding='utf-8'))
        used = set(base.values()) | set(extra.values())
        nxt = max(extra.values()) + 1 if extra else BASE_N
        pool = None
        for c in new:
            if c in extra:
                continue
            if nxt < CHRONO_LO:                    # 720~854 구간이 남아 있으면 거기부터
                extra[c] = nxt
                nxt += 1
            else:                                  # 차면 회수 슬롯으로
                if pool is None:
                    pool = [i for i in reclaim_pool() if i not in used]
                    print('  브리핑 신규 음절이 720~%d 를 넘겨 회수 슬롯 사용 '
                          '(가용 %d칸)' % (CHRONO_LO - 1, len(pool)))
                if not pool:
                    raise SystemExit('★회수 슬롯 고갈')
                extra[c] = pool.pop(0)
            used.add(extra[c])
    else:
        extra = {c: BASE_N + i for i, c in enumerate(new)}
    json.dump(extra, open(SLOTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    slot = dict(base)
    slot.update(extra)
    return base, extra, slot


def recs(d, lo, hi, fwd):
    out = []
    cur = []
    start = lo
    for off in range(lo, hi, 2):
        w = struct.unpack_from('>H', d, off)[0]
        if w in (0xFFFF, 0x0000):
            if cur:
                out.append((start, ''.join(cur)))
                cur = []
            start = off + 2
        else:
            cur.append(fwd.get(w, '{%d}' % w))
    return out


def make_enc(rev, slot):
    def enc(s):
        b = bytearray()
        for c in s:
            if '가' <= c <= '힣':
                b += struct.pack('>H', slot[c])
            elif c == ' ':
                b += struct.pack('>H', 0)
            elif c in rev:
                b += struct.pack('>H', rev[c])
            else:
                raise SystemExit('인코딩불가 %r in %r' % (c, s))
        return bytes(b)
    return enc


def plan(d, fwd, rev, slot):
    enc = make_enc(rev, slot)
    dmap = {t: (o, len(t)) for o, t in recs(d, DESC_LO, DESC_HI, fwd)}
    nrec = recs(d, NAME_LO, NAME_HI, fwd)
    plans = []
    for kind, key, kr in texts():
        if kind == 'desc':
            if key not in dmap:
                raise SystemExit('설명문 앵커 없음: %r' % key[:20])
            off, cap = dmap[key]
            label = key[:12]
        else:
            if key >= len(nrec):
                continue
            off, jp = nrec[key]
            cap = len(jp)
            label = '#%d %s' % (key, jp)
        if len(kr) > cap:
            raise SystemExit('%s → %r %d>용량%d' % (label, kr, len(kr), cap))
        raw = d[off:off + cap * 2]
        nb = enc(kr).ljust(len(raw), b'\x00')
        plans.append((off, raw, nb, label, kr))
    seen = {}
    for off, raw, nb, label, kr in plans:
        for k in range(len(raw)):
            if off + k in seen:
                raise SystemExit('계획 겹침 @0x%x (%s vs %s)' % (off + k, seen[off + k], label))
            seen[off + k] = label
    return plans


def build_font(dst, extra):
    """F: **현재 폰트 위에** 브리핑 글리프를 얹는다.

    ★세션15 개정: 예전엔 720글리프(build_menu 기록본)를 기준으로 append 했는데,
      그 뒤 build_chrono 가 855~899 를 쓰며 폰트를 900으로 키웠다. 720 기준으로
      다시 만들면 **연표 글리프가 통째로 날아간다.**
      ⇒ 현재 F: 폰트를 읽어 **크기를 유지하고 우리 인덱스만** 덮어쓴다.
        (공유 자원은 「대상에서 읽어 자기 레코드만」 고친다 — 세션14 fix_dirrec 사고 교훈)
    ★신규 음절 일부는 **회수 슬롯**(원본 가나·한자 자리)으로 가므로 폰트가 안 커질 수도 있다.
    """
    need_n = max([BASE_N] + [v + 1 for v in extra.values()])
    with open(dst, 'rb') as r:
        hits, rlba, rsize, _ = find_dirrec(r, 'ASCGSCG')
        cur = [(l, s) for _, l, s, _ in hits]
        if len(cur) != 1 or cur[0][0] != LBA:
            raise SystemExit('★F: ASCGSCG 배치가 예상 밖: %s' % cur)
        cur_n = cur[0][1] // GLYPH
        if cur_n < BASE_N:
            raise SystemExit('★F: ASCGSCG가 %d글리프 — build_menu 기록본(%d) 이상이어야 한다'
                             % (cur_n, BASE_N))
        font = bytearray(read_file(r, LBA, cur[0][1]))
    new_n = max(cur_n, need_n)
    if new_n > cur_n:
        font += bytearray((new_n - cur_n) * GLYPH)
        print('  폰트 %d → %d글리프' % (cur_n, new_n))
    else:
        print('  폰트 %d글리프 유지 (신규는 회수 슬롯)' % cur_n)
    for c, gi in extra.items():
        font[gi * GLYPH:(gi + 1) * GLYPH] = render_kr(c, ramp=RAMP)
    return hits, rlba, rsize, bytes(font), new_n


def guard(dst, nsec, check_empty=True):
    n = os.path.getsize(dst) // RAW
    SY = b'\x00' + b'\xff' * 10 + b'\x00'
    with open(dst, 'rb') as r:
        for sec in range(LBA, LBA + nsec):
            if sec > TRACK_END:
                raise SystemExit('★섹터 %d > 원본 트랙 끝 %d — 유효 MODE1 아님' % (sec, TRACK_END))
            if sec >= n:
                raise SystemExit('★섹터 %d 파일 범위 밖' % sec)
            r.seek(sec * RAW)
            h = r.read(16)
            if h[:12] != SY or h[15] != 1:
                raise SystemExit('★섹터 %d MODE1 아님' % sec)
        # 기존 폰트(720글리프=45섹터) 뒤로 새로 쓰는 섹터는 **비어 있어야** 한다
        # (--resync는 이미 우리가 쓴 자리를 다시 쓰는 것이므로 이 검사를 건너뛴다)
        for sec in ([] if not check_empty else
                    range(LBA + (BASE_N * GLYPH + USER - 1) // USER, LBA + nsec)):
            if any(read_file(r, sec, USER)):
                raise SystemExit('★확장 섹터 %d 가 비어있지 않다' % sec)
    print('관문 통과 — lba %d..%d (트랙 끝 %d 이내), 전부 MODE1.' % (LBA, LBA + nsec - 1, TRACK_END))


def main():
    revert = '--revert' in sys.argv
    # ★--resync: 번역을 수정해 재기록할 때. 현재 값이 원본이든 옛 패치본이든 **새 계획으로 덮는다**.
    #   구성이 바뀌면 --write(원본 기대)도 --revert(패치본 기대)도 대조에 걸린다(세션12 교훈).
    #   안전장치 = 덮기 전 현재 바이트에 **구분자(0xFFFF) 없음 + 전부 폰트 범위 안**인지 확인.
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    fwd, rev = load_map()
    base, extra, slot = build_slots()
    print('메뉴 기존 %d음절(594~%d) 고정 + 브리핑 신규 %d음절(%d~%d)'
          % (len(base), BASE_N - 1, len(extra), BASE_N, BASE_N + len(extra) - 1))

    f = open(TRACK1, 'rb')
    gl, gsz = [(l, s) for p, l, s in files(skip_media=False) if p == '/GMSELDT'][0]
    d = read_file(f, gl, gsz)
    f.close()
    plans = plan(d, fwd, rev, slot)
    hits, rlba, rsize, font, new_n = build_font(dst, extra)
    nsec = (len(font) + USER - 1) // USER
    print('ASCGSCG %d→%d글리프 (%dB / %d섹터, lba %d..%d), 폰트 천장 900 대비 여유 %d'
          % (BASE_N, new_n, len(font), nsec, LBA, LBA + nsec - 1, 900 - new_n))
    print('텍스트 %d곳 (설명문 %d + 미션명 %d):'
          % (len(plans), sum(1 for p in plans if not p[3].startswith('#')),
             sum(1 for p in plans if p[3].startswith('#'))))
    for off, raw, nb, label, kr in plans:
        print('  0x%06x %-14s → %s' % (off, label, kr))

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --revert).')
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
            put(LBA, font[:BASE_N * GLYPH])                     # 720글리프까지만 남기고
            put(LBA + (BASE_N * GLYPH) // USER,                 # 뒤 확장분 제로화
                bytes((nsec - (BASE_N * GLYPH) // USER) * USER))
        else:
            put(LBA, font)
        put(rlba, bytes(rd))
        for off, raw, nb, label, kr in plans:
            src, dstb = (nb, raw) if revert else (raw, nb)
            if resync:
                # 현재 값을 읽어 안전성만 확인하고 새 계획으로 덮는다
                cur = bytearray(len(raw))
                for k in range(len(raw)):
                    lo = off + k
                    sec = gl + lo // USER
                    w.seek(sec * RAW + HDR + lo % USER)
                    cur[k] = w.read(1)[0]
                for k in range(0, len(cur), 2):
                    v = struct.unpack_from('>H', cur, k)[0]
                    if v == 0xFFFF:
                        raise SystemExit('resync 중단 — 0x%x(%s)에 구분자가 있다' % (off + k, label))
                    if v and v >= new_n:
                        raise SystemExit('resync 중단 — 0x%x(%s) 글리프 %d ≥ %d'
                                         % (off + k, label, v, new_n))
            for k in range(len(raw)):
                lo = off + k
                sec = gl + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if not resync and w.read(1) != src[k:k + 1]:
                    raise SystemExit('GMSELDT 0x%x 대조실패 (%s) — %s'
                                     % (lo, label, '패치본아님' if revert else '이미패치?'))
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
        verify(dst, plans, font, gl)


def verify(dst, plans, font, gl):
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
        end = max(off + len(nb) for off, raw, nb, l, k in plans) + 4
        g = read_file(r, gl, end)
        for off, raw, nb, label, kr in plans:
            if g[off:off + len(nb)] != nb:
                bad += 1
                print('  ❌텍스트 0x%x (%s)' % (off, label))
        secs = set()
        for off, raw, nb, l, k in plans:
            for i in range(len(nb)):
                secs.add(gl + (off + i) // USER)
        for s in range(LBA, LBA + (len(font) + USER - 1) // USER):
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
