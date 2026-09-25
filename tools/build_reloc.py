"""실험 1 — 폰트 파일을 옮길 수 있는가 (ISO 디렉터리를 로더가 읽는가).

설계(이분 실험, 변수 하나):
  · ASCGSCG를 데이터 트랙 끝 빈 섹터로 **크기 그대로** 복사한다.
  · **옮긴 사본에만 한글 글리프를 넣는다.**
  · **원래 자리(lba 3434)는 원본 일본어 그대로 둔다.**
  · ISO 루트 디렉터리의 /ASCGSCG 레코드 extent만 새 위치로 갱신한다(LE·BE 둘 다).
  · GMSELDT의 타이틀 레코드는 한국어 인덱스를 유지한다.

판독:
  타이틀에 **한글**이 보이면  -> 로더가 ISO 디렉터리를 읽는다 = 재배치 가능 ✅
  타이틀에 **한자/깨짐**이 보이면 -> 로더가 LBA를 하드코딩한다 = 재배치 불가 ❌
  (원본 폰트의 해당 슬롯은 兵器図鑑·司令·蔵·抗 … 이라 한글과 확연히 다르다)
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range, read_sector
from scan_files import files
import ecc
from hangul import render_kr
from build_title import EDITS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO = r"F:\hospi\roms\ss roms\aww"
OUT = os.path.join(ROOT, "build")
NEW_LBA = 259296          # 마지막 파일 끝(259289) 뒤 여유 구간


def find_dirrec(f, name):
    """루트 디렉터리에서 name 레코드의 (절대 바이트 오프셋, lba, size)."""
    pvd = read_sector(f, 16)
    rlba = struct.unpack_from("<I", pvd, 156 + 2)[0]
    rsize = struct.unpack_from("<I", pvd, 156 + 10)[0]
    data = read_range(f, rlba, rsize)
    off = 0
    hits = []
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
            lba = struct.unpack_from("<I", data, off + 2)[0]
            size = struct.unpack_from("<I", data, off + 10)[0]
            hits.append((rlba * USER + off, lba, size, off))
        off += ln
    return hits, rlba, rsize, data


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, "rb")
    hits, rlba, rsize, rdata = find_dirrec(f, "ASCGSCG")
    if len(hits) != 1:
        raise SystemExit("ASCGSCG 디렉터리 레코드가 %d개 — 예상과 다르다" % len(hits))
    _, old_lba, size, rec_off = hits[0]
    nsec = (size + USER - 1) // USER
    print("ASCGSCG  lba=%d size=%d (%d섹터)  ->  새 lba=%d"
          % (old_lba, size, nsec, NEW_LBA))
    if NEW_LBA + nsec > os.path.getsize(TRACK1) // RAW:
        raise SystemExit("트랙 범위 초과")

    font = bytearray(read_range(f, old_lba, size))
    gm_lba, gm_size = [(l, s) for p, l, s in files(skip_media=False)
                       if p == "/GMSELDT"][0]
    gm = bytearray(read_range(f, gm_lba, gm_size))

    # --- 한글 슬롯 계산 (build_title과 동일 규칙) ---
    nglyph = len(font) // 128
    need = []
    for _, _, s in EDITS:
        for ch in s:
            if "가" <= ch <= "힣" and ch not in need:
                need.append(ch)
    n = len(gm) // 2
    W = lambda i: (gm[2 * i] << 8) | gm[2 * i + 1]
    i0 = EDITS[0][0] // 2
    lo, hi = i0, i0
    while lo > 0 and (W(lo - 1) <= nglyph or W(lo - 1) >= 0xFFF0):
        lo -= 1
    while hi < n and (W(hi) <= nglyph or W(hi) >= 0xFFF0):
        hi += 1
    cnt = [0] * nglyph
    for i in range(lo, hi):
        v = W(i)
        if v < nglyph:
            cnt[v] += 1
    for off, ln, _ in EDITS:
        for k in range((off - lo * 2) // 2, (off - lo * 2) // 2 + ln):
            v = W(lo + k)
            if v < nglyph:
                cnt[v] -= 1
    pick = sorted(range(240, nglyph), key=lambda i: (cnt[i], -i))[:len(need)]
    slot = {ch: pick[k] for k, ch in enumerate(need)}
    print("한글 슬롯 %d개: %s" % (len(slot), sorted(slot.values())))

    for ch, idx in slot.items():
        font[idx * 128:(idx + 1) * 128] = render_kr(ch)

    for off, ln, s in EDITS:
        words = [0 if c == " " else slot[c] for c in s]
        words += [0] * (ln - len(words))
        for k, w in enumerate(words):
            struct.pack_into(">H", gm, off + k * 2, w)

    # --- 이미지 작성 ---
    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print("\nTrack01 복사 중...")
    shutil.copyfile(TRACK1, dst)
    touched = set()
    with open(dst, "r+b") as w:
        # 1) 새 위치에 한글 폰트
        for k in range(0, size, USER):
            sec = NEW_LBA + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(font[k:k + USER]).ljust(USER, b"\x00")[:USER])
            touched.add(sec)
        # 2) GMSELDT 한국어 레코드
        for k in range(0, gm_size, USER):
            sec = gm_lba + k // USER
            w.seek(sec * RAW + HDR)
            w.write(bytes(gm[k:k + USER]).ljust(USER, b"\x00")[:USER])
            touched.add(sec)
        # 3) 루트 디렉터리 레코드의 extent 를 새 lba 로 (LE + BE 양쪽)
        rd = bytearray(read_range(open(TRACK1, "rb"), rlba, rsize))
        struct.pack_into("<I", rd, rec_off + 2, NEW_LBA)
        struct.pack_into(">I", rd, rec_off + 6, NEW_LBA)
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
    f.close()
    json.dump({"old_lba": old_lba, "new_lba": NEW_LBA, "size": size,
               "slots": slot, "edits": [(hex(o), l, s) for o, l, s in EDITS]},
              open(os.path.join(OUT, "reloc_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("완료 ->", dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
