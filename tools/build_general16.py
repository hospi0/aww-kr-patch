# -*- coding: utf-8 -*-
"""좌패널 커맨더/부대명 16×16 로마자화 (세션8-a). 세션7 이월 잔여① 해소.

★발견: 미션 UPK 로스터 레코드(stride 0x62) 안에 **이름이 두 벌** 들어 있다.
    +0x00  16×16 이름 (8글리프 = 16B 고정폭)   ← 좌패널·유닛 상세 헤더에 뜬다. 아직 일본어.
    +0x3A  소형폰트 이름 (널종료 ≤8자)          ← 세션6이 이미 로마자화하고 실기 검증 완료.
  세션7이 「좌패널 커맨더명은 다른 표시경로, 소스 추적 필요」로 남긴 게 이 +0x00 필드다.

⇒ **새로 번역할 것이 없다.** 레코드마다 +0x3A의 확정 로마자를 +0x00에 16×16으로 옮기면
  「〈이름〉 휘하」 HUD(세션6이 패치한 소형 필드)와 표기가 자동으로 일치한다.

★예산 0 · 폰트 불변: 라틴·숫자·`ー`는 ASC16CG 기존 글리프(0~824)라 한 바이트도 안 건드린다.
  ⇒ 세션8-a 1단계(ASC16CG 885글리프 확장)와 독립적으로 스택된다.

★length-locked: 16×16 필드는 8글리프 고정. 세션6 로마자가 전부 ≤8이라 그대로 들어간다.
  짧으면 `0x0000`으로 패딩(그 필드가 통째로 이름이라 뒤에 종료자가 따로 없다).

⚠️소스가 **F: 패치본**이다(세션6 결과를 읽는다). 소형 필드가 아직 가나면 즉시 중단한다 —
  세션6 패치가 안 올라간 ISO에 이 패치를 얹으면 일본어를 일본어로 덮는 꼴이 된다.

빌드: python tools/build_general16.py            드라이런
      python tools/build_general16.py --write    F: ISO 제자리 기록
      python tools/build_general16.py --revert   원상복구
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import smallfont as sf
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

STRIDE   = 0x62      # 로스터 레코드
OFF16    = 0x00      # 16×16 이름 (8글리프)
OFFSMALL = 0x3A      # 소형폰트 이름
W        = 8         # 글리프 수

# 16×16 폰트는 전각 기호만 있다 (세션8 build_unit16 과 동일 규칙)
ALT = {'-': 'ー', '/': '／', '.': '．', '·': '・', ')': '）', '(': '（'}

# 기본 원칙 = 소형 필드의 확정 로마자를 그대로 옮긴다(HUD와 표기 일치).
# ⚠️예외 = **16×16 필드가 소형 필드보다 정보가 많아** 그대로 옮기면 뭉개지는 것들.
#   `敵陸軍`·`敵空軍`·`敵第1陸軍`·`敵第2陸軍`·`敵援軍1` 은 소형이 전부 `テキ`(→Enemy)라
#   그대로 두면 적 부대 5종이 화면에 똑같이 뜬다. 워게임에서 혼란스러워 구분을 살린다.
OVERRIDE = {
    '敵陸軍':      'EnemyArm',
    '敵空軍':      'EnemyAF',
    '敵第1陸軍':   'Enemyー1A',
    '敵第2陸軍':   'Enemyー2A',
    '敵援軍1':     'EnemyRf1',
    'イギリス艦隊':     'UKーFleet',
    'イギリス輸送艦隊': 'UKーTrpFl',
}


def load_map():
    m = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in m.items()}
    # 🐞세션19: SAKUCG 맵은 **222 가 비어 있다**(원본 글리프가 ASC16CG 와 다른 유일한 칸).
    #   그 탓에 `name()` 이 `v in cm` 에서 걸려 **/M53/UPK 표 앞 5칸이 통째로 탈락**했다
    #   (`西ヒョウリュウ者`·`東ヒョウリュウ者` 가 222=`ョ` 를 쓴다).
    #   실기 증상: 파인애플·갈란트·로드리게스·동서표류자 5종이 미번역으로 남아 깨져 보였다.
    #   ⇒ 원문 디코드는 ASC16CG 맵으로 메운다(0~819 는 222 말고 전부 바이트 동일).
    import charmap as _cmp
    for _i, _ch in _cmp.CHARS.items():
        cm.setdefault(int(_i), _ch)
    rev = {}
    for k, v in cm.items():
        rev.setdefault(v, k)
    return cm, rev


# ── 세션15-e: 부대명·장군명 = **한글**(generals_kr, 사용자 결정 「174종 전부」) ──
#   ⚠️소형 8×8 사본(+0x3A)은 칸이 없어 로마자 유지 → HUD `〈이름〉 휘하`와 표기가 어긋난다.
_KRN = None
_SLOTC = None
if '--en' not in sys.argv:
    try:
        # ★16×16 필드는 **완전한 일본어 원문**(`フランス第2軍`)이라 그걸 직접 번역한다.
        #   소형 축약 로마자(`Frー2A`)를 옮기던 세션8-a 방식보다 정보가 많다.
        import force16_kr as _F16
        _KRN = _F16
    except ImportError:
        print('⚠️ force16_kr 없음 — 로마자 유지')


def kr_slots():
    global _SLOTC
    if _SLOTC is None:
        import build_ui16
        _SLOTC = build_ui16.build_slots()
    return _SLOTC


def enc16(s, rev):
    out = bytearray()
    for ch in s:
        if '가' <= ch <= '힣':
            gi = kr_slots().get(ch)
            if gi is None:
                raise SystemExit('한글 슬롯 없음 %r in %r' % (ch, s))
            out += struct.pack('>H', gi)
            continue
        c = ch if ch in rev else ALT.get(ch)
        if c is None or c not in rev:
            raise SystemExit('16×16 인코딩불가 %r in %r' % (ch, s))
        gi = rev[c]
        if gi > 824:
            raise SystemExit('글리프 %d(%r) 는 ASC16CG(825) 밖' % (gi, c))
        out += struct.pack('>H', gi)
    return bytes(out).ljust(W * 2, b'\x00')


def dec16(raw, cm):
    s = ''
    for i in range(W):
        v = (raw[2 * i] << 8) | raw[2 * i + 1]
        if v == 0:
            continue
        s += cm.get(v, '?')
    return s


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def find_table(d, cm, rev):
    """빈 슬롯 라벨 `NOT` 앵커 + stride 체인 검증으로 테이블 시작을 확정한다.
    ⚠️첫 `NOT` 히트를 그냥 쓰면 레코드 시작이 아닌 곳에 걸린다(실제로 겪음)."""
    def name(o):
        if o < 0 or o + 2 * W > len(d):
            return None
        s, seen_null = '', False
        for i in range(W):
            v = (d[o + 2 * i] << 8) | d[o + 2 * i + 1]
            if v == 0:
                seen_null = True
                continue
            if seen_null or not (1 <= v <= 824 and v in cm):
                return None
            s += cm[v]
        return s or None

    anchor = enc16('NOT', rev)[:6]
    i = -1
    while True:
        i = d.find(anchor, i + 1)
        if i < 0:
            return None
        if i % 2 or name(i) != 'NOT':
            continue
        if not all(name(i + k * STRIDE) for k in (1, 2, 3)):
            continue
        lo = i
        while name(lo - STRIDE):
            lo -= STRIDE
        n = 1
        while name(lo + n * STRIDE):
            n += 1
        return lo, n


def build_plans():
    cm, rev = load_map()
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    plans, mods, kana = [], {}, 0
    # ★원문(16×16 원본 바이트·테이블 위치)은 **원본 ISO**에서, 확정 로마자는 **F: 패치본**에서
    #   읽는다. 섞으면 계획이 패치 상태에 따라 달라져 `--revert`가 깨진다 — 실제로 겪었다
    #   (예외표가 원문 키인데 원문이 이미 로마자로 바뀌어 안 걸렸다).
    with open(TRACK1, 'rb') as fo, open(dst, 'rb') as f:
        for p, lba, size in [t for t in files(skip_media=False) if '/UPK' in t[0]]:
            d  = read_file(fo, lba, size)         # 원본 = 원문·테이블 위치
            dp = read_file(f, lba, size)          # 패치본 = 로마자 소스
            t = find_table(d, cm, rev)
            if t is None:
                print('  ⚠️%-14s 로스터 테이블 못 찾음' % p)
                continue
            lo, n = t
            mods[p] = (lba, size)
            for r in range(n):
                o = lo + r * STRIDE
                raw = d[o + OFF16:o + OFF16 + W * 2]
                jp = dec16(raw, cm)
                latin = sf.decode(dp, o + OFFSMALL, W + 1, stop=True).strip()
                if not latin or jp == 'NOT':
                    continue
                if any('\u3040' <= c <= '\u30ff' and c != 'ー' for c in latin):
                    kana += 1                      # 세션6 패치가 안 올라간 ISO
                    continue
                if not any('\u3040' <= c <= '\u9fff' for c in jp):
                    continue                       # 이미 라틴 = 손댈 것 없음
                if _KRN is not None:
                    _k = _KRN.to_kr(jp)
                    if _k is None:
                        raise SystemExit('부대명 번역 규칙 미비: %r' % jp)
                    latin = _k
                else:
                    latin = OVERRIDE.get(jp, latin)
                nb = enc16(latin, rev)
                if nb != raw:
                    plans.append((p, o + OFF16, raw, nb, jp, latin))
    if kana:
        raise SystemExit('소형 이름이 아직 가나인 레코드 %d개 — 세션6 패치가 없는 ISO다. 중단.' % kana)
    return plans, mods, cm, rev


def main():
    revert = '--revert' in sys.argv
    # ★--resync: 슬롯·번역 구성이 바뀐 재빌드(세션15-e). 오프셋은 계획 단계에서 확정된다.
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    plans, mods, cm, rev = build_plans()
    names = {}
    for p, o, raw, nb, jp, latin in plans:
        names.setdefault(jp, latin)
    print('UPK %d파일 / 교체 레코드 %d개 / 고유 이름 %d종' % (len(mods), len(plans), len(names)))
    for jp, latin in list(names.items())[:20]:
        print('   %-10s -> %s' % (jp, latin))
    if len(names) > 20:
        print('   ... 외 %d종' % (len(names) - 20))

    over = [(jp, la) for jp, la in names.items() if len(la) > W]
    if over:
        raise SystemExit('폭 초과 %s' % over)
    print('폭 검사 통과 (전부 ≤%d글리프), 신규 글리프 0 — 폰트 불변.' % W)

    if not write:
        print('\n드라이런 — ISO 미기록 (--write / --revert).')
        return

    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    print('\nF: ISO 제자리 %s' % ('원상복구' if revert else '패치'))
    touched = set()
    with open(dst, 'r+b') as w:
        for p, o, raw, nb, jp, latin in plans:
            lba, _ = mods[p]
            src, dstb = (nb, raw) if revert else (raw, nb)
            for k in range(len(raw)):
                lo = o + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if w.read(1) != src[k:k + 1] and '--resync' not in sys.argv:
                    raise SystemExit('%s @0x%x 대조 실패 — %s'
                                     % (p, o, '패치본이 아님' if revert else '이미 패치됨?'))
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
        verify(dst, plans, mods, cm)


def verify(dst, plans, mods, cm):
    """독립 되읽기 — 기록된 ISO를 다시 읽어 16×16 디코드가 로마자인지 확인."""
    bad = 0
    with open(dst, 'rb') as r:
        secs = set()
        for p, o, raw, nb, jp, latin in plans:
            lba, _ = mods[p]
            got = bytearray()
            for k in range(len(nb)):
                lo = o + k
                sec = lba + lo // USER
                secs.add(sec)
                r.seek(sec * RAW + HDR + lo % USER)
                got += r.read(1)
            if bytes(got) != nb:
                bad += 1
                print('  ❌%s @0x%06x 되읽기 불일치' % (p, o))
                continue
            # ★세션15-e: 한글 글리프는 공용 charmap 이 모르는 **우리 배정 슬롯**이라
            #   역맵(슬롯→음절)을 먼저 본다. 안 그러면 멀쩡한 한글이 가나로 읽혀 거짓 실패가 난다.
            _cm2 = dict(cm)
            if _KRN is not None:
                for _c, _g in kr_slots().items():
                    _cm2[_g] = _c
            dec = dec16(bytes(got), _cm2)
            # ⚠️`ー`(U+30FC)·`・`(U+30FB)는 가타카나 블록에 있지만 **문장부호**다.
            #   ALT가 '-'·'·'를 이 전각 기호로 인코딩하므로 가나 검사에서 빼야 한다
            #   (안 빼면 `N・A・Ft`(←北大西洋艦隊) 같은 정상 결과가 거짓 실패로 잡힌다).
            if any('\u3040' <= c <= '\u9fff' and c not in 'ー・' for c in dec):
                bad += 1
                print('  ❌%s @0x%06x 가나/한자 잔존 %r' % (p, o, dec))
        for sec in sorted(secs):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 되읽기 일치, 가나 잔존 0, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
