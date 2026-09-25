# -*- coding: utf-8 -*-
"""부대정보 화면 타입값(병기타입·이동타입) = **영문화** (세션11, 예산 0).

부대정보 화면에서 兵器タイプ의 값(偵察車 등)·移動タイプ의 값(ハーフトラック弱型 등)이
일본어로 남아 있었다. 라벨은 한글(build_ui16 UNITINFO), 값은 사용자 결정으로 **영문/로마자**.
유닛명이 이미 로마자라 일관되고, 라틴 글리프는 폰트에 이미 있어 예산 0.

구조(GMDT, GAME→ASC16CG 렌더):
  병기타입값 base 0x17282, stride 0xe(**7글리프**), 0~16 + 20~37(17~19 빈슬롯 skip)
  이동타입값 base 0x174b6, stride 0x12(**9글리프**), 0~12
  좌측정렬 널패딩(원본과 동일). 폰트 = SAKUCG 맵(라틴 A=0x0b, [[build_names16]]).

함선은 세션8-a [[build_unit16]] 방식대로 함종기호(BB/CA/CL/DD/SS/CV), 육상은 영어 축약.
⚠️7글리프 제약이라 Infantry(8)→Inf, Engineer(8)→Enginer 식으로 줄임.

제자리 패치: 계획=원본 TRACK1, 기록=F: ISO(멱등). 되돌리기 `--revert`.

빌드: python tools/build_typevals.py            드라이런
      python tools/build_typevals.py --write     F: ISO 기록
      python tools/build_typevals.py --revert    원상복구
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

# (base, stride, 글리프폭, [(index, 원문, 영문)])  — index는 검증용(원본 대조)
WEAPON = (0x17282, 0xe, 7, [
    # ★세션18: 표의 **진짜 시작은 0x171E8**(ダミー)인데 세션11이 0x17282(偵察車)로 잡아
    #   **앞 11칸(ダミー + 항공기 10종)이 통째로 빠졌다** — 실기 `히鬪약`(戦闘機)·
    #   `지降下爆승약`(急降下爆撃機). 음수 인덱스로 그 앞칸을 되찾는다.
    #   ([[feedback_kr_patch_verification]] §23 「풀 경계가 몇 칸만 어긋나도 조용히 미번역」)
    (-11, 'ダミー', '더미'), (-10, '艦上戦闘機', '함상전투기'), (-9, '戦闘機', '전투기'),
    (-8, '局地戦闘機', '국지전투기'), (-7, '戦闘攻撃機', '전투공격기'),
    (-6, '急降下爆撃機', '급강하폭격기'), (-5, '艦上攻撃機', '함상공격기'),
    (-4, '陸上攻撃機', '육상공격기'), (-3, '爆撃機', '폭격기'),
    (-2, '夜間戦闘機', '야간전투기'),
    (0, '偵察車', 'Scout'), (1, '軽戦車', 'LtTank'), (2, '中戦車', 'MdTank'),
    (3, '重戦車', 'HvTank'), (4, '突撃砲', 'StuG'), (5, '駆逐戦車', 'TankDes'),
    (6, '対空戦車', 'AATank'), (7, '自走高射砲', 'SPAAG'), (8, '自走榴弾砲', 'SPHow'),
    (9, '自走ロケット砲', 'SPRkt'), (10, '牽引対戦車砲', 'TowAT'), (11, '牽引高射砲', 'TowAA'),
    (12, '牽引榴弾砲', 'TowHow'), (13, '歩兵', 'Inf'), (14, '機械化歩兵', 'MechInf'),
    (15, '空挺歩兵', 'Airborn'), (16, '列車砲', 'RailGun'),
    (20, '戦艦', 'BB'), (21, '巡洋戦艦', 'BC'), (22, '重巡洋艦', 'CA'),
    (23, '軽巡洋艦', 'CL'), (24, '駆逐艦', 'DD'), (25, '潜水艦', 'SS'),
    (26, '空母', 'CV'), (27, '軽空母', 'CVL'), (28, '変形要塞', 'Fortres'),
    (29, '工兵', 'Enginer'), (30, '輸送機', 'TrspAir'), (31, '輸送車', 'Truck'),
    (32, '司令部', 'HQ'), (33, '輸送船', 'TrspShp'), (34, '（重巡）', '(CA)'),
    (35, '（戦艦）', '(BB)'), (36, '（空母）', '(CV)'), (37, '補給車', 'Supply'),
    # 세션18: 표 **끝칸**도 빠져 있었다(앞 11칸과 같은 원인 — 경계 오판)
    (38, 'トーチカ／要塞', '토치카／요새'),
])
MOVE = (0x174b6, 0x12, 9, [
    (0, 'キャタピラ弱型', 'TrackWk'), (1, 'キャタピラ型', 'Tracked'),
    (2, 'キャタピラ水陸型', 'TrackAmp'), (3, 'ハーフトラック弱型', 'HalfTrkW'),
    (4, 'ハーフトラック型', 'HalfTrack'), (5, 'タイヤ型', 'Wheeled'), (6, '牽引型', 'Towed'),
    (7, '歩兵基本装備', 'InfBasic'), (8, '歩兵積雪装備', 'InfSnow'),
    (9, '歩兵自動車化装備', 'InfMotor'), (10, '固定型', 'Fixed'),
    (11, '艦船型', 'Naval'), (12, '航空機型', 'Air'),
])


def load_maps():
    fm = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in fm.items()}
    rev = {}
    for k, v in fm.items():
        rev.setdefault(v, int(k))
    return cm, rev


CM, REV = load_maps()

# ★--resync (세션15-c): 슬롯 등록부 고정 이전에 기록된 값이 남아 있어 --write/--revert
#   양쪽 대조가 다 걸린다. 오프셋은 계획 단계에서 원본 대조로 확정했으므로 무조건 덮는다.
RESYNC = '--resync' in sys.argv


# ── 세션15: 값 = **한글**(kr_s15). 세션11의 영문표는 archive/en_tables_2026-07-26/ 에 보관.
if '--en' not in sys.argv:   # --en = 세션11 영문표 그대로(되돌리기용)
  try:
    import kr_s15 as _S
    WEAPON = WEAPON[:3] + ([(i, jp, _S.TYPEVAL_WEAPON.get(jp, en)) for i, jp, en in WEAPON[3]],)
    MOVE = MOVE[:3] + ([(i, jp, _S.TYPEVAL_MOVE.get(jp, en)) for i, jp, en in MOVE[3]],)
  except ImportError:
    print('⚠️ kr_s15 없음 — 영문표 그대로 사용')

_SLOT = None


def slots():
    """한글 글리프 슬롯 = **build_ui16 의 배정을 그대로 쓴다**(ASC16CG 단일 할당자).

    ★따로 배정하면 같은 폰트에 두 벌이 생겨 서로를 덮는다. build_brief 가
      build_menu.build_slots() 를 쓰는 것과 같은 패턴.
    ⚠️build_ui16 이 폰트에 그 글리프를 써 넣으므로 **build_ui16 을 먼저 돌려야** 한다.
    """
    global _SLOT
    if _SLOT is None:
        import build_ui16
        _SLOT = build_ui16.build_slots()
    return _SLOT


def enc(s):
    out = bytearray()
    sl = None
    for c in s:
        if '가' <= c <= '힣':
            if sl is None:
                sl = slots()
            idx = sl.get(c)
            if idx is None:
                raise SystemExit('한글 슬롯 없음: %r (%r)' % (c, s))
        else:
            idx = REV.get(c)
            if idx is None and 0x21 <= ord(c) <= 0x7E:
                idx = REV.get(chr(ord(c) + 0xFEE0))
        if idx is None:
            raise SystemExit('글리프 없음: %r (%r)' % (c, s))
        out += struct.pack('>H', idx)
    return bytes(out)


def enc_field(en, w):
    b = enc(en)
    if len(b) > w * 2:
        raise SystemExit('%r %d글리프 > %d' % (en, len(b) // 2, w))
    return b + b'\x00' * (w * 2 - len(b))


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def plan_table(d, tbl, name):
    base, stride, w, ents = tbl
    plans = []
    for idx, jp, en in ents:
        o = base + idx * stride
        old = d[o:o + w * 2]
        want = enc(jp)
        if old[:len(want)] != want:
            raise SystemExit('%s idx%d @0x%06x 원문 불일치 (기대 %s)' % (name, idx, o, jp))
        new = enc_field(en, w)
        if old != new:
            plans.append((o, old, new, jp, en))
    return plans


def build_plans(f):
    hits, _, _, _ = find_dirrec(f, 'GMDT')
    if len(hits) != 1:
        raise SystemExit('GMDT 디렉터리 %d개' % len(hits))
    _, lba, size, _ = hits[0]
    d = read_file(f, lba, size)
    wp = plan_table(d, WEAPON, '병기')
    mv = plan_table(d, MOVE, '이동')
    print('GMDT lba=%d  병기 %d + 이동 %d 치환' % (lba, len(wp), len(mv)))
    return lba, size, wp + mv


def apply(lba, plans, revert=False):
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    print('\nF: ISO 제자리 %s: %s' % ('원상복구' if revert else '패치', dst))
    touched = set()

    def sect_pos(lo):
        sec = lba + lo // USER
        return sec, sec * RAW + HDR + lo % USER

    with open(dst, 'r+b') as w:
        skipped = 0
        for off, old, new, jp, en in plans:
            src, tgt = (new, old) if revert else (old, new)
            cur = bytearray(len(old))
            for k in range(len(old)):
                _, pos = sect_pos(off + k)
                w.seek(pos)
                cur[k] = w.read(1)[0]
            cur = bytes(cur)
            if cur == tgt:
                skipped += 1
                continue
            if cur != src and not RESYNC:
                raise SystemExit('0x%06x 대조 실패(cur=%s src=%s)' % (off, cur.hex(), src.hex()))
            for k in range(len(old)):
                sec, pos = sect_pos(off + k)
                w.seek(pos)
                w.write(tgt[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개 (건너뜀 %d), EDC/ECC 재계산...' % (len(touched), skipped))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    # 독립검증
    with open(dst, 'rb') as r:
        bad = 0
        for off, old, new, jp, en in plans:
            want = old if revert else new
            cur = bytearray(len(want))
            for k in range(len(want)):
                sec = lba + (off + k) // USER
                r.seek(sec * RAW + HDR + (off + k) % USER)
                cur[k] = r.read(1)[0]
            if bytes(cur) != want:
                bad += 1
                print('  ❌0x%06x 되읽기 불일치' % off)
        for off, old, _n, _jp, _en in plans:
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
        lba, size, plans = build_plans(f)
    print('\n[매핑]')
    for off, old, new, jp, en in plans:
        print('  0x%06x %-11s → %s' % (off, jp, en))
    print('\n합계 %d곳' % len(plans))
    if not ('--write' in sys.argv or revert or RESYNC):
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    apply(lba, plans, revert)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
