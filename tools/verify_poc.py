"""빌드 산출물을 원본과 독립적으로 되읽어 검증.

1) 파일 크기/개수 불변, 변경 바이트가 의도한 범위 안에만 있는가
2) 변경 섹터의 EDC/ECC가 유효한가
3) 패치된 ASC16CG의 한글 슬롯이 실제로 한글인가 (렌더)
4) 패치된 GMSELDT 레코드가 한국어로 되읽히는가
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range, read_sector
from scan_files import files
import charmap, ecc
from hangul import glyph_to_img
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(r"F:\hospi\roms\ss roms\aww", os.path.basename(TRACK1))
PLAN = json.load(open(os.path.join(ROOT, "build", "poc_plan.json"), encoding="utf-8"))


def main():
    assert os.path.getsize(DST) == os.path.getsize(TRACK1), "이미지 크기가 변했다"
    print("✓ 이미지 크기 불변 (%d B)" % os.path.getsize(DST))

    # --- 변경 섹터 집합 ---
    changed = []
    with open(TRACK1, "rb") as a, open(DST, "rb") as b:
        n = os.path.getsize(TRACK1) // RAW
        for s in range(n):
            a.seek(s * RAW); b.seek(s * RAW)
            ra, rb = a.read(RAW), b.read(RAW)
            if ra != rb:
                changed.append(s)
    print("✓ 변경 섹터 %d개  (LBA %d ~ %d)" % (len(changed), changed[0], changed[-1]))

    # --- 변경 섹터가 대상 파일 범위 안인가 ---
    ranges = []
    for p, lba, size in files(skip_media=False):
        if p in ("/ASC16CG", "/GMSELDT"):
            ranges.append((p, lba, lba + (size + USER - 1) // USER))
    outside = [s for s in changed
               if not any(lo <= s < hi for _, lo, hi in ranges)]
    print("✓ 대상 파일(%s) 밖 변경: %d개"
          % (", ".join(sorted(set(r[0] for r in ranges))), len(outside)))
    assert not outside, "의도하지 않은 섹터가 바뀌었다: %s" % outside[:10]

    # --- EDC/ECC 유효성 ---
    bad = 0
    with open(DST, "rb") as b:
        for s in changed:
            b.seek(s * RAW)
            raw = b.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
    print("✓ EDC/ECC 유효: %d/%d 섹터" % (len(changed) - bad, len(changed)))
    assert bad == 0

    # --- 한글 글리프 되읽기 ---
    slots = {c: int(i) for c, i in PLAN["slots"].items()}
    ent = [(lba, size) for p, lba, size in files(skip_media=False) if p == "/ASC16CG"]
    with open(DST, "rb") as b:
        font = read_range(b, ent[0][0], ent[0][1])
        font2 = read_range(b, ent[1][0], ent[1][1])
    assert font == font2, "ASC16CG 두 벌이 서로 다르다 (한쪽만 패치됐다)"
    print("✓ ASC16CG 2벌 모두 동일하게 패치됨")
    items = sorted(slots.items(), key=lambda x: x[1])
    sh = Image.new("L", (len(items) * 17, 17), 40)
    for k, (ch, idx) in enumerate(items):
        sh.paste(glyph_to_img(font[idx * 128:(idx + 1) * 128]), (k * 17, 0))
    sh = sh.resize((sh.width * 5, sh.height * 5), Image.NEAREST)
    p = os.path.join(ROOT, "build", "verify_glyphs.png")
    sh.save(p)
    print("✓ 한글 슬롯 렌더 -> %s  (%s)" % (p, "".join(c for c, _ in items)))

    # --- 텍스트 되읽기 ---
    rev = {v: k for k, v in slots.items()}
    gm_lba, gm_size = [(lba, size) for p, lba, size in files(skip_media=False)
                       if p == "/GMSELDT"][0]
    with open(DST, "rb") as b:
        gm = read_range(b, gm_lba, gm_size)
    print("\n--- 패치된 레코드 되읽기 ---")
    for offs, ln, src in PLAN["edits"]:
        off = int(offs, 16)
        out = []
        for k in range(ln):
            v = struct.unpack_from(">H", gm, off + k * 2)[0]
            if v in rev:
                out.append(rev[v])
            elif v == 0xFFFD:
                out.append("⏎")
            else:
                out.append(charmap.CHARS.get(v, "〈%03x〉" % v))
        print("  0x%04x |%s|" % (off, "".join(out)))
    print("\n검증 통과")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
