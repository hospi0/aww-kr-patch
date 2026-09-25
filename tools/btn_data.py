"""전투 커맨드 버튼 한글화 — 주입 데이터(2bpp 마스크) 생성과 스텁 로직 시뮬레이션.

LWRAM 텍스처 풀은 0x002AD780부터 0x100 간격으로 42개(21라벨 x 2벌)가 늘어서 있고,
각 라벨의 B벌(첫 4바이트 ffffffff)과 A벌(00000000)은 글자 영역 원점만 (2,1)/(3,2)로
다르다. 마스크는 라벨당 1벌만 저장하고 원점은 실행 중에 첫 바이트로 판별한다.

★1bpp(잉크/판 2단계)로 만들었더니 원본 한자에 있는 중간 계조가 사라져 실기에서
  글자가 딱딱해 보였다(사용자 지적). 그래서 **2bpp 4단계**로 바꿨다.
  코드 0=판(0xb) / 1=0xa / 2=0x8 / 3=잉크(0x6).

헤더 (빅엔디안):
    +0x00 u32  magic 'KBTN'
    +0x04 u32  pool_base   (0x002AD780)
    +0x08 u16  count       (42)
    +0x0a u16  (예약)
    +0x0c u8   val[4]      2비트 코드 -> 팔레트 색인
    +0x10 u32  mask_ptr[21]  라벨별 마스크의 절대 RAM 주소, 0 = 패치 안 함
    +0x64 u32  title_src     설정 타이틀 텍스처의 LWRAM 주소(0x002B0180)
    +0x68 u32  title_ptr     타이틀 마스크 주소, 0 = 패치 안 함
헤더는 0x6c바이트. ★타이틀은 4bpp raw(원본과 같은 16단계 계조)라 색인 변환표가 없다. 버튼 마스크는 라벨당 13행 x 7바이트 = 91바이트(한 바이트에 4픽셀,
상위 2비트가 왼쪽). 절대 주소로 가리키므로 마스크는 여러 제로런에 흩어져도 된다.
★세션12에서 `設定変更` 타이틀(104x32 스프라이트)을 같은 스텁에 얹었다 — 자세한 건
  title_data.py 참조. 타이틀 마스크는 480B 연속이 필요하다(4bpp raw).
"""
import struct

try:                                    # 패키지(tools.btn_data)로도, 단독으로도 쓰인다
    from . import btn_glyph as bg
    from . import title_data as td
except ImportError:
    import btn_glyph as bg
    import title_data as td

POOL_BASE = 0x002AD780
STRIDE = 0x100
COUNT = 42
MAGIC = b"KBTN"
VAL_OFF = 0x0C
PTR_OFF = 0x10
NLABEL = 21
TSRC_OFF = PTR_OFF + NLABEL * 4         # 0x64
TPTR_OFF = TSRC_OFF + 4                 # 0x68
FIX_OFF = TPTR_OFF + 4                  # 0x6C — ★세션13-g 노이즈 보정용 영역표
#   (start, len) 빅엔디언 u32 쌍 + 0 종료. **우리가 쓴 GMDT 제로런 = 그래픽의 투명 꼬리**라
#   그 텍스처가 업로드되면 우리 바이트가 노이즈로 보인다 → 스텁이 목적지에서 그만큼 0으로 덮는다.
#   ★원본은 그 범위가 전부 0이었으니 0으로 덮는 것이 곧 원본 복원이다.
GMDT_BASE = 0x00208000
FIX_REGIONS = [(GMDT_BASE + 0x2810C, 1560), (GMDT_BASE + 0x26AD4, 464),
               (GMDT_BASE + 0x288EC, 440), (GMDT_BASE + 0x0E2D0, 400),
               (GMDT_BASE + 0x0EB3C, 405)]
#   ★run5(0x0EB3C)는 세션13-g에 추가했다 — 보정 기능이 생겼으니 그래픽 꼬리를 더 써도
#     같은 메커니즘으로 가려진다. **GMDT_RUNS와 반드시 같은 집합이어야 한다**(build_buttons가 검증).
HDR_SIZE = FIX_OFF + len(FIX_REGIONS) * 8 + 4
ROW_BYTES = 7                           # 28픽셀 / 4
MASK_SIZE = ROW_BYTES * bg.GH           # 91

# 2비트 코드 -> 팔레트 색인.
# ★진하기는 BOLDEN 하나로만 잡는다. 중간톤을 한 칸씩 어둡게(0x09/0x07) 해봤더니
#   실기에서 너무 진했다(사용자 판단) — 원래 값으로 되돌림.
LEVELS = (0x0B, 0x0A, 0x08, 0x06)

FONT = "C:/Windows/Fonts/malgunbd.ttf"
FONT_PX = 13
# 획 굵히기(4배 렌더에서 부풀린 뒤 축소). ★0.5 이상은 원본과 밀도는 맞지만
# 「설정」·「변형」·「발진」의 속공간이 막혀 못 읽는다 — 밀도 수치를 목표로 삼지 말 것.
BOLDEN = 0.25

# (라벨, 한글) — 풀 순서 그대로. None = 원문 유지(로마자라 손대지 않는다).
LABELS = [
    ("LOAD", None), ("SAVE", None), ("状況", "상황"), ("部隊", "부대"),
    ("性能", "성능"), ("上空", "상공"), ("将軍", "장군"), ("作戦", "작전"),
    ("設定", "설정"), ("終了", "종료"), ("攻撃", "공격"), ("休息", "휴식"),
    ("武装", "무장"), ("修復", "수리"), ("着陸", "착륙"), ("変型", "변형"),
    ("降下", "강하"), ("補充", "보충"), ("発進", "발진"), ("架橋", "가교"),
    ("爆撃", "폭격"),
]


def quantize(gray):
    """AA 그레이스케일 -> 2비트 코드 배열(0=판 … 3=잉크)."""
    px = gray.load()
    rows = []
    for y in range(gray.height):
        rows.append([min(3, int(round(px[x, y] / 255.0 * 3))) for x in range(gray.width)])
    return rows


def codes_to_indices(codes):
    """2비트 코드 -> 팔레트 색인(미리보기·기준 계산용)."""
    return [[LEVELS[c] for c in row] for row in codes]


def mask_bytes(codes):
    """행당 7바이트, 한 바이트에 4픽셀(상위 2비트가 왼쪽)."""
    out = bytearray()
    for row in codes:
        for i in range(ROW_BYTES):
            b = 0
            for k in range(4):
                x = i * 4 + k
                b = (b << 2) | (row[x] if x < len(row) else 0)
            out.append(b)
    return bytes(out)


def label_codes(font=FONT, px=FONT_PX, bolden=BOLDEN):
    """라벨 인덱스 -> 2비트 코드 배열."""
    out = {}
    for i, (jp, kr) in enumerate(LABELS):
        if kr is not None:
            out[i] = quantize(bg.word_gray(kr, font, px, bolden=bolden))
    return out


def build(regions, font=FONT, px=FONT_PX, bolden=BOLDEN, title=True):
    """헤더+마스크를 주어진 영역들에 배치한다.

    regions = [(이름, ram_addr, 용량)] — 앞에서부터 채운다. 첫 영역에 헤더가 들어간다.
    반환: (배치 목록 [(이름, ram_addr, bytes)], 헤더 RAM 주소, 라벨별 마스크 주소,
           타이틀 마스크 주소)
    """
    codes = label_codes(font, px, bolden)
    masks = {i: mask_bytes(c) for i, c in codes.items()}
    tmask = td.mask_bytes() if title else None

    # 1) 자리 배정 — 첫 영역 선두에 헤더
    cursors = []
    for name, addr, cap in regions:
        cursors.append([name, addr, cap, addr])          # 현재 쓰기 위치
    hdr_addr = cursors[0][3]
    cursors[0][3] += HDR_SIZE

    def alloc(size, what):
        for cur in cursors:
            _, addr, cap, pos = cur
            if pos + size <= addr + cap:
                cur[3] = pos + size
                return pos
        raise SystemExit("%s 를 넣을 자리가 없다(%d B)" % (what, size))

    # ★큰 것부터 — 480B짜리 타이틀 마스크를 먼저 잡아야 조각남으로 자리를 잃지 않는다.
    tptr = alloc(len(tmask), "타이틀 마스크") if tmask else 0
    ptr = {}
    for i in sorted(masks):
        ptr[i] = alloc(MASK_SIZE, "마스크 %d번" % i)

    # 2) 헤더 만들기
    hdr = bytearray(HDR_SIZE)
    hdr[0:4] = MAGIC
    struct.pack_into(">I", hdr, 4, POOL_BASE)
    struct.pack_into(">HH", hdr, 8, COUNT, 0)
    hdr[VAL_OFF:VAL_OFF + 4] = bytes(LEVELS)
    for i in range(NLABEL):
        struct.pack_into(">I", hdr, PTR_OFF + i * 4, ptr.get(i, 0))
    struct.pack_into(">I", hdr, TSRC_OFF, td.TEX_SRC)
    struct.pack_into(">I", hdr, TPTR_OFF, tptr)
    for i, (start, ln) in enumerate(FIX_REGIONS):          # 노이즈 보정 영역표
        struct.pack_into(">II", hdr, FIX_OFF + i * 8, start, ln)

    # 3) 영역별 바이트열로 합치기
    placed = [(p, masks[i]) for i, p in ptr.items()]
    if tmask:
        placed.append((tptr, tmask))
    blobs = []
    for (name, addr, cap), cur in zip(regions, cursors):
        buf = bytearray(cur[3] - addr)
        if addr == hdr_addr:
            buf[0:HDR_SIZE] = hdr
        for p, blob in placed:
            if addr <= p < addr + cap:
                buf[p - addr:p - addr + len(blob)] = blob
        if buf:
            blobs.append((name, addr, bytes(buf)))
    return blobs, hdr_addr, ptr, tptr


def apply_ref(tex, slot, codes):
    """스텁이 하는 일을 그대로 흉내낸다 — 텍스처 1개를 수정한 사본 반환."""
    label = slot // 2
    if label not in codes:
        return tex
    gx0, gy0 = bg.origin_of(tex)
    out = bytearray(tex)
    for y in range(bg.GH):
        for x in range(bg.GW):
            val = LEVELS[codes[label][y][x]]
            px, py = gx0 + x, gy0 + y
            i = py * 16 + px // 2
            out[i] = (out[i] & 0x0F) | (val << 4) if px % 2 == 0 else (out[i] & 0xF0) | val
    return bytes(out)
