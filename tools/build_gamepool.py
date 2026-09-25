# -*- coding: utf-8 -*-
"""GAME/GMSELDT 소형폰트 풀 패처 (세션8).

세션5~7이 놓친 소형폰트 텍스트 4곳을 메운다. 실기 증상:
  · 지도 거점 리스트 2행 「로폭야폭」  = クウコウ(空港) 미번역
  · 세이브 화면 「공설지 음종탄산」    = シンキ ファイル(新規ファイル) 미번역
원인 = **GAME 모듈이 소형폰트 텍스트 검사에서 통째로 누락**. 세션5는 폰트 5벌이 있는
모듈(GMDT/MUSEUM/SAKUSEN/KEKKA/INTERM)만 훑었고, GAME은 「크기상수만 있는 모듈」로 분류했다.

★★이 패치는 **폰트를 한 바이트도 안 건드린다**(신규 한글 음절 0). 기존 배정 음절 + 라틴만
  쓴다 → 세션5(소형폰트)·6(장군명)·7(버튼 코드주입) 검증 스택을 흔들지 않는다.

패치 대상 (전부 length-locked 제자리):
  GAME  시간대풀   0x944D6 stride 4  × 6   [텍스트 3B][ff]
  GAME  미션명풀   0x944EE stride 15 × 85  [ff][0d 00][텍스트 12B]
                     0~64 미션명 / 65~79 "Map No. Mxx"(손 안 댐) / 80~84 학교
  GAME  거점종류   0x9600C stride 6  × 16  (일부 레코드는 선두에 0x0c 아이콘 바이트)
  GMSELDT 시간대풀 0x001A1 stride 4  × 6
  GMSELDT 세이브   「シンキ ファイル」 1곳
  ⚠️GMSELDT 0x1C8~ 「パイナップル」×19 = 개발 더미(실기 화면엔 실제 세이브가 덮어씀).
    length-locked 6바이트라 마땅한 라틴 대체어가 없어 **손대지 않는다**(잔여 리스크로 기록).

오프셋은 하드코딩하지 않고 **파싱 + 원문 바이트 대조**로 확정한다(정렬 오판 방지).

빌드: python tools/build_gamepool.py           드라이런(검증만)
      python tools/build_gamepool.py --write   F: ISO 제자리 기록(세션5~7 패치본 위에 스택)
"""
import os, sys, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
import build_smalltext as B
import game_pool_kr as G
from isoread import TRACK1, RAW, HDR, USER, read_range
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT = os.path.join(ROOT, 'work', 'extract')
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

TIME_STRIDE, TIME_W = 4, 3
MISS_STRIDE, MISS_W, MISS_TXT = 15, 12, 2      # [ff][0d 00][12B]
KYO_STRIDE, KYO_W, KYO_N = 6, 6, 16


def load(name):
    with open(os.path.join(EXTRACT, name), 'rb') as f:
        return f.read()


def make_enc():
    """세션5 슬롯 배정 그대로. 신규 음절이 나오면 즉시 실패(폰트 불변 보장)."""
    _, rows = B.load_tsv()
    slot, _ = B.assign_slots(rows)
    enc = B.make_encoder(slot)
    rev = {v: k for k, v in slot.items()}
    return enc, slot, rev


def find_time_pool(d, start, end):
    """[텍스트 3B][ff] × 6 = アサ/ヒル/ユウ/ヨル/(シンヤ|ヨナカ)/ターン 를 찾는다."""
    want = sf.encode('ターン')
    for a in range(start, end):
        if d[a:a + 3] != want or d[a + 3] != 0xff:
            continue
        base = a - 5 * TIME_STRIDE                     # ターン은 6번째(마지막)
        if base < 0:
            continue
        recs = []
        for i in range(6):
            o = base + i * TIME_STRIDE
            if d[o + 3] != 0xff:
                recs = []
                break
            recs.append((o, d[o:o + 3]))
        if recs:
            return base, recs
    raise SystemExit('시간대 풀을 못 찾음')


def plan_time(d, base_off, recs, enc):
    """시간대 6개. 원문 표기는 'ヒ ル'처럼 널이 낀 3칸 고정폭이라 공백까지 살려 대조."""
    out = []
    for o, raw in recs:
        jp = sf.decode(raw, 0, TIME_W, stop=False)     # 0x00 -> ' '
        kr = G.TIME.get(jp)
        if kr is None:
            kr = G.TIME.get(jp.replace(' ', ''))
        if kr is None:
            raise SystemExit('시간대 미정의: %r @0x%x' % (jp, o))
        nb = enc(kr)
        if len(nb) > TIME_W:
            raise SystemExit('시간대 폭 초과 %r %d>%d' % (kr, len(nb), TIME_W))
        out.append((o, TIME_W, bytes(raw), nb.ljust(TIME_W, b'\x00'), jp, kr, kr))
    return out


def find_mission_pool(d):
    """[ff][0d 00][12B] × 85. 첫 레코드 = シカンガッコウ 로 앵커."""
    anchor = sf.encode('シカンガッコウ')
    i = d.find(anchor)
    while i >= 0:
        base = i - 3                                    # [ff][0d][00]
        if base >= 0 and d[base] == 0xff and d[base + 1] == 0x0d and d[base + 2] == 0x00:
            ok = all(d[base + n * MISS_STRIDE] == 0xff for n in range(85))
            if ok:
                return base
        i = d.find(anchor, i + 1)
    raise SystemExit('미션명 풀을 못 찾음')


def plan_missions(d, base, enc):
    out = []
    table = [(jp, kr) for jp, kr in G.MISSIONS] + [None] * 15 + [(jp, kr) for jp, kr in G.SCHOOL]
    if len(table) != 85:
        raise SystemExit('번역표 %d개 (85 아님)' % len(table))
    for n, ent in enumerate(table):
        o = base + n * MISS_STRIDE + 1 + MISS_TXT
        raw = d[o:o + MISS_W]
        jp = sf.decode(raw, 0, MISS_W, stop=False).rstrip()
        if ent is None:                                  # "Map No. Mxx" — 손 안 댐
            if not jp.startswith('Map No.'):
                raise SystemExit('레코드 %d 가 Map No. 아님: %r' % (n, jp))
            continue
        want, kr = ent
        if jp != want:
            raise SystemExit('레코드 %d 원문 불일치: 표=%r 실제=%r @0x%x' % (n, want, jp, o))
        nb = enc(kr)
        if len(nb) > MISS_W:
            raise SystemExit('레코드 %d 폭 초과 %r %d>%d' % (n, kr, len(nb), MISS_W))
        out.append((o, MISS_W, bytes(raw), nb.ljust(MISS_W, b'\x00'), jp, kr, kr))
    return out


def find_kyoten(d):
    """거점 종류표: stride 6 × 16. ナシ,トシ,コウジョウ… 순서로 앵커."""
    a = d.find(sf.encode('ナシ') + b'\x00\x00\x00\x00' + sf.encode('トシ'))
    if a < 0:
        raise SystemExit('거점 종류표를 못 찾음')
    return a


def plan_kyoten(d, base, enc):
    out = []
    for n in range(KYO_N):
        o = base + n * KYO_STRIDE
        raw = d[o:o + KYO_W]
        pre = b''
        body = raw
        if raw[0] == 0x0c:                               # 아이콘 바이트 보존
            pre, body = raw[:1], raw[1:]
        jp = sf.decode(body, 0, len(body), stop=True)
        kr = G.KYOTEN.get(jp)
        if kr is None:
            raise SystemExit('거점종류 미정의: %r @0x%x' % (jp, o))
        nb = pre + enc(kr)
        if len(nb) > KYO_W:
            raise SystemExit('거점종류 폭 초과 %r %d>%d' % (kr, len(nb), KYO_W))
        # 아이콘 바이트를 보존하므로 되읽기 기대값에도 그 글리프를 포함시킨다
        expect = ''.join(sf.CHARS.get(x, '<%02x>' % x) for x in pre) + kr
        out.append((o, KYO_W, bytes(raw), nb.ljust(KYO_W, b'\x00'), jp, kr, expect))
    return out


def plan_savelabel(d, enc):
    """「シンキ ファイル」= 빈 슬롯 라벨. 널을 공백으로 둔 3+4 표기.

    ⚠️폭을 상수로 주지 말 것 — 이 필드는 델리미터 풀 안에 있고 뒤의 `0xff`가 종료자다.
    세션8이 폭을 미션풀 값(12)으로 넘겨 GAME 0x949f7의 `ff`를 널로 덮었고, 렌더러가
    종료자를 못 만나 뒤의 레이아웃 좌표표를 문자로 찍었다(세이브 화면 TURN/DATE/TIME 깨짐).
    → 종료자 직전까지로 폭을 파싱해 정하고, 종료자는 절대 계획에 넣지 않는다."""
    pat = sf.encode('シンキ') + b'\x00' + sf.encode('ファイル')
    out = []
    i = d.find(pat)
    while i >= 0:
        end = d.find(b'\xff', i + len(pat))
        if end < 0 or end - i > 16:
            raise SystemExit('세이브 라벨 필드 종료자(ff)를 못 찾음 @0x%x' % i)
        width = end - i
        raw = d[i:i + width]
        kr = G.SAVE['シンキ ファイル']
        nb = enc(kr)
        if len(nb) > width:
            raise SystemExit('세이브 라벨 폭 초과 %d>%d' % (len(nb), width))
        out.append((i, width, bytes(raw), nb.ljust(width, b'\x00'), 'シンキ ファイル', kr, kr))
        i = d.find(pat, i + 1)
    if not out:
        raise SystemExit('シンキ ファイル 를 못 찾음')
    return out


def build_plans():
    enc, slot, rev = make_enc()
    plans = {}

    g = load('GAME')
    tb, trecs = find_time_pool(g, 0x94400, 0x94600)
    mb = find_mission_pool(g)
    kb = find_kyoten(g)
    print('GAME    시간대 0x%06x / 미션풀 0x%06x / 거점종류 0x%06x' % (tb, mb, kb))
    p = plan_time(g, tb, trecs, enc) + plan_missions(g, mb, enc) + plan_kyoten(g, kb, enc)
    p += plan_savelabel(g, enc)
    plans['GAME'] = p

    s = load('GMSELDT')
    tb2, trecs2 = find_time_pool(s, 0x100, 0x400)
    print('GMSELDT 시간대 0x%06x' % tb2)
    p2 = plan_time(s, tb2, trecs2, enc) + plan_savelabel(s, enc)
    plans['GMSELDT'] = p2

    # 겹침 검사 — 같은 바이트를 두 계획이 건드리면 즉시 실패
    for mod, pl in plans.items():
        seen = {}
        for o, w, raw, nb, jp, kr, ex in pl:
            for k in range(w):
                if o + k in seen:
                    raise SystemExit('%s 계획 겹침 @0x%x' % (mod, o + k))
                seen[o + k] = 1
    return plans, enc, rev


def verify(plans, enc, rev):
    """되읽기: 새 바이트를 패치된 코드표로 디코드해 의도한 문자열이 나오는지."""
    def dec(b):
        return ''.join(rev.get(x, sf.CHARS.get(x, '<%02x>' % x)) for x in b).rstrip()
    bad = 0
    for mod, pl in plans.items():
        for o, w, raw, nb, jp, kr, ex in pl:
            got = dec(nb)
            want = ex.replace('-', 'ー').rstrip()
            if got != want:
                bad += 1
                print('  ❌%s @0x%06x %r -> %r (기대 %r)' % (mod, o, jp, got, want))
            if len(nb) != w:
                bad += 1
                print('  ❌%s @0x%06x 길이 %d != %d' % (mod, o, len(nb), w))
    # 델리미터 보존 검사: 원본에 있던 0xff(필드 종료자)를 계획이 덮으면 렌더러가
    # 문자열 끝을 못 찾아 뒤의 데이터를 글자로 찍는다(세션8 세이브 화면 사고).
    for mod, pl in plans.items():
        for o, w, raw, nb, jp, kr, ex in pl:
            for k in range(w):
                if raw[k] == 0xff and nb[k] != 0xff:
                    bad += 1
                    print('  ❌%s @0x%06x +%d 델리미터 ff 파괴' % (mod, o, k))

    # 가나 잔존 검사: 새 바이트에 우리가 재정의한 가나 슬롯(63~143)이 남으면 깨져 보인다
    for mod, pl in plans.items():
        for o, w, raw, nb, jp, kr, ex in pl:
            for v in nb:
                if 63 <= v <= 143 and v not in rev:
                    bad += 1
                    print('  ❌%s @0x%06x 미배정 가나슬롯 %d 잔존' % (mod, o, v))
    if bad:
        raise SystemExit('검증 실패 %d건' % bad)


def write_iso(plans, revert=False):
    """revert=True 면 원본 바이트로 되쓴다(원상복구). 방향만 다르고 경로는 동일."""
    import ecc
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    f = open(dst, 'rb')
    loc = {}
    for mod in plans:
        hits, _, _, _ = find_dirrec(f, mod)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 레코드 %d개' % (mod, len(hits)))
        _, lba, size, _ = hits[0]
        loc[mod] = (lba, size)
        print('  %-8s lba=%d size=%d' % (mod, lba, size))
    f.close()

    print('\nF: ISO 제자리 %s: %s' % ('원상복구' if revert else '패치', dst))
    touched = set()
    with open(dst, 'r+b') as w:
        for mod, pl in plans.items():
            lba, size = loc[mod]
            for o, width, raw, nb, jp, kr, ex in pl:
                src, dstb = (nb, raw) if revert else (raw, nb)
                for k in range(width):
                    lo = o + k
                    sec = lba + lo // USER
                    pos = sec * RAW + HDR + (lo % USER)
                    w.seek(pos)
                    cur = w.read(1)
                    if cur != src[k:k + 1]:
                        raise SystemExit('%s @0x%x 대조 실패(F:) — %s'
                                         % (mod, o, '패치본이 아님' if revert else '이미 패치됨?'))
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
        verify_iso(dst, plans, loc)


def resync():
    """슬롯맵이 바뀌어 **옛 한글 인코딩**이 남은 필드만 새 코드로 다시 쓴다 (세션12).

    세션11에서 소형폰트를 89→81음절로 줄이며 빈도순 슬롯 배정이 밀렸는데, 세션8이 넣은
    GAME/GMSELDT 한글은 옛 배정 그대로라 화면에서 「도시→공시」처럼 깨졌다.
    ⚠️이 상태는 --revert(패치본 기대)도 --write(원본 기대)도 대조에 걸린다. 그래서
      「현재 값이 무엇이든 우리 필드 안이면 새 값으로 덮는」 전용 경로가 필요하다.

    안전장치 — 덮기 전에 현재 바이트가 **우리가 쓴 텍스트**임을 확인한다:
      ①구분자(0xfd/0xfe/0xff)가 하나도 없을 것 — 있으면 필드 경계를 잘못 잡은 것이다
        (세션8-a에서 종료자를 널로 덮어 세이브 화면을 깨뜨린 그 실수 방지)
      ②모든 바이트가 폰트 범위(<229) 안일 것
    기록 후에는 「원본 대비 차이가 전부 계획 안에 있는가」를 전수로 확인한다.
    """
    import ecc
    plans, enc, rev = build_plans()
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    f = open(dst, 'rb')
    loc = {}
    for mod in plans:
        hits, _, _, _ = find_dirrec(f, mod)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 레코드 %d개' % (mod, len(hits)))
        _, lba, size, _ = hits[0]
        loc[mod] = (lba, size)
    f.close()

    def cur_bytes(w, lba, o, width):
        out = bytearray()
        for k in range(width):
            lo = o + k
            w.seek((lba + lo // USER) * RAW + HDR + (lo % USER))
            out += w.read(1)
        return bytes(out)

    touched, changed = set(), 0
    with open(dst, 'r+b') as w:
        for mod, pl in plans.items():
            lba, _ = loc[mod]
            for o, width, raw, nb, jp, kr, ex in pl:
                cur = cur_bytes(w, lba, o, width)
                if cur == nb:
                    continue
                if cur != raw:                     # 원본 일본어가 아니면 우리 텍스트여야 한다
                    if any(b in (0xFD, 0xFE, 0xFF) for b in cur):
                        raise SystemExit('%s @0x%x 현재 값에 구분자가 있다 %s' % (mod, o, cur.hex()))
                    if any(b >= 229 for b in cur):
                        raise SystemExit('%s @0x%x 폰트 밖 코드 %s' % (mod, o, cur.hex()))
                changed += 1
                for k in range(width):
                    lo = o + k
                    sec = lba + lo // USER
                    w.seek(sec * RAW + HDR + (lo % USER))
                    w.write(nb[k:k + 1])
                    touched.add(sec)
        print('다시 쓴 필드 %d개, 섹터 %d개 — EDC/ECC 재계산...' % (changed, len(touched)))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw_sec = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw_sec))

    verify_iso(dst, plans, loc)
    # 계획 밖으로 새어나간 변경이 없는지 원본과 전수 대조
    from isoread import read_range
    with open(TRACK1, 'rb') as a, open(dst, 'rb') as b:
        for mod, pl in plans.items():
            lba, size = loc[mod]
            o0 = read_range(a, lba, size)
            n0 = read_range(b, lba, size)
            planned = {o + k for o, wdt, raw, nb, jp, kr, ex in pl for k in range(wdt)}
            stray = [i for i in range(size) if o0[i] != n0[i] and i not in planned]
            print('  %-8s 원본대비 차이 %d B, 그중 계획 밖 %d B'
                  % (mod, sum(1 for i in range(size) if o0[i] != n0[i]), len(stray)))
            if stray:
                print('    ⚠️계획 밖 오프셋 예:', [hex(x) for x in stray[:8]])


def verify_iso(dst, plans, loc):
    """독립 되읽기: 빌더 내부 상태가 아니라 기록된 ISO를 다시 읽어 확인한다.
    ①새 바이트가 실제로 들어갔나 ②그 필드에 재정의 가나 슬롯(63~143)이 남았나
    ③EDC/ECC가 유효한가."""
    import ecc
    _, _, rev = make_enc()
    bad = kana = 0
    with open(dst, 'rb') as r:
        secs = set()
        for mod, pl in plans.items():
            lba, _ = loc[mod]
            for o, width, raw, nb, jp, kr, ex in pl:
                got = bytearray()
                for k in range(width):
                    lo = o + k
                    sec = lba + lo // USER
                    secs.add(sec)
                    r.seek(sec * RAW + HDR + (lo % USER))
                    got += r.read(1)
                if bytes(got) != bytes(nb):
                    bad += 1
                    print('  ❌%s @0x%06x 되읽기 불일치' % (mod, o))
                for v in got:
                    if 63 <= v <= 143 and v not in rev:
                        kana += 1
        for sec in sorted(secs):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC 불일치' % sec)
    if bad or kana:
        raise SystemExit('독립검증 실패 (불일치 %d, 가나잔존 %d)' % (bad, kana))
    print('독립검증 통과 — 되읽기 일치, 가나 잔존 0, EDC/ECC 유효.')


def main():
    if '--resync' in sys.argv:
        resync()
        return
    plans, enc, rev = build_plans()
    n = sum(len(p) for p in plans.values())
    print('\n패치 필드 %d개 (GAME %d / GMSELDT %d)'
          % (n, len(plans['GAME']), len(plans['GMSELDT'])))
    verify(plans, enc, rev)
    print('검증 통과 — 폰트 불변, 신규 음절 0.')
    for mod, pl in plans.items():
        print('\n--- %s' % mod)
        for o, w, raw, nb, jp, kr, ex in pl[:6]:
            print('  0x%06x %-22s -> %s' % (o, jp, kr))
        if len(pl) > 6:
            print('  ... 외 %d개' % (len(pl) - 6))
    if '--revert' in sys.argv:
        write_iso(plans, revert=True)
        return
    if '--write' not in sys.argv:
        print('\n드라이런 — ISO 미기록 (--write 로 F: 기록 / --revert 로 원상복구).')
        return
    write_iso(plans)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
