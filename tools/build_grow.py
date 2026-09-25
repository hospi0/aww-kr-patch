"""실험 2 — 폰트 파일을 **키울** 수 있는가.

실험1(재배치)은 통과했다. 여기서 딱 한 가지만 더 바꾼다: **파일 크기**.

설계:
  · ASCGSCG(594글리프)를 트랙 끝으로 옮기면서 뒤에 GROW개 글리프를 덧붙인다.
  · **기존 594글리프는 원본 그대로 둔다**(한자 그대로).
  · 한글 15자는 **새로 생긴 인덱스(594~)에만** 넣는다.
  · GMSELDT 타이틀 레코드가 그 새 인덱스를 가리키게 한다.
  · ISO 루트 디렉터리의 extent(위치)와 **size(크기)** 를 함께 갱신한다.

판독:
  타이틀에 **한글**            -> 늘어난 영역까지 적재된다 = 폰트 확장 가능 ✅
  타이틀에 **한자/깨짐/공백**  -> 로더가 원본 크기만 읽는다 = 확장 불가 ❌
  **크래시/검은화면**          -> 폰트 적재 버퍼가 고정이다 (RAM 상한 존재) ❌
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range, read_sector
from scan_files import files
import ecc
from hangul import render_kr
from build_title import EDITS
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO = r"F:\hospi\roms\ss roms\aww"
OUT = os.path.join(ROOT, "build")
NEW_LBA = 259296
GROW = 256                 # 덧붙일 글리프 수 (594 -> 850)


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, "rb")
    hits, rlba, rsize, _ = find_dirrec(f, "ASCGSCG")
    assert len(hits) == 1
    _, old_lba, size, rec_off = hits[0]
    old_n = size // 128
    new_size = size + GROW * 128
    new_n = new_size // 128
    nsec = (new_size + USER - 1) // USER
    print("ASCGSCG %d글리프(%dB) -> %d글리프(%dB), %d섹터, lba %d"
          % (old_n, size, new_n, new_size, nsec, NEW_LBA))
    assert NEW_LBA + nsec <= os.path.getsize(TRACK1) // RAW, "트랙 범위 초과"

    font = bytearray(read_range(f, old_lba, size)) + bytearray(GROW * 128)
    gm_lba, gm_size = [(l, s) for p, l, s in files(skip_media=False)
                       if p == "/GMSELDT"][0]
    gm = bytearray(read_range(f, gm_lba, gm_size))

    # 한글은 새로 생긴 인덱스에만 넣는다 (기존 594글리프는 원본 유지)
    need = []
    for _, _, s in EDITS:
        for ch in s:
            if "가" <= ch <= "힣" and ch not in need:
                need.append(ch)
    slot = {ch: old_n + k for k, ch in enumerate(need)}
    print("한글 슬롯(전부 신규 영역): %d ~ %d" % (min(slot.values()), max(slot.values())))
    for ch, idx in slot.items():
        font[idx * 128:(idx + 1) * 128] = render_kr(ch)

    for off, ln, s in EDITS:
        words = [0 if c == " " else slot[c] for c in s]
        words += [0] * (ln - len(words))
        for k, w in enumerate(words):
            struct.pack_into(">H", gm, off + k * 2, w)
        print("  0x%05x %2d워드  %s" % (off, ln, s))

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print("\nTrack01 복사 중...")
    shutil.copyfile(TRACK1, dst)
    touched = set()
    rd = bytearray(read_range(f, rlba, rsize))
    struct.pack_into("<I", rd, rec_off + 2, NEW_LBA)
    struct.pack_into(">I", rd, rec_off + 6, NEW_LBA)
    struct.pack_into("<I", rd, rec_off + 10, new_size)
    struct.pack_into(">I", rd, rec_off + 14, new_size)
    f.close()

    with open(dst, "r+b") as w:
        for k in range(0, new_size, USER):
            sec = NEW_LBA + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(font[k:k + USER]).ljust(USER, b"\x00")[:USER])
            touched.add(sec)
        for k in range(0, gm_size, USER):
            sec = gm_lba + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(gm[k:k + USER]).ljust(USER, b"\x00")[:USER])
            touched.add(sec)
        for k in range(0, rsize, USER):
            sec = rlba + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(rd[k:k + USER]).ljust(USER, b"\x00")[:USER])
            touched.add(sec)
        print("변경 섹터 %d개, EDC/ECC 재계산..." % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW)
            raw = w.read(RAW)
            w.seek(sec * RAW)
            w.write(ecc.fix_sector(raw))

    json.dump({"old_lba": old_lba, "new_lba": NEW_LBA,
               "old_size": size, "new_size": new_size,
               "old_glyphs": old_n, "new_glyphs": new_n,
               "slots": slot, "edits": [(hex(o), l, s) for o, l, s in EDITS]},
              open(os.path.join(OUT, "grow_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("완료 ->", dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
