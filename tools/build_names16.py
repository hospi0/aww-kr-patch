# -*- coding: utf-8 -*-
"""편성명 테이블(85슬롯) + 상황표 타이틀 = **영문화** (세션10, 예산 0).

- 편성명 테이블: **8글리프(0x10바이트) 고정 슬롯** 배열. GMDT·KEKKA·SAKUSEN **3벌 사본**.
  HUD/결과/작전 화면이 시나리오별 해당 측 이름을 여기서 읽는다. 실존 WW2 편성이라 역사 표기.
  ★슬롯 내 「영문 글리프 + 널패딩」으로 채워 **총 길이 불변**(뒤 안 밀림, 포인터 안전).
- 상황표 타이틀: GAME `0x097b24` 作戦情報→INFO, `0x097b2e` 拠点情報→BASE (4글리프+0xFFFF 종료자).

폰트 인덱스는 SAKUCG 맵이 3모듈 실데이터와 일치(A=0x0b 실측). 공백=index0(=널). 하이픈=0xe1.
예산 0 — 라틴 글리프는 이미 폰트에 있다. 한글 메시지 81개는 그대로 유지.

제자리 패치 원칙: **계획=원본 TRACK1에서, 기록=F: ISO에서**(멱등). 되돌리기 `--revert`.
"""
import os
import json
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

# 편성명 테이블 = 3벌 사본. 슬롯 8글리프.
NAME_MODULES = ('GMDT', 'KEKKA', 'SAKUSEN')
SLOT = 8                       # 글리프
ANCHOR = 'ポーランド軍'         # 테이블 slot#1(고유) — 이걸로 테이블 시작 잡는다
SLOT0 = '南方軍集団'            # slot#0 검증용

# 원문 → 영문(≤8자). 실존 WW2 편성 역사 표기.
TABLE = {
    '南方軍集団': 'SOUTH', 'ポーランド軍': 'POLAND', '北方軍集団': 'NORTH', 'B軍集団': 'GROUP B',
    'オランダ軍': 'HOLLAND', 'ベルギー軍': 'BELGIUM', 'イギリス軍': 'BRITAIN', 'A軍集団': 'GROUP A',
    'フランス軍': 'FRANCE', 'ドイツ軍': 'GERMANY', 'アフリカ軍団': 'AFR CORP', 'イギリス第8軍': 'UK 8TH',
    'イタリア軍': 'ITALY', 'トブルク守備隊': 'TOBRUK', '第1装甲集団': '1PZ GRP', 'ユーゴスラビア軍': 'YUGOSLAV',
    'ハンガリー軍': 'HUNGARY', '中央軍集団': 'CENTER', '西方面軍': 'W FRONT', '北西方面軍': 'NW FRONT',
    '南西方面軍': 'SW FRONT', '予備方面軍': 'RESERVE', 'カリーニン方面軍': 'KALININ', 'キエフ軍管区': 'KIEV',
    '中央方面軍': 'C FRONT', 'ヴォロネジ方面軍': 'VORONEZH', 'ステップ方面軍': 'STEPPE', 'S・グラードFT': 'STALIN',
    '第62軍': '62ND', '南東方面軍': 'SE FRONT', 'ドン軍集団': 'DON', 'ドン方面軍': 'DON FR',
    '第2ウクライナ軍': '2 UKR', '第3ウクライナ軍': '3 UKR', 'ベルリン守備隊': 'BERLIN', '白ロシア方面軍': 'BELORUS',
    'ブリヤンスク軍': 'BRYANSK', '第1ウクライナ軍': '1 UKR', '英国空軍': 'RAF', 'ドイツ空軍': 'LUFTWAFF',
    'イタリア海軍': 'IT NAVY', 'イギリス海軍': 'RN', '英第30軍団': '30 CORP', '英第13軍団': '13 CORP',
    'アフリカ装甲軍': 'AFR PZ', '英第10軍団': '10 CORP', 'アメリカ軍': 'USA', 'アフリカ軍集団': 'AFRICA',
    'コーカサスFT': 'CAUCASU', 'コーカサス方面軍': 'CAUCASU', 'イギリス第5軍団': 'UK 5 CO', 'アメリカ第2軍団': 'US 2 CO',
    'イギリス第9軍団': 'UK 9 CO', '独伊連合軍': 'GER-ITA', 'アメリカ第7軍': 'US 7TH', 'C軍集団': 'GROUP C',
    'アメリカ第5軍': 'US 5TH', 'イギリス第2軍': 'UK 2ND', 'アメリカ第1軍': 'US 1ST', '沿岸防衛隊': 'COASTAL',
    'ラストバタリオン': 'LAST BN', 'ヴィスツラ軍集団': 'VISTULA', 'ウクライナ方面軍': 'UKRAINE', 'アメリカ3軍': 'US 3RD',
    '第1バルト方面軍': '1 BALTIC', '第12軍集団': '12TH', '第21軍集団': '21ST', '西側連合軍': 'ALLIES',
    'ドイツ青軍': 'GER BLUE', 'ドイツ赤軍': 'GER RED', '防衛ライン': 'DEF LINE', '南極守備隊': 'ANTARCT',
    'クロアチア軍': 'CROATIA', 'ソビエト軍': 'SOVIET', 'フランス軍Ⅰ': 'FRANCE I', 'フランス軍Ⅱ': 'FRANCE 2',
    'フランス軍Ⅲ': 'FRANCE 3', '84軍団': '84 CORP', 'ルーマニア第4軍': 'ROM 4TH', 'ルーンハンター隊': 'RUNEHUNT',
}
# 상황표 타이틀 (GAME) — 4글리프 필드 + 0xFFFF 종료자
TITLES = {'作戦情報': 'INFO', '拠点情報': 'BASE'}


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
    """문자열 → 글리프 인덱스 바이트. 없으면 전각 폴백."""
    out = bytearray()
    for c in s:
        idx = REV.get(c)
        if idx is None and 0x21 <= ord(c) <= 0x7E:
            idx = REV.get(chr(ord(c) + 0xFEE0))
        if idx is None:
            raise SystemExit('글리프 없음: %r (%r)' % (c, s))
        out += struct.pack('>H', idx)
    return bytes(out)


def enc_slot(en, mod=None):
    """이름 → 8글리프(16바이트) 슬롯: 글리프 + 널패딩."""
    b = enc_mod(en, mod) if mod else enc(en)
    if len(b) > SLOT * 2:
        raise SystemExit('%r 이 %d글리프 > %d' % (en, len(b) // 2, SLOT))
    return b + b'\x00' * (SLOT * 2 - len(b))


def decode_slot(d, o):
    """슬롯 선두 글리프를 널 전까지 문자열로."""
    out = []
    for k in range(SLOT):
        idx = struct.unpack_from('>H', d, o + 2 * k)[0]
        if idx == 0:
            break
        out.append(CM.get(idx, '?'))
    return ''.join(out)


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def plan_table(d, mod):
    """편성명 테이블 슬롯 치환 계획. base_lba는 오류메시지용(미사용)."""
    anchor = enc(ANCHOR)
    i = d.find(anchor)
    if i < 0:
        raise SystemExit('앵커 %s 못 찾음' % ANCHOR)
    start = i - 0x10                       # slot#1 앞이 slot#0
    if decode_slot(d, start) != SLOT0:
        raise SystemExit('테이블 slot0=%r (기대 %s)' % (decode_slot(d, start), SLOT0))
    plans = []
    for si in range(90):                   # 85슬롯 + 여유
        o = start + si * 0x10
        name = decode_slot(d, o)
        if name in TABLE:
            old = d[o:o + SLOT * 2]
            new = enc_slot(TABLE[name], mod)
            if old != new:
                plans.append((o, old, new, name, TABLE[name]))
        elif si > 84 and name not in TABLE:
            break                          # 테이블 끝 지나면 중단
    return plans


def plan_titles(d, mod):
    plans = []
    for jp, en in TITLES.items():
        pat = enc(jp)
        i = d.find(pat)
        if i < 0:
            raise SystemExit('타이틀 %s 못 찾음' % jp)
        old = d[i:i + len(pat)]
        new = enc_mod(en, mod)
        if len(new) != len(pat):
            raise SystemExit('%s→%s 길이 불일치' % (jp, en))
        # 종료자(다음 워드) 보존 확인
        if struct.unpack_from('>H', d, i + len(pat))[0] != 0xFFFF:
            raise SystemExit('%s 뒤 종료자 아님' % jp)
        if old != new:
            plans.append((i, old, new, jp, en))
    return plans


def build_plans(f):
    out = []
    for mod in NAME_MODULES:
        hits, _, _, _ = find_dirrec(f, mod)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 %d개' % (mod, len(hits)))
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
        pl = plan_table(d, mod)
        print('%-8s lba=%-6d 편성명 %d슬롯 치환' % (mod, lba, len(pl)))
        out.append((mod, lba, size, [(o, a, b) for o, a, b, _, _ in pl]))
    hits, _, _, _ = find_dirrec(f, 'GAME')
    _, lba, size, _ = hits[0]
    d = read_file(f, lba, size)
    tp = plan_titles(d, 'GAME')      # ★상황표 타이틀은 GAME 모듈 = ASC16CG 렌더
    for o, a, b, jp, en in tp:
        print('GAME     타이틀 0x%06x  %s → %s' % (o, jp, en))
    out.append(('GAME', lba, size, [(o, a, b) for o, a, b, _, _ in tp]))
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
            for off, old, new in pl:
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
            for off, old, new in pl:
                want = old if revert else new
                if d[off:off + len(want)] != want:
                    bad += 1
                    print('  ❌%s 0x%06x 되읽기 불일치' % (mod, off))
        for mod, lba, size, pl in plans:
            for off, old, _new in pl:
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
    n = sum(len(p[3]) for p in plans)
    print('\n합계 %d곳 치환' % n)
    if not ('--write' in sys.argv or revert or RESYNC):
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    apply(plans, revert)


# ── 세션15: 편성명·상황표 타이틀 = **한글**(kr_s15) ────────────────────────
# 영문판 보관 = archive/en_tables_2026-07-26/build_names16.py
import sys as _sys
if '--en' not in _sys.argv:
  try:
    import kr_s15 as _S
    TABLE = {jp: _S.FORMATIONS.get(jp, en) for jp, en in TABLE.items()}
    TITLES = {jp: _S.INFO_TITLES.get(jp, en) for jp, en in TITLES.items()}
  except ImportError:
    print('⚠️ kr_s15 없음 — 편성명은 영문 그대로')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
