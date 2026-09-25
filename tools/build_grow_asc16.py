"""실험 3 — 전역 폰트 ASC16CG를 **필요치급으로 키울 수 있는가** (RAM 상한 측정).

세션1: ASCGSCG를 +256 확장 실기 통과. 하지만 정작 병목인 전역 ASC16CG는 로드 경로가 달라
상한을 따로 재야 한다. 이 실험은 ASC16CG를 **+675(825→1500)** 로 키우고,
★한글을 **확장 범위 맨 위(1477~1499)** 에 놓는다. 그게 렌더되면 상한 ≥1500 확정.

단일 변수: **원본 Track01에서 새로 빌드**(ASCGSCG는 원본 그대로 = 타이틀은 일본어로 복귀).
  → 이 테스트 ISO에서 화면이 갈리는 변수는 오직 ASC16CG 확장 하나.

판독(사장님 실기):
  GMDT 문자열이 뜨는 화면(장군선택/게임계속·종료/유닛상세)에 **한글** -> 상한 ≥1500 ✅
  같은 자리에 **일본어 유지** -> 그 풀이 그 화면에 안 쓰임(다른 화면 확인)
  **빈칸/깨짐** -> 늘어난 글리프가 안 실림(상한 < 1500) ❌
  **크래시/검은화면** -> 폰트 버퍼 고정(상한 존재) ❌

★ASC16CG는 디렉터리 엔트리가 2벌(lba 4108·3362) — 둘 다 새 확장본을 가리키게 갱신.
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range, read_sector
from scan_files import files
import ecc
from hangul import render_kr
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO = r"F:\hospi\roms\ss roms\aww"
OUT = os.path.join(ROOT, "build")
NEW_LBA = 259296           # 트랙 끝 여유 (세션1 재배치와 동일 위치)
NEW_N = 1500               # 목표 글리프 수 (825 -> 1500, +675)

# GMDT 안 ASC16CG 문자열 (오프셋=파일 내, ln=워드수) -> 한글
# 원문은 records() 디코드로 확인함. 여러 화면을 노려 하나는 걸리게 한다.
EDITS = [
    (0x169cc, 11, "장군을 선택하십시오"),   # 将軍を選択してください (장군 선택 화면)
    (0x25bb0,  9, "게임을 계속한다"),        # ゲームを続ける。
    (0x25bc4,  9, "게임을 종료한다"),        # ゲームを終了する。
    (0x1656a,  5, "병기타입"),               # 兵器タイプ (유닛 상세)
    (0x16576,  5, "이동타입"),               # 移動タイプ
]


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, "rb")
    hits, rlba, rsize, _ = find_dirrec(f, "ASC16CG")
    assert len(hits) == 2, "ASC16CG 엔트리 %d개(예상 2)" % len(hits)
    src_lba = hits[0][1]                       # 폰트 원본은 첫 엔트리에서 읽는다
    size = hits[0][2]
    old_n = size // 128
    assert old_n == 825, old_n
    new_size = NEW_N * 128
    nsec = (new_size + USER - 1) // USER
    print("ASC16CG %d글리프(%dB) -> %d글리프(%dB), %d섹터, lba %d"
          % (old_n, size, NEW_N, new_size, nsec, NEW_LBA))
    assert NEW_LBA + nsec <= os.path.getsize(TRACK1) // RAW, "트랙 범위 초과"

    # NEW_LBA 영역이 원본에서 비어있는지(0) 확인 — 데이터 덮어쓰기 방지
    for s in range(NEW_LBA, NEW_LBA + nsec):
        if any(read_range(f, s, USER)):
            raise SystemExit("★NEW_LBA %d 영역 비어있지 않음(sec %d) — 다른 자리 필요" % (NEW_LBA, s))

    font = bytearray(read_range(f, src_lba, size)) + bytearray((NEW_N - old_n) * 128)
    gm_lba, gm_size = [(l, s) for p, l, s in files(skip_media=False) if p == "/GMDT"][0]
    gm = bytearray(read_range(f, gm_lba, gm_size))

    # 한글은 **확장 범위 맨 위**에 배치 (상한 테스트의 핵심)
    need = []
    for _, _, s in EDITS:
        for ch in s:
            if "가" <= ch <= "힣" and ch not in need:
                need.append(ch)
    base = NEW_N - len(need)
    slot = {ch: base + k for k, ch in enumerate(need)}
    print("한글 %d자, 슬롯 %d ~ %d (확장 맨 위)" % (len(need), min(slot.values()), max(slot.values())))
    for ch, idx in slot.items():
        font[idx * 128:(idx + 1) * 128] = render_kr(ch)

    for off, ln, s in EDITS:
        words = [0 if c == " " else slot[c] for c in s]
        assert len(words) <= ln, "0x%05x: %r %d워드 > %d" % (off, s, len(words), ln)
        words += [0] * (ln - len(words))
        for k, w in enumerate(words):
            struct.pack_into(">H", gm, off + k * 2, w)
        print("  GMDT 0x%05x %2d워드  %s" % (off, ln, s))

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print("\nTrack01 복사 중...")
    shutil.copyfile(TRACK1, dst)
    touched = set()
    rd = bytearray(read_range(f, rlba, rsize))
    # ★ASC16CG 엔트리 2벌 모두 새 확장본을 가리키게
    for _, _, _, rec_off in hits:
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

    json.dump({"font": "ASC16CG", "old_lba": src_lba, "new_lba": NEW_LBA,
               "old_glyphs": old_n, "new_glyphs": NEW_N, "grow": NEW_N - old_n,
               "hangul_slots": slot, "edits": [(hex(o), l, s) for o, l, s in EDITS],
               "dir_entries": len(hits)},
              open(os.path.join(OUT, "grow_asc16_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("완료 ->", dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
