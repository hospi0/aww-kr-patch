"""한글 PoC 빌드.

범위: /GMSELDT 초기 메뉴 문자열 일부를 한글로 교체한다.
방식: **전부 length-locked 제자리 수정** — 파일 크기·오프셋 불변.
  1) ASCGSCG(=GMSELDT 전용 폰트)의 '텍스트 풀에서 안 쓰는' 글리프 슬롯에 한글 주입
  2) /GMSELDT 텍스트 레코드의 인덱스를 그 슬롯으로 교체 (남는 칸은 0=공백)
  3) Track01 사본에 기록 + 변경 섹터 EDC/ECC 재계산
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
import charmap, ecc
from hangul import render_bitmap, to_glyph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 패치된 Track01은 여기로 출력한다 (오디오 트랙·cue가 이미 들어 있는 실행용 폴더).
# 사용자 지시 2026-07-20.
OUT_ISO = r"F:\hospi\roms\ss roms\aww"
OUT = os.path.join(ROOT, "build")     # xdelta·계획 json 등 부산물
FONT = r"C:\Windows\Fonts\gulim.ttc"
FONT_PX = 16

POOL0, POOL1 = 0x710, 0x13dc     # GMSELDT 텍스트 풀 (docs/02)

# (레코드 오프셋, 원본 길이(워드), 한국어) — 길이 초과 시 빌드 실패
EDITS = [
    (0x1332, 3, "저장"),
    (0x133a, 3, "로드"),
    (0x134a, 3, "아니오"),
    (0x1352, 3, "예"),
    (0x1362, 9, " 본체 RAM"),
    (0x1376, 9, "카트리지 RAM"),
    (0x139e, 9, "게임 계속하기"),
    (0x13b2, 9, "게임 끝내기"),
    (0x12e4, 38, "  기록을 불러왔습니다.\x01  게임을 시작합니다."),  # \x01 = {FD} 줄바꿈
]

CTRL_FD = 0xFFFD

# 게임 폰트에 없는 문자 → 대체 글리프
ALIAS = {".": "．", ",": "、", "?": "？", "!": "！"}


def all_entries(path):
    """같은 이름의 디렉터리 엔트리가 여러 개일 수 있다(ASC16CG는 2개)."""
    out = [(lba, size) for p, lba, size in files(skip_media=False) if p == path]
    if not out:
        raise SystemExit("no file " + path)
    return out


def index_of(path):
    return all_entries(path)[0]


def used_indices(gmseldt):
    u = set()
    i = POOL0
    while i < POOL1:
        v = (gmseldt[i] << 8) | gmseldt[i + 1]
        if v <= 824:
            u.add(v)
        i += 2
    return u


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, "rb")
    # ★ GMSELDT 헤더는 'ASCGSCG'를 이름하지만, 메시지 풀의 인덱스는 ASCGSCG와 맞지 않는다
    #   (ASCGSCG[284]=数인데 문장은 「…できません。」로 끝난다).
    #   ASC16CG 표로 디코드했을 때만 자연스러운 일본어가 나오므로 메시지 풀 폰트는 ASC16CG다.
    #   ASCGSCG는 타이틀/설정 메뉴용 별도 글리프 세트(兵器図鑑·難易度·登録 …).
    font_entries = all_entries("/ASC16CG")     # 같은 내용 2벌 — 둘 다 패치
    gm_lba, gm_size = index_of("/GMSELDT")
    font = bytearray(read_range(f, font_entries[0][0], font_entries[0][1]))
    gm = bytearray(read_range(f, gm_lba, gm_size))
    nglyph = len(font) // 128
    print("ASC16CG %d글리프 (엔트리 %d벌) / GMSELDT %d B"
          % (nglyph, len(font_entries), len(gm)))

    # --- 1. 필요한 음절 수집 ---
    need = []
    for _, _, s in EDITS:
        for ch in s:
            if "가" <= ch <= "힣" and ch not in need:
                need.append(ch)
    print("필요 음절 %d자: %s" % (len(need), "".join(need)))

    # --- 2. 텍스트 풀에서 안 쓰는 슬롯을 뒤에서부터 확보 ---
    used = used_indices(gm)
    free = [i for i in range(nglyph - 1, 239, -1) if i not in used]
    if len(free) < len(need):
        raise SystemExit("빈 슬롯 부족: %d < %d" % (len(free), len(need)))
    slot = {ch: free[k] for k, ch in enumerate(need)}
    print("사용 슬롯: %d ~ %d" % (min(slot.values()), max(slot.values())))

    # --- 3. 폰트에 한글 주입 ---
    for ch, idx in slot.items():
        g = to_glyph(render_bitmap(ch, FONT, FONT_PX))
        font[idx * 128:(idx + 1) * 128] = g

    # --- 4. 텍스트 레코드 교체 (length-locked) ---
    inv = {}
    for k, v in charmap.CHARS.items():
        inv.setdefault(v, k)
    for off, ln, s in EDITS:
        words = []
        for ch in s:
            if ch == "\x01":
                words.append(CTRL_FD)
            elif ch in slot:
                words.append(slot[ch])
            elif ch in inv:
                words.append(inv[ch])
            elif ch == " ":
                words.append(0)
            elif ch in ALIAS and ALIAS[ch] in inv:
                words.append(inv[ALIAS[ch]])
            else:
                raise SystemExit("인코딩 불가 문자 %r (레코드 0x%x)" % (ch, off))
        if len(words) > ln:
            raise SystemExit("길이 초과 0x%x: %d > %d  (%r)" % (off, len(words), ln, s))
        words += [0] * (ln - len(words))
        for k, w in enumerate(words):
            struct.pack_into(">H", gm, off + k * 2, w)
        print("  0x%04x  %-3d워드  %s" % (off, ln, s.replace("\x01", "⏎")))

    # --- 5. Track01 사본에 기록 ---
    os.makedirs(OUT_ISO, exist_ok=True)
    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print("\nTrack01 복사 중...")
    shutil.copyfile(TRACK1, dst)
    touched = set()
    targets = [(lba, size, font) for lba, size in font_entries]
    targets.append((gm_lba, gm_size, gm))
    with open(dst, "r+b") as w:
        for lba, size, data in targets:
            for k in range(0, size, USER):
                sec = lba + k // USER
                chunk = data[k:k + USER]
                w.seek(sec * RAW + HDR)
                w.write(chunk.ljust(USER, b"\x00")[:USER])
                touched.add(sec)
        print("변경 섹터 %d개, EDC/ECC 재계산..." % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    f.close()
    print("완료 ->", dst)
    json.dump({"slots": {c: i for c, i in slot.items()},
               "edits": [(hex(o), l, s) for o, l, s in EDITS]},
              open(os.path.join(OUT, "poc_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
