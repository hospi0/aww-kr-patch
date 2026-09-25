# -*- coding: utf-8 -*-
"""전투맵 16×16 UI 라벨 한글화 — 1단계 (세션8-a).

무엇을 하나:
  ① ASC16CG 825글리프 → **885글리프**로 키우고 825~884에 한글 60자를 렌더해 넣는다.
     파일이 할당 섹터(52)를 넘으므로 **트랙 꼬리 빈 섹터로 재배치**하고
     ASC16CG 디렉터리 레코드 **2벌**을 모두 새 위치·크기로 갱신한다.
  ② GAME·GMDT의 UI 라벨을 한글 글리프 인덱스로 바꾼다.

왜 ASC16CG만 건드리나 — 로드 지점 역산 결과 화면마다 다른 폰트를 쓴다:
     GAME(브리핑·전투맵)·KEKKA(결과) = ASC16CG   ← 대상
     SAKUSEN=SAKUCG / INTERM=ASCIMCG / MUSEUM=ASCMSCG / GMSELDT=ASCGSCG
  같은 라벨이 그쪽에도 사본으로 있지만 **폰트가 달라 손대면 그 화면이 깨진다**.

왜 885인가 — 천장은 **VDP2 패턴 네임 테이블**이 `0x1E080`(=글리프 901)에 붙어 있어서다.
  세션3 실기(900에서 첫 깨짐)와 스테이트 2개 VRAM 실측(76·97글리프 여유)이 일치.
  885는 두 측정 모두의 안전선 아래다. (이 한계를 넘는 건 2단계 = PNT 이설.)

⚠️**종료자 `0xFFFF`는 절대 덮지 않는다.** 번역이 짧으면 `0x0000`으로만 패딩한다.
  (이번 세션에 세이브 화면이 바로 이 실수로 깨졌다 — build_gamepool 참조.)

빌드: python tools/build_ui16.py            드라이런(검증만)
      python tools/build_ui16.py --write    F: ISO 제자리 기록
      python tools/build_ui16.py --revert   원상복구
"""
import os, sys, json, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc
import ui16_kr as K

from hangul import render_kr
from isoread import TRACK1, RAW, HDR, USER
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO_DIR = r'F:\hospi\roms\ss roms\aww'

OLD_N, NEW_N = 825, 900
if '--legacy' in sys.argv:          # 세션8-a 구성으로 되돌릴 때만
    NEW_N = 885
if '--ceil964' in sys.argv:         # archive/ui16_kr_ko964 한글본 복원용(맵 이설 필요)
    NEW_N = 964
GLYPH = 128
NEW_LBA = 259296                 # 세션3이 쓴 트랙 꼬리 빈 자리(빌드 때 0인지 재확인)

# ★천장 = 964. 원래는 900이었다 — NBG3 맵이 VDP2 VRAM `0x1E000`에 있어 폰트(0x1E00~)가
#   거기서 막혔다. 세션9에서 **맵만 0x7E000으로 옮겨**(tools/build_mapmove.py, 데이터 패치)
#   0x20000까지 텄고, charnum 12비트 한계(240+idx*4 ≤ 4095)와 정확히 일치하는 964가 됐다.
#   ⚠️이 빌더로 900을 넘겨 쓰려면 **build_mapmove가 반드시 같이 적용돼야 한다.**
#   ⚠️글리프 재사용(안 쓰는 기존 슬롯 덮어쓰기)은 불가로 판명 — 세션9에서 「자유」로 보였던
#     115칸이 실은 미션명·부대명에 쓰이고 있었다(자유는 2칸뿐). free_slots.py는 그 근거 기록용.

# 풀 = (모듈, 앵커 원문, 앵커 앞으로, 앵커 뒤로, 번역표, 레코드경계요구)
#   레코드경계요구=True면 원문이 레코드 하나와 정확히 일치할 때만 바꾼다. 메시지는
#   짧은 항목(セーブ 등)이 긴 문장 속에 박혀 있어, 조각만 바꾸면 문장이 깨진다.
POOLS = [
    ('GAME', '累積度',              0x40, 0x80,   'LABELS',   False),  # 브리핑 HUD
    ('GMDT', '将軍を選択してください', 0x90, 0x08,   'LABELS',   False),  # 장군 화면 라벨
    ('GMDT', '中止終了中止占領墜落',   0x10, 0x60,   'LABELS',   False),  # 전투 상태·시간대·날씨
    # 시스템 메시지 풀 0x024C92~0x025D78 — 앵커는 유일하게 잡히는 긴 문장
    ('GMDT', '燃料タンクで攻撃することはできません。', 0x40, 0x1200, 'MESSAGES', True),
    # 부대정보 라벨 풀 0x016560~0x0165D8 (세션11) — 델리미터 구분, 레코드경계 매칭
    ('GMDT', '兵器タイプ', 0x10, 0x80, 'UNITINFO', True),
    # 설정화면 풀 0x025BE0~0x025D20 (세션11) — 세션12 B안에 뺐다가 **세션14에 복원**.
    #   슬롯 회수(asc16_reclaim)로 예산이 생겨 설정화면을 다시 한글로 되돌린다.
    ('GMDT', '面セレクト', 0x140, 0x40, 'SETTINGS', True),
]


def load_map():
    m = json.load(open(os.path.join(ROOT, 'work', 'fontmaps.json'), encoding='utf-8'))['SAKUCG']
    cm = {int(k): v for k, v in m.items()}
    rev = {}
    for k, v in cm.items():
        rev.setdefault(v, k)
    return cm, rev


def enc_jp(s, rev):
    return b''.join(struct.pack('>H', rev[c]) for c in s)


# 16×16 폰트엔 **전각 기호만** 있다(세션8-a). 반각으로 쓰면 글리프가 없어 빈칸이 된다.
PUNCT = {'.': '．', '?': '？', ',': '、', '·': '・', '!': '！', '%': '％', '~': 'ー'}

# 저장 위치 라벨 = 델리미터 필드 **중앙 정렬**(세션11 사용자 지적: MainRAM 우측 치우침).
#   本体RAM는 원래 앞2칸+본체RAM5+뒤2칸(중앙), カートリッジRAM는 9칸 꽉참 → 영문을 필드 중앙에
#   두어야 ◄►로 토글할 때 두 라벨 위치가 맞는다. 좌측 시작점 고정으로 쓰면 길이차로 어긋난다.
CENTER_LABELS = {'本体RAM', 'カートリッジRAM'}


def enc_kr(s, slot, rev):
    """번역문 → 워드열. 한글은 배정한 슬롯, 그 외는 원본 폰트에 있는 글리프."""
    out = bytearray()
    for c in s:
        if c in slot:
            out += struct.pack('>H', slot[c])
            continue
        for cand in (c, PUNCT.get(c), chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else None):
            if cand and cand in rev:
                out += struct.pack('>H', rev[cand])
                break
        else:
            raise SystemExit('글리프 없음: %r (문자열 %r)' % (c, s))
    return bytes(out)


# ★--legacy = 세션8-a가 실제로 F: ISO에 쓴 구성(885글리프·라벨만). **되돌릴 때만** 쓴다.
#   제자리 패치 도구는 「계획=원본에서」가 원칙이지만, 되돌리기는 **디스크에 실제로 쓰인
#   그 구성**으로 계획해야 대조가 맞는다(세션8-a에서 revert 2개가 깨졌던 것과 같은 함정).
LEGACY = '--legacy' in sys.argv


def encoder_glyphs(rev):
    """번역문이 **한글 아닌 문자로 쓰는** 글리프 인덱스 집합.

    ★회수 대상에서 반드시 빼야 한다. 회수 목록엔 `！`(757)·`▼`(761) 같은 기호가
      들어 있는데(어떤 일본어 텍스트도 안 쓰니 census상 자유), 우리 번역문이 그 문자를
      쓰면 enc_kr가 같은 인덱스를 기호로 인코딩한다. 그 자리를 한글로 덮어버리면
      기호 자리에 엉뚱한 한글이 찍힌다 — 자기 발등 찍기.
    """
    tables = [K.LABELS, K.MESSAGES, K.UNITINFO, K.SETTINGS]
    try:                                   # 세션15: 부대정보 타입값·16×16 유닛명도 같은 폰트를 쓴다
        import kr_s15 as S
        tables += [S.TYPEVAL_WEAPON, S.TYPEVAL_MOVE, S.UNIT16]
    except ImportError:
        pass
    need = set()
    for tbl in tables:
        for kr in tbl.values():
            for c in kr:
                if '가' <= c <= '힣':
                    continue
                for cand in (c, PUNCT.get(c),
                             chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else None):
                    if cand and cand in rev:
                        need.add(rev[cand])
                        break
    return need


def build_slots():
    """한글 → 글리프 인덱스. 정렬이 고정이라 빌드마다 같은 결과.

    확장 슬롯 825~899(75칸)를 먼저 쓰고, 모자라면 **회수 슬롯**으로 이어 붙인다
    (세션14). 세션9의 「재사용 불가(자유 2칸)」 판정은 그 뒤 유닛명·미션명이
    로마자화되면서 뒤집혔다 — asc16_reclaim.py 참조.
    """
    syl = K.budget() if LEGACY else K.budget_all()
    ext = list(range(OLD_N, NEW_N))
    grow = len(ext)
    if not LEGACY and len(syl) > grow:
        # ★★세션15 방침 = **전면 한글화 기준**([[feedback_aww_full_kr_budget]]).
        #   세션14는 「일본어로 남는 텍스트가 참조하지 않는 슬롯」만 회수해 60칸을 얻었지만,
        #   사용자 결정으로 그 보수성을 폐기했다 — 못 찾은 소비자가 깨져도 그건 어차피
        #   이 폰트를 쓰는 텍스트라 번역하면 사라지고, 그게 한글화의 목적이다.
        #   ⇒ **가나·한자 글리프 전체를 회수 대상**으로 본다.
        #   ⚠️단 라틴·숫자·로마숫자(Ⅰ~Ⅹ)·기호는 남긴다 — build_unit16/general16/names16 등이
        #     **로마자 텍스트를 그대로 두는** 곳이 많아, 그 인덱스를 덮으면 즉시 깨진다.
        import charmap
        _, rev = load_map()
        keep = encoder_glyphs(rev)

        # ⚠️문장부호성 가나는 회수하면 안 된다 — `ー`(U+30FC)는 build_unit16.ALT 가
        #   `'-' → 'ー'` 로 쓰는 **하이픈**이라 `B-17`·제식명이 전부 이걸 참조한다.
        #   (실기 증상: 「B-17」이 **「B목17」**. 세션15-c에 실제로 터졌다.)
        PUNCT_KANA = {'ー', '・', '゛', '゜', 'ヽ', 'ヾ', 'ゝ', 'ゞ'}

        def kana_or_kanji(i):
            ch = charmap.CHARS.get(i)
            if ch is None or len(ch) != 1 or ch in PUNCT_KANA:
                return False
            o = ord(ch)
            return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF

        reclaim = [i for i in range(1, OLD_N) if kana_or_kanji(i) and i not in keep]
        print('  회수 대상 = 가나·한자 글리프 %d칸 (라틴·숫자·로마숫자·기호는 보존)'
              % len(reclaim))
        ext += reclaim
    if len(syl) > len(ext):
        raise SystemExit('한글 %d자 > 확장 %d + 회수 %d칸'
                         % (len(syl), grow, len(ext) - grow))

    # ★★세션15-c 사고 수정: 예전엔 `{c: ext[i] for i,c in enumerate(syl)}` 로 **매번 새로**
    #   배정했다. budget_all() 뒤쪽 목록이 정렬돼 있어 **음절을 하나 추가하면 그 뒤가 전부
    #   한 칸씩 밀린다** — 이미 기록한 텍스트(부대정보·유닛명·UPK)가 통째로 어긋났다.
    #   실기 증상: 「정예병」→**「정네병」**.
    #   ⇒ 배정을 `work/asc16_slots.json` 에 **영구 고정**하고 신규만 남은 칸에 붙인다.
    #     (build_brief·build_museum·sakucg_kr 이 이미 쓰는 방식과 같다.)
    reg = os.path.join(ROOT, 'work', 'asc16_slots.json')
    slot = {}
    if os.path.exists(reg):
        slot = {k: v for k, v in json.load(open(reg, encoding='utf-8')).items()}
    # ★★세션15-e: 유닛명 음절은 **ASCMSCG와 같은 인덱스**를 써야 한다 —
    #   유닛명 표는 사본이 하나인데 전투화면(ASC16CG)·병기도감(ASCMSCG)이 같이 읽는다.
    #   (실기 증상: 병기도감 유닛명이 `37mm니サ進接`)
    import shared_slots
    _sh = shared_slots.build(verbose=False)
    for _c, _g in _sh.items():
        slot[_c] = _g
    taken = set(slot.values())
    # ★세션17: 부관이름 공용 슬롯(ASC16CG·SCHOOL 동일 인덱스)은 **배정 금지**.
    #   slot 에 넣으면 안 된다(음절 인덱스가 바뀐다) — 자리만 막는다.
    import shared_school_slots
    taken |= set(shared_school_slots.build(verbose=False).values())
    free = [g for g in ext if g not in taken]
    added = 0
    for c in syl:
        if c in slot:
            continue
        if not free:
            raise SystemExit('★ASC16CG 슬롯 고갈')
        slot[c] = free.pop(0)
        added += 1
    # 이제 안 쓰는 음절은 등록부에 남겨 둔다(다시 쓰일 때 같은 자리를 받도록 = 안정성)
    json.dump(slot, open(reg, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    used_reclaim = sum(1 for g in slot.values() if g < OLD_N)
    print('슬롯: 확장 %d칸 + 회수 %d칸 = %d칸 중 %d칸 사용 (신규 %d, 여유 %d)'
          % (grow, len(ext) - grow, len(ext), len(slot), added, len(ext) - len(slot)))
    if used_reclaim:
        print('  ★원본 글리프 %d칸을 한글로 재정의한다(회수 슬롯).' % used_reclaim)
    return slot


def read_file(f, lba, size):
    out = bytearray()
    for k in range(0, size, USER):
        f.seek((lba + k // USER) * RAW + HDR)
        out += f.read(min(USER, size - k))
    return bytes(out)


def at_record_bounds(d, j, nbytes):
    """레코드(문장) 하나와 정확히 일치하는가.

    이 풀의 레코드는 제어어(0xFFFx)나 널로 구분된다. 앞뒤가 그 둘 중 하나가 아니면
    더 긴 문장의 일부라는 뜻이므로 건드리지 않는다.
    """
    def sep(off):
        if off < 0 or off + 2 > len(d):
            return True
        w = struct.unpack_from('>H', d, off)[0]
        return w == 0 or w >= 0xFFF0
    return sep(j - 2) and sep(j + nbytes)


def plan_text(f, rev, slot):
    """(모듈, 오프셋, 원본바이트, 새바이트, jp, kr) 목록."""
    plans, mods = [], {}
    pools = POOLS[:3] if LEGACY else POOLS
    for mod, anchor, back, fwd, table, whole_rec in pools:
        if mod not in mods:
            hits, _, _, _ = find_dirrec(f, mod)
            if len(hits) != 1:
                raise SystemExit('%s 디렉터리 레코드 %d개' % (mod, len(hits)))
            _, lba, size, _ = hits[0]
            mods[mod] = (lba, size, read_file(f, lba, size))
        lba, size, d = mods[mod]
        ab = enc_jp(anchor, rev)
        i = d.find(ab)
        if i < 0 or d.find(ab, i + 1) >= 0:
            raise SystemExit('%s 앵커 %r 히트 %d개(1개여야 함)'
                             % (mod, anchor, d.count(ab)))
        lo, hi = max(0, i - back), min(len(d), i + len(ab) + fwd)
        print('  %-5s 앵커 %-14s → 풀 0x%06x..0x%06x' % (mod, anchor, lo, hi))
        # ★긴 라벨 먼저 — 深夜 안의 夜, 雪1 안의 雪 같은 부분일치를 막는다.
        tbl = getattr(K, table)
        taken = set()
        for jp in sorted(tbl, key=len, reverse=True):
            kr = tbl[jp]
            jb = enc_jp(jp, rev)
            p = lo
            while True:
                j = d.find(jb, p, hi)
                if j < 0:
                    break
                p = j + 2
                if (j - lo) % 2:                        # 워드 정렬만 인정
                    continue
                if any(x in taken for x in range(j, j + len(jb))):
                    continue                            # 더 긴 라벨이 이미 차지
                if whole_rec and not at_record_bounds(d, j, len(jb)):
                    continue                            # 문장 조각만 바꾸면 원문이 깨진다
                # 필드 용량 = 원문 + 바로 뒤에 이어지는 **널 패딩**까지.
                # 종료자(0xFFFF)나 다른 라벨(0이 아닌 값)은 절대 안 넘는다.
                cap = len(jb) // 2
                e = j + len(jb)
                while e + 2 <= hi and struct.unpack_from('>H', d, e)[0] == 0:
                    cap += 1
                    e += 2
                if len(kr) > cap:
                    raise SystemExit('%s %r→%r %d워드 > 용량 %d'
                                     % (mod, jp, kr, len(kr), cap))
                if jp in CENTER_LABELS:
                    # 필드 = 앞 널 + 원문 + 뒤 널(e까지). 그 안에서 중앙 정렬.
                    s = j
                    while s - 2 >= lo and struct.unpack_from('>H', d, s - 2)[0] == 0:
                        s -= 2
                    field_w = (e - s) // 2
                    if len(kr) > field_w:
                        raise SystemExit('%s %r→%r %d > 필드 %d'
                                         % (mod, jp, kr, len(kr), field_w))
                    raw = d[s:e]
                    if 0xFFFF in [struct.unpack_from('>H', raw, k)[0]
                                  for k in range(0, len(raw), 2)]:
                        raise SystemExit('%s 0x%06x 필드에 종료자 포함 — 중단' % (mod, s))
                    lead = (field_w - len(kr)) // 2
                    nb = (b'\x00' * (lead * 2) + enc_kr(kr, slot, rev)
                          ).ljust(field_w * 2, b'\x00')
                    taken.update(range(s, e))
                    plans.append((mod, s, raw, nb, jp, kr))
                    continue
                # 🐞세션17: 원문 길이만큼만 덮으면 **이전 빌드의 꼬리가 남는다.**
                #   「BGM→배경음악」을 다시 「BGM」으로 되돌렸더니 4번째 칸의 `악`이 살아남아
                #   실기에 `BGM악`으로 떴다. --resync 는 이전 기록을 안 보기 때문이다.
                #   ⇒ 필드 = 원문 + **뒤따르는 널 구간(e)** 까지 잡고 남는 칸을 널로 되쓴다.
                #     (원본에서 널인 자리를 널로 만드는 것이라 원본과 같아진다.)
                width = max(len(jb) // 2, len(kr), (e - j) // 2)
                raw = d[j:j + width * 2]
                if 0xFFFF in [struct.unpack_from('>H', raw, k)[0]
                              for k in range(0, len(raw), 2)]:
                    raise SystemExit('%s 0x%06x 필드에 종료자 포함 — 중단' % (mod, j))
                nb = enc_kr(kr, slot, rev).ljust(len(raw), b'\x00')
                taken.update(range(j, j + len(raw)))
                plans.append((mod, j, raw, nb, jp, kr))
    # 겹침 검사
    seen = {}
    for mod, o, raw, nb, jp, kr in plans:
        for k in range(len(raw)):
            if (mod, o + k) in seen:
                raise SystemExit('계획 겹침 %s @0x%x' % (mod, o + k))
            seen[(mod, o + k)] = 1
    return plans, mods


def build_font(f, cm, slot):
    hits, rlba, rsize, _ = find_dirrec(f, 'ASC16CG')
    if len(hits) != 2:
        raise SystemExit('ASC16CG 디렉터리 레코드 %d개(2개여야 함)' % len(hits))
    lbas = {h[1] for h in hits}
    sizes = {h[2] for h in hits}
    if len(sizes) != 1:
        raise SystemExit('ASC16CG 엔트리 크기 불일치 %s' % sizes)
    size = sizes.pop()
    lba = sorted(lbas)[0]
    n = size // GLYPH
    if n not in (OLD_N, NEW_N):
        raise SystemExit('ASC16CG %d글리프 — 예상 %d' % (n, OLD_N))
    font = bytearray(read_file(f, lba, OLD_N * GLYPH))
    font += bytearray((NEW_N - OLD_N) * GLYPH)
    for ch, gi in slot.items():
        font[gi * GLYPH:(gi + 1) * GLYPH] = render_kr(ch, ramp='dark')
    # ★세션17: 사관학교 동료(부관) 이름은 **사본 하나를 SCHOOL 폰트와 같이 읽는다.**
    #   ⇒ 두 폰트의 같은 인덱스에 같은 글리프를 그려야 한다(shared_school_slots).
    #   ⚠️`slot` 에 병합하지 **않는다** — 병합하면 같은 음절의 인덱스가 바뀌어
    #     이미 기록한 ASC16CG 텍스트가 통째로 어긋난다(세션15-c 「정네병」 사고).
    #     여기서는 **글리프만 추가로 그린다**. 인코딩은 각자 자기 등록부를 쓴다.
    import shared_school_slots
    for ch, gi in shared_school_slots.build(verbose=False).items():
        font[gi * GLYPH:(gi + 1) * GLYPH] = render_kr(ch, ramp='dark')
    return hits, rlba, rsize, lba, size, n, bytes(font)


def main():
    revert = '--revert' in sys.argv
    # ★--resync (세션15 추가): 번역·슬롯 구성이 바뀐 재빌드용.
    #   구성이 바뀌면 --write(원본 기대)도 --revert(패치본 기대)도 바이트 대조에 걸린다.
    #   현재 값이 무엇이든 새 계획으로 덮되, 덮기 전 **구분자(0xFFFF) 없음 + 폰트 범위 안**을
    #   확인한다(build_brief·build_gamepool 과 같은 설계).
    resync = '--resync' in sys.argv
    write = '--write' in sys.argv or revert or resync
    dst = os.path.join(OUT_ISO_DIR, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        raise SystemExit('대상 ISO 없음: %s' % dst)

    cm, rev = load_map()
    slot = build_slots()
    print('한글 %d자 → 글리프 %d~%d (ASC16CG %d→%d)'
          % (len(slot), min(slot.values()), max(slot.values()), OLD_N, NEW_N))

    # ★계획(원문·원본 디렉터리 레코드)은 **원본 ISO**에서 뽑는다. 패치본에서 뽑으면
    #   앵커(`累積度`)가 이미 한글이라 안 잡히고, 되돌릴 lba/size도 패치값이 들어가
    #   `--revert`가 통째로 깨진다. 기록·검증만 F: 패치본에 한다.
    f = open(TRACK1, 'rb')
    hits, rlba, rsize, old_lba, old_size, cur_n, font = build_font(f, cm, slot)
    print('ASC16CG lba=%d size=%d (%d글리프), 디렉터리 레코드 2벌' % (old_lba, old_size, cur_n))
    nsec = (len(font) + USER - 1) // USER
    print('새 폰트 %d B / %d 섹터 → lba %d..%d' % (len(font), nsec, NEW_LBA, NEW_LBA + nsec - 1))

    plans, mods = plan_text(f, rev, slot)
    print('\n텍스트 %d곳' % len(plans))
    for mod, o, raw, nb, jp, kr in plans:
        print('  %-5s 0x%06x %-8s → %s' % (mod, o, jp, kr))
    want = (set(K.LABELS) if LEGACY else
            set(K.LABELS) | set(K.MESSAGES) | set(K.UNITINFO) | set(K.SETTINGS))
    missing = want - {p[4] for p in plans}
    if missing:
        print('\n⚠️풀에서 못 찾은 라벨 %d개: %s' % (len(missing), ' '.join(sorted(missing))))

    if '--verify' in sys.argv:      # 기록은 그대로 두고 독립 되읽기만 다시 한다
        f.close()
        verify(dst, plans, mods, font, slot, cm)
        return
    if not write:
        f.close()
        print('\n드라이런 — ISO 미기록 (--write / --revert).')
        return

    f.close()
    # ★★세션14 버그픽스 — 루트 디렉터리는 **대상 ISO(F:)** 에서 읽는다.
    #   원본 TRACK1에서 읽어 통째로 되쓰면, 다른 도구가 재배치해 둔 항목
    #   (ASCGSCG 259357·ASCMSCG 3434)이 **전부 원본 값으로 리셋**된다.
    #   실제로 그 사고가 났다: ASCMSCG를 3434에 놓았는데 ASCGSCG 레코드가 3434를
    #   가리키게 되어 메뉴·브리핑·병기도감이 한꺼번에 깨졌다. 점검·복구 = fix_dirrec.py.
    #   ⚠️--revert도 마찬가지다. 되돌릴 값(old_lba/old_size)은 원본에서 뽑되,
    #     **그 레코드만** 고치고 나머지는 대상 ISO의 현재 값을 보존해야 한다.
    with open(dst, 'rb') as fd:
        rd = bytearray(read_file(fd, rlba, rsize))
    # 재배치 자리가 정말 비어 있는지 — **기록 대상(F:)** 에서 확인해야 의미가 있다
    if not revert and not resync:
        with open(dst, 'rb') as chk:
            for s_ in range(NEW_LBA, NEW_LBA + nsec):
                if any(read_file(chk, s_, USER)):
                    raise SystemExit('★lba %d 비어있지 않음 — 다른 자리 필요' % s_)

    for _, _, _, rec_off in hits:
        struct.pack_into('<I', rd, rec_off + 2, old_lba if revert else NEW_LBA)
        struct.pack_into('>I', rd, rec_off + 6, old_lba if revert else NEW_LBA)
        struct.pack_into('<I', rd, rec_off + 10, OLD_N * GLYPH if revert else len(font))
        struct.pack_into('>I', rd, rec_off + 14, OLD_N * GLYPH if revert else len(font))

    print('\nF: ISO 제자리 %s' % ('원상복구' if revert else '패치'))
    touched = set()
    with open(dst, 'r+b') as w:
        def put(lba, data):
            for k in range(0, len(data), USER):
                sec = lba + k // USER
                w.seek(sec * RAW + HDR)
                w.write(data[k:k + USER].ljust(USER, b'\x00')[:USER])
                touched.add(sec)
        if revert:
            put(NEW_LBA, bytes(nsec * USER))            # 확장본 자리 0으로
        else:
            put(NEW_LBA, font)
        put(rlba, bytes(rd))
        for mod, o, raw, nb, jp, kr in plans:
            lba = mods[mod][0]
            src, dstb = (nb, raw) if revert else (raw, nb)
            if resync:
                # 현재 바이트를 읽어 **구분자가 없고 전부 폰트 범위 안**인지만 확인하고 덮는다
                cur = bytearray()
                for k in range(len(raw)):
                    lo = o + k
                    sec = lba + lo // USER
                    w.seek(sec * RAW + HDR + lo % USER)
                    cur += w.read(1)
                for k in range(0, len(cur) - 1, 2):
                    v = (cur[k] << 8) | cur[k + 1]
                    if v >= 0xFFF0:
                        raise SystemExit('%s @0x%x 현재값에 구분자 %04X — 덮으면 위험' % (mod, o, v))
                    if v >= NEW_N:
                        raise SystemExit('%s @0x%x 현재값 글리프 %d ≥ %d' % (mod, o, v, NEW_N))
            for k in range(len(raw)):
                lo = o + k
                sec = lba + lo // USER
                pos = sec * RAW + HDR + lo % USER
                w.seek(pos)
                if not resync and w.read(1) != src[k:k + 1]:
                    raise SystemExit('%s @0x%x 대조 실패 — %s'
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
        verify(dst, plans, mods, font, slot, cm)


def verify(dst, plans, mods, font, slot, cm):
    """독립 되읽기 — 빌더 내부 상태가 아니라 기록된 ISO를 다시 읽는다."""
    bad = 0
    inv = {v: k for k, v in slot.items()}
    with open(dst, 'rb') as r:
        hits, _, _, _ = find_dirrec(r, 'ASC16CG')
        for _, lba, size, _ in hits:
            if (lba, size) != (NEW_LBA, len(font)):
                bad += 1
                print('  ❌디렉터리 레코드 lba=%d size=%d' % (lba, size))
        got = read_file(r, NEW_LBA, len(font))
        if got != font:
            bad += 1
            print('  ❌폰트 되읽기 불일치')
        secs = set()
        for mod, o, raw, nb, jp, kr in plans:
            lba = mods[mod][0]
            cur = bytearray()
            for k in range(len(nb)):
                lo = o + k
                sec = lba + lo // USER
                secs.add(sec)
                r.seek(sec * RAW + HDR + lo % USER)
                cur += r.read(1)
            if bytes(cur) != nb:
                bad += 1
                print('  ❌%s 0x%06x 텍스트 불일치' % (mod, o))
                continue
            # ★디코드 검사는 **인코더와 같은 표**로 해야 한다. 한글 슬롯만 보고 검사하면
            #   공백·「？」·라틴이 사라져 멀쩡한 문자열이 거짓 실패로 잡힌다(세션9에서 75건).
            dec = ''.join(inv.get(w, cm.get(w, '·' if w else ' '))
                          for w in (struct.unpack_from('>H', cur, k)[0]
                                    for k in range(0, len(cur), 2)))
            want = ''.join(inv.get(w, cm.get(w, '·' if w else ' '))
                           for w in (struct.unpack_from('>H', nb, k)[0]
                                     for k in range(0, len(nb), 2)))
            if dec != want:
                bad += 1
                print('  ❌%s 0x%06x 디코드 %r != %r' % (mod, o, dec, want))
        for sec in sorted(secs | {NEW_LBA}):
            r.seek(sec * RAW)
            raw = r.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
                print('  ❌섹터 %d EDC/ECC' % sec)
    if bad:
        raise SystemExit('독립검증 실패 %d건' % bad)
    print('독립검증 통과 — 디렉터리 2벌·폰트·텍스트 되읽기 일치, EDC/ECC 유효.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
