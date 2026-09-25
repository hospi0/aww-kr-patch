"""타이틀 패치 독립 검증 (패치된 이미지만 읽어서 확인)."""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
from scan_files import files
import ecc
from hangul import glyph_to_img
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(r"F:\hospi\roms\ss roms\aww", os.path.basename(TRACK1))
PLAN = json.load(open(os.path.join(ROOT, "build", "title_plan.json"), encoding="utf-8"))


def main():
    assert os.path.getsize(DST) == os.path.getsize(TRACK1)
    print("✓ 이미지 크기 불변 (%d B)" % os.path.getsize(DST))

    changed = []
    with open(TRACK1, "rb") as a, open(DST, "rb") as b:
        for s in range(os.path.getsize(TRACK1) // RAW):
            a.seek(s * RAW); b.seek(s * RAW)
            if a.read(RAW) != b.read(RAW):
                changed.append(s)
    print("✓ 변경 섹터 %d개 (LBA %d~%d)" % (len(changed), changed[0], changed[-1]))

    rng = [(p, lba, lba + (size + USER - 1) // USER)
           for p, lba, size in files(skip_media=False) if p in ("/ASCGSCG", "/GMSELDT")]
    outside = [s for s in changed if not any(lo <= s < hi for _, lo, hi in rng)]
    print("✓ 대상 파일 밖 변경: %d개" % len(outside))
    assert not outside, outside[:10]

    bad = 0
    with open(DST, "rb") as b:
        for s in changed:
            b.seek(s * RAW)
            raw = b.read(RAW)
            if ecc.fix_sector(raw) != raw:
                bad += 1
    print("✓ EDC/ECC 유효 %d/%d" % (len(changed) - bad, len(changed)))
    assert bad == 0

    slots = {c: int(i) for c, i in PLAN["slots"].items()}
    fl, fs = [(lba, size) for p, lba, size in files(skip_media=False)
              if p == "/ASCGSCG"][0]
    gl, gs = [(lba, size) for p, lba, size in files(skip_media=False)
              if p == "/GMSELDT"][0]
    with open(DST, "rb") as b:
        font = read_range(b, fl, fs)
        gm = read_range(b, gl, gs)

    items = sorted(slots.items(), key=lambda x: x[1])
    sh = Image.new("L", (len(items) * 17, 17), 40)
    for k, (ch, idx) in enumerate(items):
        sh.paste(glyph_to_img(font[idx * 128:(idx + 1) * 128]), (k * 17, 0))
    sh = sh.resize((sh.width * 5, sh.height * 5), Image.NEAREST)
    p = os.path.join(ROOT, "build", "verify_title_glyphs.png")
    sh.save(p)
    print("✓ 글리프 렌더 -> %s (%s)" % (p, "".join(c for c, _ in items)))

    rev = {v: k for k, v in slots.items()}
    print("\n--- 레코드 되읽기 ---")
    for offs, ln, src in PLAN["edits"]:
        off = int(offs, 16)
        out = []
        for k in range(ln):
            v = struct.unpack_from(">H", gm, off + k * 2)[0]
            out.append(rev.get(v, " " if v == 0 else "〈%03x〉" % v))
        print("  0x%05x |%s|" % (off, "".join(out)))
    print("\n검증 통과")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
