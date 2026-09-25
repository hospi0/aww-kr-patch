# -*- coding: utf-8 -*-
"""장군/부대명 로마자화 패처 (세션6).

「〈장군명〉配下」 HUD의 장군명이 소형폰트 가나 → 세션5에서 가나슬롯을 한글로 재정의해
깨져 표시됨. 이름을 라틴으로 바꿔 해소.

장군명 저장 구조 (세션6 확정):
  각 미션 /Mxx/UPKn 파일에 고정 stride 0x62 로스터 테이블. 레코드 =
    +0    이름 (소형폰트, 널종료, 최대 8자 → 고정 9바이트 필드 +0..+8)
    +0x09~ 가변 플래그 + 스탯쌍 + `09` + `ff`런(≥8)   ← 이 09가 검출 시그니처
  빈 슬롯 = 이름 'NOT'(18 19 1e).  유닛 병종명은 별도 stride 0x52 표(로스터 아님).

★검출: `09`+ff×8 시그니처 위치 → 레코드+0은 "앞바이트가 널"(앞 레코드 꼬리)로 정렬확정.
   (마커 6464는 스탯값이라 불안정 → 폐기. ff-run 역산은 정렬모호 → 널경계로 확정.)
패치 = length-locked 제자리: 이름필드 9바이트(+0..+8)만 라틴+널패딩. +9 이후 불침.
       이름필드는 ≤8자+널 전용버퍼(8자명이 +7까지 쓰고 +8=널, 플래그는 +9부터가 증거).
       짧은 이름의 널이후 잔여바이트는 버퍼 내부라 덮어써도 안전(게임은 널까지만 읽음).

⚠️드라이런(기본)은 원본 Track01 논리파일로 메모리 검증만. --write 로 F: ISO 제자리 기록.
  (F: UPK는 원본과 동일 — 세션5가 안 건드림 — 이라 원본기준 오프셋으로 F: 패치 유효.)
"""
import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
from generals_romaji import ROMAJI
from isoread import TRACK1, RAW, HDR, USER, read_range

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_TSV = os.path.join(ROOT, 'work', 'files.tsv')
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

FFSIG = b'\x09' + b'\xff' * 8   # 로스터 레코드 시그니처 (09 + ff런)
FIELD = 9                       # 이름필드 +0..+8 (최대 8자 + 널종료)
MAXDIST = 0x16                  # 레코드+0 에서 09 시그니처까지 최대 거리

SAFE = set('0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
           '.·’=/?!%:ⅠⅡⅢ[]()+-')   # '-'→ー(154) 인코딩 시 매핑


def enc_latin(s):
    """라틴 로마자 → 소형폰트 바이트. '-'→ー(154)."""
    out = bytearray()
    for c in s:
        if c == '-':
            out.append(sf.REV['ー'])
        elif c in sf.REV:
            out.append(sf.REV[c])
        else:
            raise SystemExit('인코딩불가 %r in %r' % (c, s))
    return bytes(out)


def has_kana(name_bytes):
    return any(63 <= b <= 143 for b in name_bytes)   # 가나(탁점 포함) 슬롯 범위


def name_at(buf, o):
    """레코드+0 후보 o 에서 이름 읽기. 앞바이트 널(레코드경계) 요구 → 정렬확정."""
    if o < 1 or buf[o - 1] != 0:
        return None
    n = 0
    while o + n < len(buf) and buf[o + n] != 0 and buf[o + n] < 176 and n < 9:
        n += 1
    if not (1 <= n <= 8) or o + n >= len(buf) or buf[o + n] != 0:
        return None
    return n


def roster_records(buf):
    """반환 [(o, n)] — 모든 로스터 레코드(이름@o, 길이 n). ff-run+널정렬로 검출."""
    out = []
    i = 0
    while True:
        i = buf.find(FFSIG, i)
        if i < 0:
            break
        for o in range(max(1, i - MAXDIST), i):     # 가장 이른 경계 = 가장 긴 이름
            n = name_at(buf, o)
            if n and o + n <= i <= o + MAXDIST:
                out.append((o, n))
                break
        i += 1
    return out


def mission_upk_files():
    rows = [l.rstrip('\n').split('\t') for l in open(FILES_TSV, encoding='utf-8')][1:]
    out = []
    for r in rows:
        if len(r) < 4 or r[3] == '1':
            continue
        if re.match(r'/M\d+/UPK\d*$', r[0]):
            out.append((r[0], int(r[1]), int(r[2])))
    return out


def extract(f, lba, size):
    return bytearray(read_range(f, lba, size))


def plan_file(buf):
    """반환: [(off, old_name_bytes, jp, latin, new_field)] · 미매핑 가나 로스터명."""
    plans = []
    skipped = []
    for o, n in roster_records(buf):
        nb = bytes(buf[o:o + n])
        if not has_kana(nb):
            continue                       # 이미 라틴(Team.PP 등) → 손 안 댐
        jp = sf.decode(buf, o, n)
        if jp not in ROMAJI:
            skipped.append(jp)
            continue
        latin = ROMAJI[jp]
        fb = enc_latin(latin)
        assert len(fb) <= 8, '%r->%r 8초과' % (jp, latin)
        # 구조 어서션: 이름필드 뒤(+9~)에 09 시그니처가 있는지 = 진짜 레코드
        e = buf.find(FFSIG, o + n, o + MAXDIST + len(FFSIG))
        assert e >= o + FIELD, '%r @0x%x 구조이상(09시그니처 위치 %d)' % (jp, o, e - o)
        newfield = fb + b'\x00' * (FIELD - len(fb))
        plans.append((o, nb, jp, latin, newfield))
    return plans, skipped


def build(write=False):
    f = open(TRACK1, 'rb')
    files = mission_upk_files()
    print('미션 UPK 파일 %d개 스캔' % len(files))

    total_recs = 0
    names_hit = {}
    nomap = {}
    file_plans = []       # (path, lba, size, buf, plans)
    for path, lba, size in files:
        buf = extract(f, lba, size)
        plans, skip = plan_file(buf)
        if plans:
            file_plans.append((path, lba, size, buf, plans))
            total_recs += len(plans)
            for o, nb, jp, latin, nf in plans:
                names_hit[jp] = names_hit.get(jp, 0) + 1
        for s in skip:
            nomap[s] = nomap.get(s, 0) + 1

    print('패치 대상 레코드 %d개 (파일 %d개), 고유 이름 %d종' %
          (total_recs, len(file_plans), len(names_hit)))

    # 검증 1: 라운드트립 (라틴 되읽기)
    rt_bad = 0
    for _, _, _, _, plans in file_plans:
        for o, nb, jp, latin, nf in plans:
            got = sf.decode(nf, 0, len(enc_latin(latin)))
            want = latin.replace('-', 'ー')
            if got != want:
                rt_bad += 1
    if rt_bad:
        raise SystemExit('라운드트립 불일치 %d' % rt_bad)

    # 검증 2: 안전 글리프
    for jp, latin in ROMAJI.items():
        bad = [c for c in latin if c not in SAFE]
        if bad or len(latin) > 8:
            raise SystemExit('맵 오류 %r->%r %s' % (jp, latin, bad or 'len>8'))

    # 검증 3: 완전성 — 패치본을 로스터 재검출, 가나 로스터명 잔존 0
    left = 0
    for path, lba, size, buf, plans in file_plans:
        pb = bytearray(buf)
        for o, nb, jp, latin, nf in plans:
            assert pb[o:o + len(nb)] == nb, '%s @0x%x 원문 불일치' % (path, o)
            pb[o:o + FIELD] = nf
        for o, n in roster_records(pb):
            if has_kana(bytes(pb[o:o + n])):
                jp = sf.decode(pb, o, n)
                if jp in ROMAJI:                      # 매핑된 가나 로스터명이 남음 = 누락
                    left += 1
                    if left <= 20:
                        print('  ⚠️잔존 %s @%s 0x%x' % (jp, path, o))
    if left:
        raise SystemExit('완전성 검증 실패: 가나 로스터명 잔존 %d' % left)

    print('검증 통과 (라운드트립·글리프·완전성).')

    # 미매핑 가나 이름 (있으면 보고)
    kana_nomap = {k: v for k, v in nomap.items() if any('゠' <= c <= 'ヿ' for c in k)}
    if kana_nomap:
        print('⚠️맵에 없는 가나 로스터 이름 %d종:' % len(kana_nomap))
        for k, v in sorted(kana_nomap.items(), key=lambda x: -x[1]):
            print('    %r x%d' % (k, v))

    # 상위 이름 요약
    print('\n최다 출현 이름:')
    for jp, c in sorted(names_hit.items(), key=lambda x: -x[1])[:12]:
        print('  %-14s %-9s x%d' % (jp, ROMAJI[jp], c))

    f.close()
    if not write:
        print('\n드라이런 — ISO 미기록 (--write 로 F: 기록).')
        return file_plans
    write_iso(file_plans)
    return file_plans


def write_iso(file_plans):
    import shutil, ecc
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s (먼저 build_smalltext --write 로 소형폰트 패치본 생성)' % dst)
    print('\nF: ISO 제자리 패치: %s' % dst)
    touched = set()
    with open(dst, 'r+b') as w:
        for path, lba, size, buf, plans in file_plans:
            # 원본(F:)에서 이 파일 논리 읽어 원문 대조 후 필드 덮기
            for o, nb, jp, latin, nf in plans:
                # 논리 오프셋 o..o+FIELD 를 섹터별로 기록
                for k in range(FIELD):
                    lo = o + k
                    sec = lba + lo // USER
                    pos = sec * RAW + HDR + (lo % USER)
                    w.seek(pos)
                    cur = w.read(1)
                    if k < len(nb):
                        if cur != nb[k:k + 1]:
                            raise SystemExit('%s @0x%x 원문 불일치(F:) — UPK가 이미 변경됨?' % (path, o))
                    w.seek(pos)
                    w.write(nf[k:k + 1])
                    touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    print('완료 ->', dst)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build(write='--write' in sys.argv)
