"""타이틀 화면 한글화.

대상 = /GMSELDT 의 **ASCGSCG 계열 텍스트 풀**(0x1279c~) 4개 레코드.
  ⚠️ GMSELDT 안에는 폰트가 다른 풀이 최소 2개 있다:
     - 0x0710~0x13dc : 인게임 메시지 (ASC16CG 색인). PoC에서 고쳤으나 이 화면엔 안 쓰인다.
     - 0x1279c~      : 타이틀/이름입력 (ASCGSCG 색인). ← 이번 대상
방식 = length-locked 제자리 수정. 파일 크기·오프셋 불변.
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
import ecc
from hangul import render_kr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO = r"F:\hospi\roms\ss roms\aww"
OUT = os.path.join(ROOT, "build")
FONT_TTF = r"C:\Windows\Fonts\gulim.ttc"
FONT_PX = 16

EDITS = [
    (0x1279c, 9, "캠페인 모드"),
    (0x127b0, 9, "스탠더드 모드"),
    (0x127c4, 7, "병기도감 모드"),
    (0x127d4, 7, "이어하기"),
]


def entries(path):
    out = [(lba, size) for p, lba, size in files(skip_media=False) if p == path]
    if not out:
        raise SystemExit("no file " + path)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, "rb")
    fe = entries("/ASCGSCG")
    gm_lba, gm_size = entries("/GMSELDT")[0]
    font = bytearray(read_range(f, fe[0][0], fe[0][1]))
    gm = bytearray(read_range(f, gm_lba, gm_size))
    nglyph = len(font) // 128
    print("ASCGSCG %d글리프(엔트리 %d) / GMSELDT %d B" % (nglyph, len(fe), len(gm)))

    need = []
    for _, _, s in EDITS:
        for ch in s:
            if "가" <= ch <= "힣" and ch not in need:
                need.append(ch)
    print("필요 음절 %d자: %s" % (len(need), "".join(need)))

    # --- ASCGSCG 풀 범위 자동 검출 (편집 대상을 포함하는 유효 워드 연속구간) ---
    n = len(gm) // 2
    W = lambda i: (gm[2 * i] << 8) | gm[2 * i + 1]
    i0 = EDITS[0][0] // 2
    lo, hi = i0, i0
    while lo > 0 and (W(lo - 1) <= nglyph or W(lo - 1) >= 0xFFF0):
        lo -= 1
    while hi < n and (W(hi) <= nglyph or W(hi) >= 0xFFF0):
        hi += 1
    print("ASCGSCG 풀 0x%x~0x%x (%d워드)" % (lo * 2, hi * 2, hi - lo))

    # 풀 안에서만 빈도를 센다(파일 전체 카운트는 바이너리 노이즈로 무의미).
    cnt = [0] * nglyph
    for i in range(lo, hi):
        v = W(i)
        if v < nglyph:
            cnt[v] += 1
    # 편집으로 사라질 원문 글자의 사용분은 먼저 차감
    for off, ln, _ in EDITS:
        for k in range((off - lo * 2) // 2, (off - lo * 2) // 2 + ln):
            v = W(lo + k)
            if v < nglyph:
                cnt[v] -= 1

    fm = json.load(open(os.path.join(ROOT, "work", "fontmaps.json"), encoding="utf-8"))
    gsmap = {int(k): v for k, v in fm["ASCGSCG"].items()}
    cand = sorted((c for c in range(240, nglyph)), key=lambda i: (cnt[i], -i))
    pick = cand[:len(need)]
    slot = {ch: pick[k] for k, ch in enumerate(need)}
    print("희생되는 글리프 (풀 내 사용횟수):")
    for ch in need:
        i = slot[ch]
        print("   %s <- idx %-3d %s (%d회)" % (ch, i, gsmap.get(i, "미판독"), cnt[i]))

    for ch, idx in slot.items():
        font[idx * 128:(idx + 1) * 128] = render_kr(ch)

    for off, ln, s in EDITS:
        words = []
        for ch in s:
            if ch == " ":
                words.append(0)
            elif ch in slot:
                words.append(slot[ch])
            else:
                raise SystemExit("인코딩 불가 %r" % ch)
        if len(words) > ln:
            raise SystemExit("길이 초과 0x%x: %d > %d" % (off, len(words), ln))
        words += [0] * (ln - len(words))
        for k, w in enumerate(words):
            struct.pack_into(">H", gm, off + k * 2, w)
        print("  0x%05x %2d워드  %s" % (off, ln, s))

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    if not os.path.exists(dst):
        print("\nTrack01 복사 중...")
        shutil.copyfile(TRACK1, dst)
    touched = set()
    with open(dst, "r+b") as w:
        for lba, size, data in [(fe[0][0], fe[0][1], font), (gm_lba, gm_size, gm)]:
            for k in range(0, size, USER):
                sec = lba + k // USER
                w.seek(sec * RAW + HDR)
                w.write(bytes(data[k:k + USER]).ljust(USER, b"\x00")[:USER])
                touched.add(sec)
        print("변경 섹터 %d개, EDC/ECC 재계산..." % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))
    f.close()
    json.dump({"font": "/ASCGSCG", "slots": slot,
               "edits": [(hex(o), l, s) for o, l, s in EDITS]},
              open(os.path.join(OUT, "title_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("완료 ->", dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
