"""재배치 실험 이미지 독립 검증.

확인 항목
 1) 이미지 크기 불변
 2) ISO를 새로 파싱했을 때 /ASCGSCG 가 새 lba 를 가리키는가
 3) 새 위치에 한글이 들어간 폰트가, 원래 위치에는 **원본 그대로**가 있는가
 4) 변경 섹터가 (새위치 / GMSELDT / 루트디렉터리) 안에만 있는가
 5) 변경 섹터 EDC/ECC 유효
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range, read_sector
import ecc
from hangul import glyph_to_img
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(r"F:\hospi\roms\ss roms\aww", os.path.basename(TRACK1))
PLAN = json.load(open(os.path.join(ROOT, "build", "reloc_plan.json"), encoding="utf-8"))


def root_lookup(f, name):
    pvd = read_sector(f, 16)
    rlba = struct.unpack_from("<I", pvd, 156 + 2)[0]
    rsize = struct.unpack_from("<I", pvd, 156 + 10)[0]
    data = read_range(f, rlba, rsize)
    off = 0
    out = []
    while off < len(data):
        ln = data[off]
        if ln == 0:
            off = (off // USER + 1) * USER
            if off >= len(data):
                break
            continue
        nlen = data[off + 32]
        nm = data[off + 33:off + 33 + nlen].split(b";")[0]
        if nm == name.encode():
            le = struct.unpack_from("<I", data, off + 2)[0]
            be = struct.unpack_from(">I", data, off + 6)[0]
            sz = struct.unpack_from("<I", data, off + 10)[0]
            out.append((le, be, sz))
        off += ln
    return out, rlba, rsize


def main():
    assert os.path.getsize(DST) == os.path.getsize(TRACK1)
    print("✓ 이미지 크기 불변")

    with open(DST, "rb") as b:
        recs, rlba, rsize = root_lookup(b, "ASCGSCG")
        assert len(recs) == 1, recs
        le, be, sz = recs[0]
        print("✓ ISO 재파싱: /ASCGSCG lba(LE)=%d lba(BE)=%d size=%d" % (le, be, sz))
        assert le == be == PLAN["new_lba"], "extent 갱신 실패"
        assert sz == PLAN["size"], "size가 바뀌었다"
        new_font = read_range(b, PLAN["new_lba"], sz)
        old_font = read_range(b, PLAN["old_lba"], sz)
    with open(TRACK1, "rb") as a:
        orig = read_range(a, PLAN["old_lba"], sz)

    assert old_font == orig, "원래 위치가 변조됐다 (실험이 모호해진다)"
    print("✓ 원래 위치(lba %d)는 원본 그대로" % PLAN["old_lba"])
    assert new_font != orig, "새 위치가 원본과 같다 (한글이 안 들어갔다)"
    print("✓ 새 위치(lba %d)는 한글 주입본" % PLAN["new_lba"])

    slots = {c: int(i) for c, i in PLAN["slots"].items()}
    items = sorted(slots.items(), key=lambda x: x[1])
    sh = Image.new("L", (len(items) * 2 * 17, 17), 40)
    for k, (ch, idx) in enumerate(items):
        sh.paste(glyph_to_img(new_font[idx * 128:(idx + 1) * 128]), (k * 17, 0))
    for k, (ch, idx) in enumerate(items):
        sh.paste(glyph_to_img(orig[idx * 128:(idx + 1) * 128]),
                 ((len(items) + k) * 17, 0))
    sh = sh.resize((sh.width * 4, sh.height * 4), Image.NEAREST)
    p = os.path.join(ROOT, "build", "verify_reloc.png")
    sh.save(p)
    print("✓ 좌=새위치(한글) 우=원래위치(원본한자) -> %s" % p)

    changed = []
    with open(TRACK1, "rb") as a, open(DST, "rb") as b:
        for s in range(os.path.getsize(TRACK1) // RAW):
            a.seek(s * RAW); b.seek(s * RAW)
            if a.read(RAW) != b.read(RAW):
                changed.append(s)
    nsec = (sz + USER - 1) // USER
    ok_ranges = [(PLAN["new_lba"], PLAN["new_lba"] + nsec), (rlba, rlba + 5)]
    from scan_files import files
    for p2, l2, s2 in files(skip_media=False):
        if p2 == "/GMSELDT":
            ok_ranges.append((l2, l2 + (s2 + USER - 1) // USER))
    outside = [s for s in changed if not any(a <= s < b2 for a, b2 in ok_ranges)]
    print("✓ 변경 섹터 %d개, 예상 범위 밖 %d개" % (len(changed), len(outside)))
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
    print("\n검증 통과")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
