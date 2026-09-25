# -*- coding: utf-8 -*-
"""NBG3 패턴네임 테이블 이설 — 900 글리프 천장을 964로 여는 **데이터 전용** 패치 (세션9).

문제: ASC16CG는 VDP2 VRAM `0x1E00`부터 올라가는데 **NBG3 맵이 `0x1E000`에 있어서**
      0x1E00 + 900×128 = 0x1E000 으로 딱 맞닿는다. 그래서 900이 천장이었다.

세션8-a는 「폰트를 다른 128KB 블록으로 옮기자」고 했으나, 세션9 조사에서 **GAME이
블록1·2·3을 모두 쓰기 때문에 폰트(123KB)를 통째로 놓을 빈 블록이 없다**는 게 확인됐다.
⇒ 대신 **맵(8KB)만** 옮긴다. 그러면 폰트가 `0x1E00~0x20000`을 다 써서 **964글리프**가 된다.

세션8-a가 이 길을 접은 이유(「맵 주소는 런타임 생성 구조체라 정적으로 못 바꾼다」)는
**오판이었다**: `GAME 0x0609169A`가 리터럴 `0x25E1E000`을 그 구조체 `+0x0C`에 그대로
넣는다. 즉 맵 주소는 데이터고, 나머지는 화면상 글자 위치 리터럴이다.

패치 3종 — 전부 데이터, 코드 주입 0줄:
  ① 맵·글자위치 리터럴 `0x25E1Exxx → 0x25E5Exxx`
     **모듈0 6 + GAME 222 + KEKKA 57 + INTERM 29**
     ★값 범위로만 고르지 않고 **`mov.l @(disp,pc)` 명령이 실제로 읽는 리터럴**인지 확인한다
       (원본 대조 결과 279개 전부 참조됨 = 우연히 값이 겹친 데이터 없음).
  ② VRAM 액세스 사이클 표(GAME 7·KEKKA 1·INTERM 3): NBG3 패턴네임을 A0 → **CYCB0**로.
     맵이 뱅크 B로 갔으니 그 뱅크에 사이클이 없으면 VDP2가 패턴을 못 읽는다.
     ★**타임슬롯은 그대로, 뱅크만**(A0U의 `3` 자리 → B0U 같은 자리).
  ③ MUSEUM·SAKUSEN·SCHOOL·GMSEL(DT)는 **한 바이트도 안 건드린다** — 자기 맵을 따로 쓴다
     (MUSEUM 0x40000 · SAKUSEN 0x6A000 · SCHOOL 0x2E000).

★★**왜 0x5E000인가 — 세션9에서 두 번 틀린 끝에 나온 답이다.**
  ⓐ 1차 `0x7E000`(뱅크 B1)은 **실기 전면 깨짐**. `RAMCTL=0x1100`이라 **VRBMD=0 = 뱅크 B는
    분할 안 됨** ⇒ CYCB1은 통째로 무시된다. "B1이 FFFF라 비었다"가 아니라 **애초에 안 쓰이는
    레지스터**였다. ⇒ 사이클은 CYCB0에 넣어야 한다.
  ⓑ 목적지를 **0x40000~0x5FFFF(B0)** 로 잡으면 **뱅크 B 분할 여부와 무관하게 언제나 CYCB0**다
    (INTERM은 B를 분할해 B1을 쓰므로, 0x6xxxx·0x7xxxx에 두면 모듈마다 레지스터가 갈린다).
  ⓒ `0x5E000`은 스테이트 6장 전부에서 비어 있고 GAME·KEKKA·INTERM 리터럴에도 없다
    (0x29~0x2F를 쓰는 스테이트가 하나 있었으나 **MUSEUM**이라 무관 — 자기 맵을 쓴다).

★★**맵의 진짜 주인은 모듈0이다.** GAME 리터럴만 고쳤을 때 레지스터가 안 움직였다
  (`MPABN3=0f0f` 그대로). 실제 파라미터 구조체는 **모듈0 `0x06039990`**(+0x08·+0x0C)이고
  그 값은 모듈0 리터럴 `0x06010EEC`에서 온다. ⇒ 모듈0도 같이 패치해야 하고, 그러면
  같은 기본값을 쓰는 INTERM도 함께 움직이므로 INTERM 리터럴·사이클도 같이 옮긴다.

⚠️**사이클 표 검출은 2바이트 정렬로 훑어야 한다** — 4바이트로만 보다가 GAME의 표 2개
  (`0x09693A`·`0x097A86`)를 놓쳤고, 실기 스테이트의 레지스터 값이 우리 표와 안 맞는 걸로
  드러났다. 오검출(코드가 표로 잡힘)은 **코드 8~E 미사용 + 포인터 참조** 두 조건으로 막는다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

OLD_MAP, NEW_MAP = 0x25E1E000, 0x25E5E000      # 0x1E000(뱅크 A0) → 0x5E000(뱅크 B0)
SPAN = 0x2000                                   # 1x1 플레인 = 64×64셀 × 1워드 = 8KB
DELTA = NEW_MAP - OLD_MAP
OLD_OFF, NEW_OFF = 0x0001E000, 0x0005E000       # ★맵 주소의 **오프셋 형식**(구조체 필드)

MODULES = ('0', 'GAME', 'KEKKA', 'INTERM')
BASES = {'0': 0x0600C000}        # 모듈0만 적재 주소가 다르다
DEFAULT_BASE = 0x06060000
EXPECT_LIT = {'0': 6, 'GAME': 222, 'KEKKA': 57, 'INTERM': 29}   # 원본 대조용
EXPECT_CYC = {'0': 0, 'GAME': 9, 'KEKKA': 1, 'INTERM': 3}   # GAME=NBG3 7 +NBG1(거점리스트)+NBG0(설정변경)
# ★맵 레지스터(MPABN3) 소스 = 스크롤 설정 구조체의 플레인 A/B/C/D 주소(오프셋형 0x0001E000).
#   mov.l이 안 읽는 순수 데이터라 plan_literals(참조 필수)가 통째로 놓쳤다 → MPABN3=0f0f로 남아
#   「텍스트는 0x5E000에 쓰였는데 NBG3는 0x1E000(폰트)을 읽어」 상황표 빈칸 증상을 냈다(세션10 규명).
EXPECT_STRUCT = {'GAME': 8, 'KEKKA': 4, 'INTERM': 4}   # 각 모듈의 클린 4연속 블록


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def pc_read_targets(d, base):
    """`mov.l @(disp,pc),Rn` 이 읽는 리터럴 주소 집합."""
    out = set()
    for o in range(0, len(d) - 1, 2):
        w = struct.unpack_from('>H', d, o)[0]
        if (w >> 12) == 0xD:
            pc = base + o
            out.add(((pc + 4) & ~3) + (w & 0xFF) * 4)
    return out


def plan_literals(d, base):
    """[(오프셋, 원본4B, 새4B)] — 맵 영역을 가리키는 리터럴만."""
    read = pc_read_targets(d, base)
    plans, skipped = [], []
    for o in range(0, len(d) - 3, 4):
        v = struct.unpack_from('>I', d, o)[0]
        if not (OLD_MAP <= v < OLD_MAP + SPAN):
            continue
        if base + o not in read:                 # 명령이 안 읽으면 그냥 같은 값의 데이터다
            skipped.append((o, v))
            continue
        plans.append((o, struct.pack('>I', v), struct.pack('>I', v + DELTA)))
    return plans, skipped


# 액세스 사이클 코드: 0~3=NBG0~3 패턴네임, 4~7=NBG0~3 문자패턴, 8~B=수직셀스크롤,
#                     C=CPU, D~F=액세스 없음
N3_PN, N3_CHAR, NONE = 3, 7, 0xF


def nibbles(w):
    return [(w >> (12 - 4 * i)) & 0xF for i in range(4)]


def pointed_at(d, base, addr, read, span=0x44):
    """이 자리(또는 그 앞 0x44바이트 안)를 코드가 포인터로 들고 있는가.

    사이클 표는 화면 설정 구조체 안에 있고 그 구조체를 코드가 리터럴 포인터로 가리킨다.
    값만 보고 고르면 압축 데이터가 우연히 같은 모양일 수 있으므로 이 확인을 통과해야 한다.
    """
    for k in range(0, span, 4):
        pat = struct.pack('>I', addr - k)
        start = 0
        while True:
            i = d.find(pat, start)
            if i < 0:
                break
            start = i + 4
            if i % 4 == 0 and base + i in read:
                return True
    return False


def plan_structs(d):
    """[(오프셋, 원본4B, 새4B)] — 스크롤 설정 구조체의 맵 플레인 주소(오프셋형).

    구조체는 플레인 A/B/C/D 주소 4개를 4연속 롱워드로 담는다(1×1 플레인이라 4개 다 동일).
    이 값을 셋업 루틴이 `>>13` 해서 MPABN3/MPCDN3 레지스터로 만든다. 즉 **NBG3가 어디를 읽는지**를
    결정하는 진짜 소스다. plan_literals가 옮기는 25E1Exxx(=CPU가 텍스트를 쓰는 목적지)와 짝을 이룬다 —
    둘 다 옮겨야 쓰는 곳과 읽는 곳이 일치한다.
    ★고립된 0x0001E000(압축 데이터의 우연)은 제외하려고 **인접(≥2연속)** 조건을 건다.
    """
    n = len(d)
    is_map = [False] * (n // 4)
    for i in range(n // 4):
        if struct.unpack_from('>I', d, i * 4)[0] == OLD_OFF:
            is_map[i] = True
    plans = []
    for i in range(n // 4):
        if not is_map[i]:
            continue
        if not ((i > 0 and is_map[i - 1]) or (i + 1 < len(is_map) and is_map[i + 1])):
            continue                             # 고립 = 노이즈, 건너뜀
        o = i * 4
        plans.append((o, struct.pack('>I', OLD_OFF), struct.pack('>I', NEW_OFF)))
    return plans


def plan_cycles(d, base):
    """[(오프셋, 원본16B, 새16B, 설명)] — 옮긴 맵을 읽는 텍스트 레이어의 패턴네임을 A0→B0로.

    ★★세션10 정정: 원래 **NBG3만** 옮겼는데, 같은 맵(0x1E000)을 **화면마다 다른 레이어**로
      그린다는 게 실기로 드러났다(상황표=NBG3, 거점리스트=NBG1). 16×16 텍스트 맵은 원래
      0x1E000 **한 곳**뿐이라(그래서 옮기면 폰트 공간이 열렸다), 그 맵을 읽는 레이어면 어느
      것이든 PN 사이클을 옮겨야 한다. ⇒ 표가 실제로 쓰는 텍스트 레이어 L을 **자동 판별**한다:
      문자패턴 코드 `4+L`이 A0L에, 패턴네임 코드 `L`이 A0U에 있으면 그 레이어가 A0 폰트로
      텍스트를 그리는 것 = 옮긴 맵을 읽는 레이어다(폰트는 늘 A0 0x1E00, 안 옮겼으므로).
    """
    plans = []
    read = pc_read_targets(d, base)
    for o in range(0, len(d) - 15, 2):   # ★2바이트 정렬 — 4바이트로 훑으면 표를 놓친다
        w = [struct.unpack_from('>H', d, o + 2 * i)[0] for i in range(8)]
        a0l, a0u, _a1l, _a1u, _b0l, b0u, _b1l, _b1u = w
        # ★텍스트 오버레이 시그니처(실측 8표 전부·오검출 0):
        #   A0U = 「PN 코드 L(0~3)」 슬롯0 + 나머지 F  (3fff=NBG3, 1fff=NBG1)
        #   A0L 슬롯0 = 문자 코드 4+L                  (7fff=NBG3, 5fff=NBG1)
        #   즉 A0을 이 텍스트 레이어가 슬롯0으로 독점한다. B0U 슬롯0이 비어 있어야 옮긴다.
        L = a0u >> 12
        if not (L <= 3 and (a0u & 0x0FFF) == 0x0FFF):
            continue
        if (a0l >> 12) != 4 + L:                  # 슬롯0 문자패턴이 이 레이어 것이어야
            continue
        if (b0u >> 12) != NONE:                   # 옮겨 갈 B0U 슬롯0이 비어 있어야
            continue
        # ★진짜 설정표 판별. 위 slot0 시그니처(A0U=X+FFF·A0L상위=4+L·B0U상위=F)가 매우
        #   특이해서 SH-2 코드 오검출(`7502 33e3`류: A0U가 XFFF 아님)은 이미 배제된다.
        #   ⚠️세션9의 「8~E 코드는 안 쓴다」 가정은 틀렸다 — 설정변경 표(0x942F4)는 A1L=3cd5로
        #     CPU(C)·무액세스(D) 코드를 실제로 쓴다(s13 실기 레지스터로 확인). 그 필터를 빼야 잡힌다.
        alln = [n for x in w for n in nibbles(x)]
        if alln.count(NONE) < 8:                  # 사이클표는 미사용(F)이 많다
            continue
        # ⚠️「패턴네임은 레이어당 한 번」은 규칙이 아니다 — 축소 표시 레이어는 여러 번 읽는다
        #   (실제로 `f010`인 GAME 0x0954B4가 그 규칙에 걸려 빠졌었다. 실기 레지스터와 대조해 발견).
        if not pointed_at(d, base, base + o, read):
            continue
        na0u = a0u | (NONE << 12)                                  # A0U 슬롯0 제거
        nb0u = (b0u & 0x0FFF) | (L << 12)                          # B0U 슬롯0에 PN L
        moved = ['NBG%d' % L]
        nw = list(w)
        nw[1], nw[5] = na0u, nb0u
        old = b''.join(struct.pack('>H', x) for x in w)
        new = b''.join(struct.pack('>H', x) for x in nw)
        plans.append((o, old, new,
                      'A0U %04x→%04x  B0U %04x→%04x (%s)' % (a0u, na0u, b0u, nb0u, ','.join(moved))))
    return plans


def build_plans(f):
    out = []
    for mod in MODULES:
        hits, _, _, _ = find_dirrec(f, mod)
        if len(hits) != 1:
            raise SystemExit('%s 디렉터리 레코드 %d개' % (mod, len(hits)))
        _, lba, size, _ = hits[0]
        d = read_file(f, lba, size)
        base = BASES.get(mod, DEFAULT_BASE)
        lits, skipped = plan_literals(d, base)
        cycs = plan_cycles(d, base)
        structs = plan_structs(d)
        if mod in EXPECT_LIT and (len(lits) != EXPECT_LIT[mod] or len(cycs) != EXPECT_CYC[mod]):
            raise SystemExit('%s 리터럴 %d(기대 %d)·사이클 %d(기대 %d) — 원본이 아닌가?'
                             % (mod, len(lits), EXPECT_LIT[mod], len(cycs), EXPECT_CYC[mod]))
        if mod in EXPECT_STRUCT and len(structs) != EXPECT_STRUCT[mod]:
            raise SystemExit('%s 맵 구조체 필드 %d(기대 %d) — 원본이 아닌가?'
                             % (mod, len(structs), EXPECT_STRUCT[mod]))
        print('%-6s lba=%-6d 맵 리터럴 %3d개 + 구조체필드 %d개 패치 (값 겹침 비참조 %d개 제외)'
              % (mod, lba, len(lits), len(structs), len(skipped)))
        for o, _old, _new, why in cycs:
            print('        사이클표 0x%06x  %s' % (o, why))
        for o, _old, _new in structs:
            print('        맵구조체 0x%06x  0x%05X→0x%05X' % (o, OLD_OFF, NEW_OFF))
        out.append((mod, lba, size,
                    [(o, a, b) for o, a, b in lits]
                    + [(o, a, b) for o, a, b, _ in cycs]
                    + [(o, a, b) for o, a, b in structs]))
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
                if cur == tgt:                   # ★위치별 멱등 — 이미 목표값이면 통과
                    skipped += 1
                    continue
                if cur != src:                   # 원본도 목표도 아님 = 진짜 손상
                    raise SystemExit('%s 0x%06x 대조 실패(cur=%s src=%s) — %s'
                                     % (mod, off, cur.hex(), src.hex(),
                                        '패치본이 아님' if revert else '예상 밖 값'))
                for k in range(len(old)):
                    sec, pos = sect_pos(lba, off + k)
                    w.seek(pos)
                    w.write(tgt[k:k + 1])
                    touched.add(sec)
        print('쓴 섹터 %d개 (이미 %s 상태라 건너뛴 위치 %d개), EDC/ECC 재계산...'
              % (len(touched), '복구' if revert else '패치', skipped))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    with open(dst, 'rb') as r:                   # 독립 되읽기
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
    print('독립검증 통과 — 리터럴·사이클표 되읽기 일치, EDC/ECC 유효.')


def main():
    revert = '--revert' in sys.argv
    with open(TRACK1, 'rb') as f:                # ★계획은 언제나 **원본**에서
        plans = build_plans(f)
    n = sum(len(p[3]) for p in plans)
    print('\n합계 %d곳 (맵 0x%05X → 0x%05X)' % (n, OLD_MAP & 0xFFFFF, NEW_MAP & 0xFFFFF))
    if not ('--write' in sys.argv or revert):
        print('드라이런 — ISO 미기록 (--write / --revert).')
        return
    apply(plans, revert)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
