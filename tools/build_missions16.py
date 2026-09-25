# -*- coding: utf-8 -*-
"""미션 타이틀 테이블(16×16, 66엔트리) = **영문화** (세션11, 예산 0).

브리핑·상황 화면 좌상단 미션명(`マンシュタイン計画` 등)이 일본어로 남아 있었다.
이건 세션8 game_pool의 **소형폰트 미션 SELECT 리스트와 별개인 16×16 타이틀 테이블**이다.

구조: **stride 0x18(12글리프 고정폭), 좌측정렬 널패딩, 66엔트리(0~65)**. 3벌 사본:
    GMDT(브리핑/상황, GAME→ASC16CG 렌더) · KEKKA(결과) · SAKUSEN(작전, SAKUCG)
  순서가 game_pool.MISSIONS와 인덱스 1:1 일치(entry0=士官学校 entry4=マンシュタイン計画
  entry64=完全なる勝利へ entry65=関ヶ原の戦い). 영문명은 game_pool 것을 재사용(세션8 사인오프).
  ★entry65 関ヶ原の戦い(세키가하라, 보너스 미션)만 game_pool에 없어 → Sekigahara.

폰트: 라틴은 SAKUCG 맵이 3모듈 실데이터와 일치(A=0x0b, [[build_names16]] 실측). 공백=index0.
예산 0 — 라틴 글리프는 이미 폰트에 있다.

앵커 기반 base 탐지(하드코딩 금지): `マンシュタイン計画`(entry4) → base = hit-4*0x18,
  entry0=士官学校 검증. SAKUSEN은 히트 2개 중 entry0=士官学校인 것만 채택(다른 하나는 본문).

제자리 패치 원칙: 계획=원본 TRACK1, 기록=F: ISO(멱등). 되돌리기 `--revert`.

빌드: python tools/build_missions16.py            드라이런
      python tools/build_missions16.py --write     F: ISO 기록
      python tools/build_missions16.py --revert    원상복구
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import game_pool_kr as GP
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

MODULES = ('GMDT', 'KEKKA', 'SAKUSEN')
STRIDE = 0x18                      # 24바이트 = 12글리프
NGLYPH = 12
NENT = 66                          # 0~65
ANCHOR = 'マンシュタイン計画'       # entry4
ENT0 = '士官学校'                  # entry0 검증
ENT65 = '関ヶ原の戦い'             # entry65 검증

# 영문 66개 = game_pool MISSIONS[0..64] + Sekigahara(관ヶ原)
ENGLISH = [m[1] for m in GP.MISSIONS] + ['Sekigahara']
assert len(ENGLISH) == NENT, '영문 %d개 (기대 %d)' % (len(ENGLISH), NENT)


def load_maps():
    fm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in fm.items()}
    rev = {}
    for k, v in fm.items():
        rev.setdefault(v, int(k))
    return cm, rev


CM, REV = load_maps()


# ── 세션15: 사본마다 **그 모듈 폰트의 한글 슬롯**으로 인코딩한다 ─────────────
#   GMDT·KEKKA = ASC16CG(build_ui16 배정) / SAKUSEN = SAKUCG(sakucg_kr 배정)
#   ★라틴은 세 폰트에서 인덱스가 같아 한 번에 됐지만(세션10·11), 한글은 폰트마다 다르다.
_KRSLOT = {}


def kr_slots(mod):
    if mod not in _KRSLOT:
        if mod == 'SAKUSEN':
            import sakucg_kr
            _KRSLOT[mod] = sakucg_kr.build_slots()
        else:
            import build_ui16
            _KRSLOT[mod] = build_ui16.build_slots()
    return _KRSLOT[mod]


# ★--resync (세션15-c): 슬롯 등록부 고정 이전에 기록된 값이 남아 있어 --write/--revert
#   양쪽 대조가 다 걸린다. 오프셋은 계획 단계에서 원본 대조로 확정했으므로 무조건 덮는다.
RESYNC = '--resync' in sys.argv


def enc_mod(s, mod):
    """모듈별 인코딩 — 한글은 그 폰트의 슬롯, 나머지는 기존 라틴 인덱스."""
    out = bytearray()
    sl = None
    for c in s:
        if '가' <= c <= '힣':
            if sl is None:
                sl = kr_slots(mod)
            idx = sl.get(c)
            if idx is None:
                raise SystemExit('%s 한글 슬롯 없음: %r (%r)' % (mod, c, s))
        else:
            idx = REV.get(c)
            if idx is None and 0x21 <= ord(c) <= 0x7E:
                idx = REV.get(chr(ord(c) + 0xFEE0))
            if idx is None:
                raise SystemExit('글리프 없음: %r (%r)' % (c, s))
        out += struct.pack('>H', idx)
    return bytes(out)


def enc(s):
    out = bytearray()
    for c in s:
        idx = REV.get(c)
        if idx is None and 0x21 <= ord(c) <= 0x7E:
            idx = REV.get(chr(ord(c) + 0xFEE0))
        if idx is None:
            raise SystemExit('글리프 없음: %r (%r)' % (c, s))
        out += struct.pack('>H', idx)
    return bytes(out)


def enc_field(en, mod=None):
    """이름 → 12글리프(24바이트) 필드: 글리프 + 널패딩."""
    b = enc_mod(en, mod) if mod else enc(en)
    if len(b) > NGLYPH * 2:
        raise SystemExit('%r 이 %d글리프 > %d' % (en, len(b) // 2, NGLYPH))
    return b + b'\x00' * (NGLYPH * 2 - len(b))


def decode_field(d, o):
    out = []
    for k in range(NGLYPH):
        idx = struct.unpack_from('>H', d, o + 2 * k)[0]
        if idx == 0:
            break
        out.append(CM.get(idx, '?%d' % idx))
    return ''.join(out)


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def find_base(d):
    """앵커(entry4)로 테이블 base 탐지 + entry0/entry65 검증."""
    anc = enc(ANCHOR)
    e0 = enc(ENT0)
    e65 = enc(ENT65)
    i = d.find(anc)
    while i >= 0:
        base = i - 4 * STRIDE
        if base >= 0 and d[base:base + len(e0)] == e0 \
                and d[base + 65 * STRIDE:base + 65 * STRIDE + len(e65)] == e65:
            return base
        i = d.find(anc, i + 1)
    raise SystemExit('미션 테이블 base 못 찾음 (entry0=士官学校·entry4=%s·entry65=関ヶ原 미충족)' % ANCHOR)


def plan_module(d, mod):
    base = find_base(d)
    plans = []
    for i in range(NENT):
        o = base + i * STRIDE
        old = d[o:o + NGLYPH * 2]
        # 안전: 원본 첫 글리프가 널이면 미션 테이블 밖(편성명) — 중단
        if struct.unpack_from('>H', d, o)[0] == 0:
            raise SystemExit('entry%d 원본 선두 널 — 테이블 경계 이상' % i)
        new = enc_field(ENGLISH[i], mod)
        if old != new:
            plans.append((o, old, new, decode_field(d, o), ENGLISH[i]))
    return base, plans


def build_plans(f):
    out = []
    for mod in MODULES:
        hits, _, _, _ = find_dirrec(f, mod)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 %d개' % (mod, len(hits)))
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
        base, pl = plan_module(d, mod)
        print('%-8s lba=%-6d base=0x%06x 미션 %d엔트리 치환' % (mod, lba, base, len(pl)))
        out.append((mod, lba, size, pl))
    return out


def apply(plans, revert=False):
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    print('\nF: ISO 제자리 %s: %s' % ('원상복구' if revert else '패치', dst))
    touched = set()

    def sect_pos(lba, lo):
        sec = lba + lo // USER
        return sec, sec * RAW + HDR + lo % USER

    with open(dst, 'r+b') as w:
        skipped = 0
        for mod, lba, size, pl in plans:
            for off, old, new, _jp, _en in pl:
                src, tgt = (new, old) if revert else (old, new)
                cur = bytearray(len(old))
                for k in range(len(old)):
                    _, pos = sect_pos(lba, off + k)
                    w.seek(pos)
                    cur[k] = w.read(1)[0]
                cur = bytes(cur)
                if cur == tgt:
                    skipped += 1
                    continue
                if cur != src and not RESYNC:
                    raise SystemExit('%s 0x%06x 대조 실패(cur=%s src=%s)'
                                     % (mod, off, cur.hex(), src.hex()))
                for k in range(len(old)):
                    sec, pos = sect_pos(lba, off + k)
                    w.seek(pos)
                    w.write(tgt[k:k + 1])
                    touched.add(sec)
        print('쓴 섹터 %d개 (건너뜀 %d), EDC/ECC 재계산...' % (len(touched), skipped))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    with open(dst, 'rb') as r:
        bad = 0
        for mod, lba, size, pl in plans:
            d = read_file(r, lba, size)
            for off, old, new, _jp, _en in pl:
                want = old if revert else new
                if d[off:off + len(want)] != want:
                    bad += 1
                    print('  ❌%s 0x%06x 되읽기 불일치' % (mod, off))
        for mod, lba, size, pl in plans:
            for off, old, _new, _jp, _en in pl:
                for sec in {lba + (off + k) // USER for k in range(len(old))}:
                    r.seek(sec * RAW)
                    raw = r.read(RAW)
                    if ecc.fix_sector(raw) != raw:
                        bad += 1
                        print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 되읽기 일치, EDC/ECC 유효.')


def main():
    revert = '--revert' in sys.argv
    with open(TRACK1, 'rb') as f:
        plans = build_plans(f)
    # 매핑 미리보기(GMDT 기준)
    print('\n[GMDT 매핑 미리보기]')
    for off, old, new, jp, en in plans[0][3]:
        print('  0x%06x %-14s → %s' % (off, jp, en))
    n = sum(len(p[3]) for p in plans)
    print('\n합계 %d곳 치환 (3벌)' % n)
    if not ('--write' in sys.argv or revert or RESYNC):
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    apply(plans, revert)



# ── 세션15: 미션 타이틀 = **한글**(kr_s15.MISSION16) ──────────────────────
# 영문판 보관 = archive/en_tables_2026-07-26/build_missions16.py
import sys as _sys
if '--en' not in _sys.argv:
  try:
    import kr_s15 as _S
    ENGLISH = list(_S.MISSION16)
  except ImportError:
    print('⚠️ kr_s15 없음 — 미션 타이틀은 영문 그대로')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
