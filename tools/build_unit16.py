# -*- coding: utf-8 -*-
"""전투 유닛 패널의 16×16 유닛명 로마자화 (세션8).

대상 = MUSEUM 유닛 DB의 **16×16 이름 필드**. 전투 화면 좌측 큰 패널(「歩兵」「38t式戦車A型」)과
병기도감이 같은 표를 읽는다.

★구조: 레코드 base `0x7E404`, stride `0x52`, **+0x00 = 16×16 이름(8글리프/16B 고정폭)**,
  **+0x10 = 소형폰트 이름(8B)** — 세션4가 찾은 「유닛 DB 0x7e3c2 stride 0x52」와 같은 표인데
  세션4는 소형폰트 이름에 위상을 맞춰 +0으로 불렀다. 16×16 필드는 그 표의 **다른 필드**다.
  ⚠️두 필드의 위상이 0x42 어긋나므로 대응을 잘못 맞추면 전 유닛 이름이 한 칸씩 밀린다.

★★예산 0: 로마자·숫자는 ASC16CG의 기존 글리프(0~824)라 **폰트를 전혀 안 건드린다**.
  한글로 하면 신규 70음절 = 성장 슬롯 75칸 중 70을 소모하는데, 900 천장(= VDP2 VRAM
  0x1E00 + 900×128 = 0x1E000 배치 한계) 안에서 본문 번역이 이미 빠듯하므로 그 칸을 남긴다.

이름 결정 규칙(사용자 선택 = B안):
  ① 원문이 라틴·숫자뿐(PSW222, AB41 …)        → 손대지 않음
  ② 한자 서술형 중 **육상·시설**(歩兵, 工兵 …)   → **영어 단어로 풀어씀**(8칸 한도)
     ★해군은 CL/CA/DD/SS 함종기호가 이 장르의 표준 표기라 축약을 유지한다
       (Submarin·Destroyr처럼 잘린 철자보다 낫다는 판단).
  ③ 나머지(가타카나·병기 제식명)                → **세션5의 기존 로마자 재사용**
     (PzKwⅢG·StuGⅢB·Panther… 제식명은 축약이 정답이라 풀어쓸 것이 없다)

⚠️소형폰트 코드표 오류 회피: 세션4가 소형폰트 162·165·166·167을 `[`·`]`·`✕`·`✖`로 읽었는데
  16×16 원문과 대조하면 **로마 숫자의 조각**이다(161+162=Ⅵ, 165+166=Ⅸ, 167=Ⅹ — 8×8 반각이라
  넓은 숫자가 두 칸에 걸친다). 그 글자를 쓰는 5종은 아래 NUM_FIX로 직접 지정한다.

빌드: python tools/build_unit16.py           드라이런
      python tools/build_unit16.py --write   F: ISO 제자리 기록
      python tools/build_unit16.py --revert  원상복구
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_smalltext as B
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
EXTRACT = os.path.join(ROOT, 'work', 'extract')

BASE16, STRIDE, NREC, WIDTH = 0x7E404, 0x52, 644, 8

# ★--resync (세션15-c): 슬롯 등록부 고정 이전에 기록된 값이 남아 있어 --write/--revert
#   양쪽 대조가 다 걸린다. 오프셋은 계획 단계에서 원본 대조로 확정했으므로 무조건 덮는다.
RESYNC = '--resync' in sys.argv

SMALL_OFF = 0x10

# ② 육상·시설 서술형 → 영어 풀어쓰기 (≤8글리프)
EN = {
    '歩兵': 'Infantry', '機械化歩兵': 'MechInf', '自動車化歩兵': 'MotorInf',
    '空挺隊': 'Airborne', '降下猟兵': 'Fallschr', '擲弾兵': 'Grenadr',
    '装甲擲弾兵': 'PzGrenad', 'SS装甲擲弾兵': 'SSPzGren', '狙撃兵': 'Sniper',
    '工兵': 'Engineer', '戦闘工兵': 'CmbtEngr', '義勇兵': 'Voluntr',
    '予備役兵': 'Reserve', '動員兵': 'Mobilzd', '州兵': 'NatGuard',
    '親衛赤軍': 'RedGuard', 'エリート兵': 'Elite', 'エリート歩兵': 'EliteInf',
    'スキー歩兵': 'SkiInf', '擲弾兵43': 'Grenad43', '歩兵44': 'Infant44',
    '輸送車': 'Truck', '補給車': 'Supply', '輸送機': 'TrnsPlan',
    '将軍輸送機': 'GenTrnsp', '輸送船': 'TrnsShip',
    '要塞': 'Fortress', 'マジノ要塞': 'Maginot', '構築陣地': 'DefPost',
    '沿岸砲台': 'CoastGun', '高射砲塔': 'FlakTowr', 'レーダー基地': 'RadarBse',
    'カタリナ飛行艇': 'Catalina', 'T-38水陸戦車': 'T-38Amph',
}

_KANJI = None
_KJ = None
_KTK = None

# ── 세션15: 서술형 유닛명 = **한글**(kr_s15.UNIT16). 영문판은 archive/en_tables_2026-07-26/ 보관.
if '--en' not in sys.argv:   # --en = 세션8 영문표 그대로(되돌리기용)
  try:
    import kr_s15 as _S
    # ★★세션15-e 버그수정: 예전엔 `{jp: UNIT16.get(jp, en) for jp, en in EN.items()}` 로
    #   **원래 EN 키만** 순회해서, UNIT16 에 새로 넣은 해상유닛 13종이 통째로 무시됐다
    #   (실기: 병기도감 해상유닛이 CL/CA/DD/SS 그대로).
    #   ⇒ UNIT16 을 **병합**한다.
    EN = dict(EN)
    EN.update(_S.UNIT16)
    _KANJI = _S.kanji_unit
    _KJ = _S.KANJI_UNITS
    import katakana_kr as _KK
    _KTK = _KK        # 가타카나 유닛명 195종(세션15-f 사용자 결정)
  except ImportError:
    print('⚠️ kr_s15 없음 — 영문 유닛명 그대로 사용')


# ⚠️로마 숫자 조각을 쓰는 5종 — 소형폰트 로마자가 깨져 있어 직접 지정
NUM_FIX = {
    # ★세션15-e: 소형폰트 8자 제한 탓에 `MarderⅢ(r)` 이 `MarderⅢ)` 로 잘려 있었다.
    #   (r)=노획 소련제 포 탑재형. 16×16 도 8글리프라 `MarderⅢr` 로 의미를 살린다.
    'マーダーⅢ（r）': 'MarderⅢr',
    'スピットⅨ': 'SpitfirⅨ', 'スピットⅩⅣ': 'SpitfⅩⅣ',
    'バレンタインⅩⅠ': 'ValentⅩⅠ', 'チャーチルⅥ': 'ChurchⅥ',
}

# 반각 → 전각 (16×16 폰트는 전각 기호만 갖고 있다)
ALT = {'/': '／', '.': '．', '·': '・', ')': '）', '(': '（', '-': 'ー'}


def han(c):
    return '\u4e00' <= c <= '\u9fff'


def kana(c):
    return '\u30a0' <= c <= '\u30ff'


def load_map():
    m = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in m.items()}
    rev = {}
    for k, v in cm.items():
        rev.setdefault(v, k)
    return cm, rev


_SLOT = None


def slots():
    """한글 슬롯 = build_ui16 배정(ASC16CG 단일 할당자). build_ui16 을 먼저 돌려야 한다."""
    global _SLOT
    if _SLOT is None:
        import build_ui16
        _SLOT = build_ui16.build_slots()
    return _SLOT


def encode(s, rev):
    out = bytearray()
    for ch in s:
        if '가' <= ch <= '힣':                    # 세션15: 서술형 유닛명 한글화
            gi = slots().get(ch)
            if gi is None:
                raise SystemExit('한글 슬롯 없음 %r in %r' % (ch, s))
        else:
            c = ch if ch in rev else ALT.get(ch)
            if c is None or c not in rev:
                raise SystemExit('인코딩불가 %r in %r' % (ch, s))
            gi = rev[c]
            if gi > 824:
                raise SystemExit('글리프 %d(%r) 는 ASC16CG(825) 밖 — SAKUCG 전용' % (gi, c))
        out += struct.pack('>H', gi)
    return bytes(out).ljust(WIDTH * 2, b'\x00')


def plan():
    cm, rev = load_map()
    d = open(os.path.join(EXTRACT, 'MUSEUM'), 'rb').read()
    _, rows = B.load_tsv()
    byoff = {int(r[2], 16): r for r in rows if r[1] == 'units'}
    p, stats = [], {'라틴유지': 0, '영어풀이': 0, '한자한글': 0, '가타카나한글': 0, '기존로마자': 0, '수동': 0}
    for r in range(NREC):
        o = BASE16 + r * STRIDE
        raw = d[o:o + WIDTH * 2]
        s = ''
        for i in range(0, WIDTH * 2, 2):
            v = (raw[i] << 8) | raw[i + 1]
            if v in (0, 0xFFFF):
                continue
            s += cm.get(v, '?')
        s = s.strip()
        if not s or '?' in s:
            continue
        if not any(han(c) or kana(c) for c in s):     # ① 라틴·숫자뿐
            stats['라틴유지'] += 1
            continue
        if s in NUM_FIX:
            new, k = NUM_FIX[s], '수동'
        elif s in EN:
            new, k = EN[s], '영어풀이'
        elif _KJ is not None and s in _KJ:
            # ★세션15-d(사용자 결정): **한자만으로 된 이름은 한글로 번역**.
            #   3号戦車G型→3호전차G형 · 88㎜対戦車砲→88㎜대전차포 · 零式艦上21型→영식함상21형
            #   ⚠️가타카나 고유명사(Tiger·Bismarck…)는 그대로 로마자 — 그건 일본어 음차를
            #     원어로 되돌린 것이라 한글 음차로 바꿔봐야 이득이 없다.
            new, k = _KJ[s], '한자한글'
        elif _KTK is not None and _KTK.to_kr(s):
            # ★세션15-f: 가타카나 유닛명도 **한글**(사용자 결정). 제식기호(Ⅰ·L6·AA)는 유지.
            new, k = _KTK.to_kr(s), '가타카나한글'
        else:                                          # ③ 기존 로마자
            t = byoff.get(o + SMALL_OFF)
            if not t or not t[7]:
                raise SystemExit('rec %d (%s) 로마자 없음' % (r, s))
            new, k = t[7], '기존로마자'
        if len(new) > WIDTH:
            raise SystemExit('rec %d %r -> %r 폭 %d>%d' % (r, s, new, len(new), WIDTH))
        nb = encode(new, rev)
        if nb != raw:
            p.append((r, o, raw, nb, s, new))
            stats[k] += 1
    return p, stats, cm


def rw(dst, p, revert=False):
    import ecc
    hits, _, _, _ = find_dirrec(open(dst, 'rb'), 'MUSEUM')
    if len(hits) != 1:
        raise SystemExit('MUSEUM 디렉터리 %d개' % len(hits))
    lba = hits[0][1]
    print('MUSEUM lba=%d' % lba)
    touched = set()
    with open(dst, 'r+b') as w:
        for r, o, old, new, jp, en in p:
            src, dstb = (new, old) if revert else (old, new)
            for k in range(len(old)):
                lo = o + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                if w.read(1) != src[k:k + 1] and not RESYNC:
                    raise SystemExit('rec %d @0x%x 대조 실패 (%s)'
                                     % (r, o, '패치본 아님' if revert else '이미 패치됨?'))
                w.seek(pos)
                w.write(dstb[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    return lba


def verify_iso(dst, p, lba, revert, cm):
    """독립 되읽기 — 기록된 ISO를 다시 읽어 디코드까지 확인."""
    bad = 0
    with open(dst, 'rb') as r:
        for rec, o, old, new, jp, en in p:
            want = old if revert else new
            got = bytearray()
            for k in range(len(want)):
                lo = o + k
                r.seek((lba + lo // USER) * RAW + HDR + (lo % USER))
                got += r.read(1)
            if bytes(got) != want:
                bad += 1
                print('  ❌rec %d 되읽기 불일치' % rec)
                continue
            if not revert:
                # ★세션15: 한글 글리프는 공용 charmap 이 모르는 **우리 배정 슬롯**이라
                #   역맵(슬롯→음절)을 먼저 본다. 안 그러면 멀쩡한 한글이 'サホ?陥' 로 읽혀
                #   거짓 실패가 난다(실제로 54건 났다).
                inv = {gi: c for c, gi in slots().items()}
                s = ''
                for i in range(0, len(got), 2):
                    v = (got[i] << 8) | got[i + 1]
                    if v in (0, 0xFFFF):
                        continue
                    s += inv.get(v) or cm.get(v, '?')
                # ★인코더와 **같은 규칙**으로 기대값을 만들어야 한다. 인코더는 폰트에 있는
                #   글자를 우선 쓰고 없을 때만 전각으로 바꾼다. 공백은 글리프0이라 디코드에서
                #   사라지므로 기대값에서도 뺀다(첫 실행에서 이 둘 때문에 거짓 실패 3건이 났다).
                _, rv = load_map()
                want_s = ''.join((c if c in rv else ALT.get(c, c)) for c in en if c != ' ')
                if s.strip() != want_s.strip():
                    bad += 1
                    print('  ❌rec %d 디코드 %r != %r' % (rec, s.strip(), en))
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립 되읽기 통과 (%d레코드).' % len(p))


def main():
    p, stats, cm = plan()
    print('패치 레코드 %d개  %s' % (len(p), stats))
    print()
    for rec, o, old, new, jp, en in p[:5] + p[len(p) // 2:len(p) // 2 + 3] + p[-3:]:
        print('   rec %3d @0x%06x  %-13s -> %s' % (rec, o, jp, en))
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    rev = '--revert' in sys.argv
    if not rev and '--write' not in sys.argv and not RESYNC:
        print('\n드라이런 — 미기록 (--write / --revert).')
        return
    lba = rw(dst, p, revert=rev)
    verify_iso(dst, p, lba, rev, cm)
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
