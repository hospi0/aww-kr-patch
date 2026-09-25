# -*- coding: utf-8 -*-
"""훈장·레벨업·결과화면 **사본** 한글화 (세션17).

세션16이 `/KEKKA` 사본만 번역해서 **화면이 실제로 읽는 `/GMDT` 쪽이 통째로 일본어**로 남아
있었다. 회수한 글리프를 그 일본어가 참조해 깨진 한글로 떴다
(사용자 스샷 `훈장수여.png`·`레벨업1~4.png`·`결과화면글자깨짐.png`·`저장.png`).

★치환은 **원문 바이트 앵커**로 한다 — 레코드 경계로 자르면 앞에 그래픽이 붙은 자리에서
  경계를 오판한다(0x015C40 에서 실제로 발생).
★length-locked: 번역 ≤ 원문 칸수, 남는 칸은 널로 패딩(원문 셀 수 유지).
⚠️새 음절이 생기면 ASC16CG 폰트에 없으므로 **build_ui16 을 먼저** 돌려야 한다
  (ui16_kr.budget_all 에 gmdt_medal_kr.NEW 를 넣어 뒀다).

빌드: python tools/build_gmdt_medal.py            드라이런
      python tools/build_gmdt_medal.py --write     F: ISO 기록
      python tools/build_gmdt_medal.py --resync    구성 바뀐 재기록
      python tools/build_gmdt_medal.py --revert    원상복구
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import charmap
import gmdt_medal_kr as G
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESYNC = '--resync' in sys.argv
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

# (파일, 시작, 끝) — 화면이 읽는 **사본** 위치
#   ①/GMDT 훈장·레벨업·보상 풀
#   ②/GMDT 저장 확인창(`は い`)
#   ③/KEKKA 결과화면 설명문 — 코드 사이에 박힌 **단독 문자열**이라 풀 스캔에 안 걸렸다
TARGETS = [('/GMDT',  0x015C40, 0x016A00),
           ('/GMDT',  0x025B50, 0x025B70),
           ('/KEKKA', 0x019D20, 0x019D80),
           # ④/KEKKA 훈장 풀 **바로 앞 4칸** — 세션16이 풀 시작을 0x20F8E(海軍将軍)로 잡아
           #   `陸軍将軍` 이 범위 밖으로 빠졌다(실기 「잘함텍함」).
           ('/KEKKA', 0x020F80, 0x020F90),
           # ⑤/GMDT 설정화면 아래쪽 옵션·디버그 항목(項目制限…累積度, 값 無有通常雨雪)
           ('/GMDT',  0x025D28, 0x025DA0),
           # ⑥/GAME 전투맵 메시지(원군 도착·자동귀환) — build_ui16 은 브리핑 HUD 만 다룬다
           ('/GAME',  0x0976A0, 0x097800)]


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def slots():
    d = {}
    for fn in ('asc16_slots.json', 'shared_unit_slots.json'):
        p = os.path.join(ROOT, 'work', fn)
        if os.path.exists(p):
            for c, g in json.load(open(p, encoding='utf-8')).items():
                d.setdefault(c, int(g))
    return d


def enc(s, slot, rev):
    out = bytearray()
    for c in s:
        if '가' <= c <= '힣':
            g = slot.get(c)
            if g is None:
                raise KeyError('한글 슬롯 없음 %r (build_ui16 먼저)' % c)
        else:
            g = rev.get(c)
            if g is None:
                raise KeyError('인코딩 불가 %r in %r' % (c, s))
        out += struct.pack('>H', g)
    return bytes(out)


def build_plans():
    """{파일: (lba, size, orig, [(off, old, new, jp, kr), ...])}"""
    m = {q: (l, s) for q, l, s in files(skip_media=False)}
    rev = {}
    for k, v in charmap.CHARS.items():
        rev.setdefault(v, k)
    slot = slots()
    tbl = G.table()
    # ★F: 패치본을 같이 읽어 **아직 미번역인 자리만** 치환한다.
    #   다른 빌더(build_ui16 등)가 이미 처리한 구간과 범위가 겹치기 때문이다.
    #   (겹친 자리를 또 건드리면 1칸 필드에 2칸 역어를 넣으려다 막힌다 — `朝`→`아침`)
    dstiso = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    mods, taken = {}, {}
    for mod, lo, hi in TARGETS:
        if mod not in mods:
            lba, size = m[mod]
            with open(TRACK1, 'rb') as f:
                orig0 = read_file(f, lba, size)
            cur0 = orig0
            if os.path.exists(dstiso):
                with open(dstiso, 'rb') as f:
                    cur0 = read_file(f, lba, size)
            mods[mod] = [lba, size, orig0, [], cur0]
            taken[mod] = set()
        lba, size, orig, plans, cur = mods[mod]
        # 긴 원문부터 — 짧은 문구가 긴 문구 안에서 먼저 잡히는 것을 막는다
        for jp in sorted(tbl, key=len, reverse=True):
            kr = tbl[jp]
            if not any('\u3040' <= c <= '\u9fff' for c in jp):
                continue
            try:
                pat = enc(jp, slot, rev)
                nb = enc(kr, slot, rev)
            except KeyError as e:
                if jp in G.NEW:
                    raise SystemExit('★%s' % e)
                continue
            if len(nb) > len(pat):
                # 다른 화면용 역어라 이 풀 칸수에 안 맞는다(예: 2칸짜리 `朝`→`아침`이
                # 여기서는 1칸 필드). 그 자리는 다른 빌더가 이미 처리하므로 건너뛴다.
                continue
            nb = nb.ljust(len(pat), b'\x00')
            i = orig.find(pat, lo)
            while 0 <= i < hi:
                # ★--resync 는 이 자리에 **무엇이 들어 있든** 새 값으로 덮는다 (세션18).
                #   `already`(=이미 누가 건드렸다)로 건너뛰면, 슬롯 재배정 전에 옛 등록부로
                #   기록된 자리가 **영원히 안 고쳐진다** — 실기에서 `승候등車`·`자駆귀환` 이
                #   그렇게 남았다. 위치는 원본 TRACK1 대조로 확정되고 칸수 초과는 아래
                #   `len(nb) > len(pat)` 가 막으므로 덮어도 안전하다.
                already = (not RESYNC) and cur[i:i + len(pat)] != orig[i:i + len(pat)]
                if not already and not (set(range(i, i + len(pat))) & taken[mod]):
                    plans.append((i, orig[i:i + len(pat)], nb, jp, kr))
                    taken[mod].update(range(i, i + len(pat)))
                i = orig.find(pat, i + 2)
    for mod in mods:
        mods[mod][3].sort()
    return mods


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    revert = '--revert' in sys.argv
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    mods = build_plans()
    total = sum(len(v[3]) for v in mods.values())
    for mod, (lba, size, orig, plans, _cur) in mods.items():
        print('%s 치환 %d곳' % (mod, len(plans)))
        for o, a, b, jp, kr in plans[:6]:
            print('   0x%06X %-22s → %s' % (o, jp, kr))
        if len(plans) > 6:
            print('   ... 외 %d곳' % (len(plans) - 6))
    if not write:
        print('\n합계 %d곳. 드라이런 — ISO 미기록 (--write / --resync / --revert).' % total)
        return
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)
    nsec = 0
    for mod, (lba, size, orig, plans, _cur) in mods.items():
        with open(dst, 'r+b') as f:
            buf = bytearray(read_file(f, lba, size))
            for o, a, b, jp, kr in plans:
                src, dstb = (b, a) if revert else (a, b)
                if not resync and bytes(buf[o:o + len(a)]) != src:
                    raise SystemExit('★%s 0x%06X 대조 실패 — 중단' % (mod, o))
                buf[o:o + len(a)] = dstb
            secs = sorted({(o + k) // USER for o, a, b, _, _ in plans
                           for k in range(len(a))})
            for s in secs:
                f.seek((lba + s) * RAW)
                raw = bytearray(f.read(RAW))
                raw[HDR:HDR + USER] = buf[s * USER:(s + 1) * USER]
                f.seek((lba + s) * RAW)
                f.write(ecc.fix_sector(raw))
            nsec += len(secs)
    print('쓴 섹터 %d개, EDC/ECC 재계산...' % nsec)
    bad = 0
    with open(dst, 'rb') as f:
        for mod, (lba, size, orig, plans, _cur) in mods.items():
            back = read_file(f, lba, size)
            bad += sum(1 for o, a, b, _, _ in plans
                       if back[o:o + len(a)] != (a if revert else b))
    print('독립검증 %s' % ('통과 — 되읽기 일치' if bad == 0 else '❌실패 %d곳' % bad))


if __name__ == '__main__':
    main()
