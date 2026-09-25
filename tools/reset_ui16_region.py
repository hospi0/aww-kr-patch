# -*- coding: utf-8 -*-
"""ui16 풀 영역을 **원본 바이트로 리셋**한다 (세션9 이후 재빌드 전 단계).

왜 필요한가 — ui16_kr.py의 슬롯 배정·번역이 바뀌면 F: ISO에 남은 이전 패치 위에
build_ui16 --write를 바로 돌리면 대조(원본 기대)가 실패한다. 이전 config를 손으로
재구성하는 대신 **원본 TRACK1 바이트를 그대로 되쓴다** — 안전하다.

★★세션12 개정 = 「플랜 오프셋」이 아니라 **풀 윈도우 전체**를 리셋한다.
  세션11 회귀사고의 원인: 이전 빌드가 패치했으나 새 플랜엔 없는 오프셋(당시 자동보급 등,
  세션12엔 SETTINGS 15 + 時間/その他 = 20곳)이 「리셋 사각지대」로 남아 새 폰트에서 깨진다.
  풀 윈도우(anchor lo..hi) 전체를 원본으로 되돌리면 어떤 구성 변화에도 사각이 안 생긴다.
  설정 윈도우(0x025bca..0x025d54)는 메시지 윈도우(0x024c6a..0x025ed0) 안에 포함되므로
  메시지 윈도우만 온전히 리셋해도 설정이 함께 원복된다.

안전 근거(세션12 실측): 리셋할 6개 윈도우(GAME 0x0969d2.., GMDT 0x01655a../0x01693c../
  0x024c12../0x024c6a../설정)는 **map-move·names16·missions16·typevals·gamepool 오프셋과
  겹침 0**(전수 확인). 윈도우 전체 되쓰기가 그 패치들을 안 건드린다.

하는 일:
  ① 964 폰트 영역(lba 259296)을 0으로 — build_ui16 --write의 「비어있음」 검사 통과용
  ② 6개 풀 윈도우 lo..hi 전체에 **원본 TRACK1 바이트** 되쓰기(설정 사각 포함)
  ③ 건드린 섹터 EDC/ECC 재계산
  ※ ASC16CG 디렉터리는 안 건드린다 — 뒤이어 돌릴 build_ui16 --write가 새 값으로 덮는다.

이 스크립트 뒤에는 반드시 `python tools/build_ui16.py --write` 를 돌린다.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import build_ui16 as B
from isoread import TRACK1, RAW, HDR, USER
from scan_files import files

# 리셋할 풀 앵커(윈도우 lo..hi 전체 되돌림). B.POOLS에 없는 앵커가 있으면 덧붙인다.
#   ★세션14에 설정 풀이 B.POOLS로 복귀했으므로 여기선 **중복만 피하면** 된다
#     (세션12엔 B.POOLS에 없어서 이 목록이 유일한 리셋 경로였다).
RESET_POOLS = list(B.POOLS)
for _extra in [('GMDT', '面セレクト', 0x140, 0x40, 'SETTINGS', True)]:
    if not any(p[0] == _extra[0] and p[1] == _extra[1] for p in RESET_POOLS):
        RESET_POOLS.append(_extra)


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def pool_windows(f, rev):
    """RESET_POOLS 앵커로 각 풀의 (mod, lba, lo, hi) 윈도우를 원본에서 계산."""
    ent = {p: (l, s) for p, l, s in files(skip_media=False)}
    wins = []
    for mod, anchor, back, fwd, tbl, wr in RESET_POOLS:
        lba, size = ent['/' + mod]
        d = read_file(f, lba, size)
        ab = B.enc_jp(anchor, rev)
        i = d.find(ab)
        if i < 0 or d.find(ab, i + 1) >= 0:
            raise SystemExit('%s 앵커 %r 히트 이상' % (mod, anchor))
        lo, hi = max(0, i - back), min(len(d), i + len(ab) + fwd)
        wins.append((mod, lba, lo, hi, d))
    return wins


def main():
    dst = os.path.join(B.OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    cm, rev = B.load_map()
    slot = B.build_slots()
    f = open(TRACK1, 'rb')
    wins = pool_windows(f, rev)
    hits, rlba, rsize, old_lba, old_size, cur_n, font = B.build_font(f, cm, slot)
    f.close()
    nsec = (len(font) + USER - 1) // USER

    print('리셋 대상 풀 윈도우 %d개 + 폰트영역 lba %d..%d' % (len(wins), B.NEW_LBA, B.NEW_LBA + nsec - 1))
    for mod, lba, lo, hi, d in wins:
        print('  %-5s 0x%06x..0x%06x (%d B)' % (mod, lo, hi, hi - lo))

    touched = set()
    with open(dst, 'r+b') as w:
        # ① 964 폰트 영역 0으로
        for k in range(0, nsec * USER, USER):
            sec = B.NEW_LBA + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(USER))
            touched.add(sec)
        # ② 풀 윈도우 전체를 원본 바이트로 되쓰기 (설정 사각 포함)
        for mod, lba, lo, hi, d in wins:
            for off in range(lo, hi):
                sec = lba + off // USER
                w.seek(sec * RAW + HDR + off % USER)
                w.write(d[off:off + 1])
                touched.add(sec)
        # ③ EDC/ECC
        print('건드린 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            rawb = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(rawb))

    # ── 검증: F: 풀 윈도우가 원본 TRACK1과 바이트 일치하는가 ──────────────────
    fd = open(dst, 'rb')
    bad = 0
    for mod, lba, lo, hi, d in wins:
        b = read_file(fd, lba, hi)
        if b[lo:hi] != d[lo:hi]:
            bad += 1
            print('  ❌%s 0x%06x..0x%06x 리셋 불일치' % (mod, lo, hi))
    z = read_file(fd, B.NEW_LBA, nsec * USER)
    if any(z):
        bad += 1
        print('  ❌폰트영역 비어있지 않음')
    fd.close()
    if bad:
        raise SystemExit('리셋 검증 실패 %d건' % bad)
    print('리셋 완료·검증 통과 — 풀 윈도우 전체 원본 일치, 폰트영역 0. 이제 build_ui16 --write.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
