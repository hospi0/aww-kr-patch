"""실험 3b — 전역 폰트 ASC16CG의 **RAM 성장 상한을 한 번에 좁힌다**.

세션2 실험3(build_grow_asc16, NEW_N=1500, 한글을 1477~1499에 배치)은 실기에서
장군 선택 화면의 「将軍を選択してください」자리가 **한글이 아니라 한자(秋彗星 山流銀龍二富)**로
떴다. 인덱스 순서(1477~1485)가 화면 글자와 1:1로 정확히 일치 → 그 화면은 우리 GMDT 문자열을
확실히 소비하지만, **1477~1485 슬롯이 RAM 폰트 버퍼 밖**이라 인접 메모리를 읽어 한자로 보였다.
=> 상한 < 1477 확정. 하지만 정확한 천장은 미측정(825 제자리인지, 1000/1100까지 되는지).

이 빌드: **한글 9자를 826~1474 사이 9개 층에 흩어** 심고, 장군 선택 화면의 그 문자열이
각 층을 가리키게 한다. 화면에서 **왼→오로 한글이 한자로 바뀌는 경계 = 상한.**

  · NEW_N=1500 (디렉터리는 크게 요청 — 로더가 자기 버퍼 상한까지 로드하게)
  · 한글은 아래 TIERS 슬롯에만, 나머지 신규 슬롯은 0(공백)
  · 장군 선택 문자열(0x169cc)만 패치 — 확실히 도달·소비 검증된 유일한 풀
  · 단일 변수: 원본 Track01에서 새 빌드(ASCGSCG 원본 = 타이틀 일본어 복귀)

판독(사장님 실기, 장군 선택 화면 하단 파란 글씨):
  「장 군 을 ␣ 선 택 하 십 시 오」 순서로 9칸.
  왼쪽부터 한글이다가 어느 지점부터 한자로 바뀌면 → 그 직전 층이 상한 근처.
  전부 한자    -> 상한 < 826 = **전역 폰트 성장 불가**(제자리 825칸 재활용 전략)
  전부 한글    -> 상한 >= 1474 (예상 밖, 이전 결과와 모순 — 재점검)
  중간에서 갈림 -> 두 층 사이가 상한 밴드 → 다음 빌드로 정밀화
"""
import os, sys, json, shutil, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, RAW, HDR, USER, read_range
import ecc
from hangul import render_kr
from scan_files import files
from build_reloc import find_dirrec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ISO = r"F:\hospi\roms\ss roms\aww"
OUT = os.path.join(ROOT, "build")
NEW_LBA = 259296
NEW_N = 1500

STRING = "장군을 선택하십시오"   # GMDT 0x169cc, 11워드 (将軍を選択してください)
GM_OFF, GM_LN = 0x169cc, 11
# 9개 비공백 글자를 흩어 심을 층(오름차순). 825 바로 위 ~ 1474(이전엔 1477+가 한자).
# 850(ASCGSCG 성공선)·1024·1152 등 유력 천장 주변 해상도를 높게.
# 정밀 확정: 896한글·900깨짐 확인됨 → 전이는 897~899. 895~903에 촘촘히.
# 마지막 한글 인덱스 = 천장-1, 첫 깨진 인덱스 = 천장.
TIERS = [895, 896, 897, 898, 899, 900, 901, 902, 903]


def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(TRACK1, "rb")
    hits, rlba, rsize, _ = find_dirrec(f, "ASC16CG")
    assert len(hits) == 2, "ASC16CG 엔트리 %d개(예상 2)" % len(hits)
    src_lba, size = hits[0][1], hits[0][2]
    old_n = size // 128
    assert old_n == 825, old_n
    new_size = NEW_N * 128
    nsec = (new_size + USER - 1) // USER
    print("ASC16CG %d -> %d글리프(%dB), %d섹터, lba %d" % (old_n, NEW_N, new_size, nsec, NEW_LBA))
    assert NEW_LBA + nsec <= os.path.getsize(TRACK1) // RAW, "트랙 범위 초과"
    for s in range(NEW_LBA, NEW_LBA + nsec):
        if any(read_range(f, s, USER)):
            raise SystemExit("★NEW_LBA 영역 비어있지 않음(sec %d)" % s)

    font = bytearray(read_range(f, src_lba, size)) + bytearray((NEW_N - old_n) * 128)
    gm_lba, gm_size = [(l, s) for p, l, s in files(skip_media=False) if p == "/GMDT"][0]
    gm = bytearray(read_range(f, gm_lba, gm_size))

    glyphs = [c for c in STRING if c != " "]
    assert len(glyphs) == len(TIERS), "%d글자 != %d층" % (len(glyphs), len(TIERS))
    slot = {}
    for ch, idx in zip(glyphs, TIERS):
        slot[ch] = idx
        font[idx * 128:(idx + 1) * 128] = render_kr(ch)
    print("층 배치:", "  ".join("%s@%d" % (c, i) for c, i in zip(glyphs, TIERS)))

    words = [0 if c == " " else slot[c] for c in STRING]
    assert len(words) <= GM_LN
    words += [0] * (GM_LN - len(words))
    for k, w in enumerate(words):
        struct.pack_into(">H", gm, GM_OFF + k * 2, w)
    print("GMDT 0x%05x:" % GM_OFF, words)

    dst = os.path.join(OUT_ISO, os.path.basename(TRACK1))
    print("Track01 복사 중...")
    shutil.copyfile(TRACK1, dst)
    rd = bytearray(read_range(f, rlba, rsize))
    for _, _, _, rec_off in hits:
        struct.pack_into("<I", rd, rec_off + 2, NEW_LBA)
        struct.pack_into(">I", rd, rec_off + 6, NEW_LBA)
        struct.pack_into("<I", rd, rec_off + 10, new_size)
        struct.pack_into(">I", rd, rec_off + 14, new_size)
    f.close()

    touched = set()
    with open(dst, "r+b") as w:
        for k in range(0, new_size, USER):
            sec = NEW_LBA + k // USER
            w.seek(sec * RAW + HDR); w.write(bytes(font[k:k + USER]).ljust(USER, b"\x00")[:USER]); touched.add(sec)
        for k in range(0, gm_size, USER):
            sec = gm_lba + k // USER
            w.seek(sec * RAW + HDR); w.write(bytes(gm[k:k + USER]).ljust(USER, b"\x00")[:USER]); touched.add(sec)
        for k in range(0, rsize, USER):
            sec = rlba + k // USER
            w.seek(sec * RAW + HDR); w.write(bytes(rd[k:k + USER]).ljust(USER, b"\x00")[:USER]); touched.add(sec)
        print("변경 섹터 %d개, EDC/ECC 재계산..." % len(touched))
        for sec in sorted(touched):
            w.seek(sec * RAW); raw = w.read(RAW)
            w.seek(sec * RAW); w.write(ecc.fix_sector(raw))

    json.dump({"font": "ASC16CG", "new_lba": NEW_LBA, "new_glyphs": NEW_N,
               "string": STRING, "gm_off": hex(GM_OFF), "tiers": TIERS,
               "slot": slot},
              open(os.path.join(OUT, "probe_asc16_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("완료 ->", dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
