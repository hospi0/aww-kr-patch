# -*- coding: utf-8 -*-
"""이분 실험 — 전투 유닛 패널의 「〈이름〉配下」가 폰트 텍스트인가 그래픽인가 (세션8).

배경. 정적 증거가 정확히 갈렸다:
  · 텍스트 쪽 — 화면 픽셀이 ASC16CG 글리프 534(配)·363(下)와 모양이 같다.
                같은 패널의 「歩兵」은 독립 문자열 사본이 3개(GMDT·MUSEUM·SAKUSEN) 있고,
                옆의 이름 「Reichnau」는 세션6에서 우리가 UPK 로스터를 패치해 실제로 바뀌었다.
  · 그래픽 쪽 — **디스크 전체(610MB)에 독립 「配下」 문자열이 0개**. 어떤 폰트의 인덱스
                공간(ASC16CG/SAKUCG 534·363, ASCIMCG 437·404)으로도 없다. 문장 속에만 있다.
                이건 세션6-b의 `休息`과 같은 signature였고, 그때 답은 **그래픽**이었다.
  ⚠️픽셀 일치는 증거가 못 된다 — 세션6-b에서 攻撃 버튼도 폰트 글리프와 픽셀이 같았는데 그래픽이었다.

⇒ 정적으로는 못 가른다. **완전한 반례 실험 한 번**으로 끝낸다.
   세션6-b 교훈: 「처음에 완전하게(전 폰트·전 사본) 한 번만」. 한 곳이라도 빠지면 결론이 뒤집힌다.

방법. 디스크 전체를 **글리프 비트맵(128바이트) 내용으로 검색**해 사본을 빠짐없이 찾아
      알아보기 쉬운 표식으로 덮는다. 파일명·LBA 하드코딩을 안 하므로 누락이 구조적으로 불가능하다.
      전수 결과: 配 6곳(SCHOOL·SAKUCG·**ASC16CG ×2**·ASCMSCG·ASCIMCG)
                下 8곳(BKCK·SCHOOL·SAKUCG·**ASC16CG ×2**·ASCGSCG·ASCMSCG·ASCIMCG)

표식을 다르게 준다 — 配=■(꽉 찬 사각) / 下=□(속 빈 사각). 한쪽만 바뀌는 경우도 판독된다.

판독(전투에서 유닛 선택 → 우하단 패널):
  「■□」로 바뀜      → **폰트 텍스트 확정.** 코드의 인덱스 참조를 찾아 폰트에 휘·하를 추가해 교체.
  「配下」 그대로     → **그래픽 확정.** 세션7 코드주입(VDP1 텍스처) 경로로 간다.
  한쪽만 바뀜        → 두 글자가 서로 다른 경로(하나는 텍스트, 하나는 그래픽).
  ★다른 텍스트(支配下·配下兵器·以下…)에도 표식이 뜨는 게 정상이다. 실험이 살아있다는 증거.

빌드: python tools/exp_haika.py            드라이런(스캔·계획만)
      python tools/exp_haika.py --write    F: ISO 기록 (+ build/haika_exp_plan.json)
      python tools/exp_haika.py --revert   원본 글리프로 복구
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'
PLAN = os.path.join(ROOT, 'build', 'haika_exp_plan.json')
ASC16 = os.path.join(ROOT, 'work', 'extract', 'ASC16CG')

IDX_HAI, IDX_KA = 534, 363          # 配, 下 (ASC16CG/SAKUCG/ASCMSCG 공통 인덱스)


def pack_glyph(mat):
    """16x16 값행렬 -> 폰트 128바이트(8x8셀 TL,TR,BL,BR / 저니블=왼쪽)."""
    out = bytearray(128)
    for c in range(4):
        oy, ox = (c // 2) * 8, (c % 2) * 8
        for y in range(8):
            for x in range(4):
                lo = mat[oy + y][ox + x * 2] & 0xF
                hi = mat[oy + y][ox + x * 2 + 1] & 0xF
                out[c * 32 + y * 4 + x] = (hi << 4) | lo
    return bytes(out)


def marker(filled):
    m = [[0] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            edge = (1 <= y <= 14 and 1 <= x <= 14 and
                    (y in (1, 2, 13, 14) or x in (1, 2, 13, 14)))
            inner = 3 <= y <= 12 and 3 <= x <= 12
            m[y][x] = 15 if (edge or (filled and inner)) else 0
    return pack_glyph(m)


def scan(path, pats):
    """ISO 논리 스트림을 훑어 128바이트 패턴의 (lba, 섹터내offset) 전부를 찾는다."""
    found = {k: [] for k in pats}
    with open(path, 'rb') as f:
        lba = 0
        prev = b''
        CH = RAW * 2048
        while True:
            raw = f.read(CH)
            if not raw:
                break
            nsec = len(raw) // RAW
            ud = b''.join(raw[k * RAW + HDR:k * RAW + HDR + USER] for k in range(nsec))
            s = prev + ud
            for k, p in pats.items():
                i = s.find(p)
                while i >= 0:
                    abs_off = lba * USER + (i - len(prev))
                    found[k].append(abs_off)
                    i = s.find(p, i + 1)
            prev = s[-(max(len(p) for p in pats.values()) + 4):]
            lba += nsec
    return found


def rw(dst, plan, data_for, verify_for):
    """plan의 각 논리오프셋에 128B를 기록. 먼저 원문 대조."""
    import ecc
    touched = set()
    with open(dst, 'r+b') as w:
        for name, off in plan:
            src, new = verify_for[name], data_for[name]
            for k in range(128):
                lo = off + k
                sec = lo // USER
                pos = sec * RAW + HDR + (lo % USER)
                w.seek(pos)
                if w.read(1) != src[k:k + 1]:
                    raise SystemExit('%s @0x%x 대조 실패 — 예상과 다름' % (name, off))
                w.seek(pos)
                w.write(new[k:k + 1])
                touched.add(sec)
        print('쓴 섹터 %d개, EDC/ECC 재계산...' % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))


def main():
    d = open(ASC16, 'rb').read()
    orig = {'配': d[IDX_HAI * 128:(IDX_HAI + 1) * 128],
            '下': d[IDX_KA * 128:(IDX_KA + 1) * 128]}
    mark = {'配': marker(True), '下': marker(False)}
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    if '--revert' in sys.argv:
        if not os.path.exists(PLAN):
            raise SystemExit('계획 파일 없음: %s' % PLAN)
        pl = [(n, o) for n, o in json.load(open(PLAN, encoding='utf-8'))]
        print('원상복구 %d곳' % len(pl))
        rw(dst, pl, orig, mark)                     # 표식 -> 원본
        print('복구 완료.')
        return

    print('F: ISO 전수 스캔 중 (610MB)...')
    found = scan(dst, orig)
    plan = []
    for k in ('配', '下'):
        print('  %s : %d곳' % (k, len(found[k])))
        for o in found[k]:
            print('      LBA %-6d (논리 0x%x)' % (o // USER, o))
            plan.append((k, o))
    if not plan:
        raise SystemExit('글리프를 못 찾음 — 이미 표식이 씌워져 있나?')

    if '--write' not in sys.argv:
        print('\n드라이런 — 미기록 (--write 로 기록 / --revert 로 복구).')
        return
    os.makedirs(os.path.dirname(PLAN), exist_ok=True)
    json.dump(plan, open(PLAN, 'w', encoding='utf-8'))
    rw(dst, plan, mark, orig)                       # 원본 -> 표식
    print('완료 — 계획 저장:', PLAN)
    # 독립 되읽기
    ok = 0
    with open(dst, 'rb') as r:
        for name, off in plan:
            got = bytearray()
            for k in range(128):
                lo = off + k
                r.seek((lo // USER) * RAW + HDR + (lo % USER))
                got += r.read(1)
            if bytes(got) == mark[name]:
                ok += 1
    print('독립 되읽기 %d/%d 일치.' % (ok, len(plan)))
    if ok != len(plan):
        raise SystemExit('되읽기 불일치')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
