"""전투 커맨드 버튼 한글화 — 주입 코드(SH-2).

텍스처 업로더가 쓰는 memmove 리터럴(@0x06017778)을 트램폴린으로 바꿔 가로챈다.

  트램폴린 (모듈0, 항상 상주)  — 데이터 매직을 확인해서
      맞으면 → 본체 스텁(GMDT 안)으로 점프
      아니면 → 원본 memmove로 점프 (GMDT가 안 올라온 화면에서 안전)
  본체 스텁 (GMDT)             — 소스가 버튼 텍스처 풀 안이면 그 자리에서 글자 영역을
      2bpp 마스크로 덮고 원본 memmove로 꼬리 점프한다.

★본체를 GMDT로 옮긴 이유: 2bpp로 바꾸면서 코드가 커져 모듈0 제로런(230B)에 안 들어간다.
★배치 순서는 [본체 코드][매직 헤더][마스크] — 매직이 코드 뒤에 있으므로, 파일을 앞에서부터
  적재하는 한 "매직이 보이면 코드도 이미 올라와 있다"가 성립한다.
★세션12: 같은 스텁이 **설정 메뉴 타이틀(`設定変更`, 104x32 스프라이트)** 도 처리한다.
  관문은 크기가 아니라 **소스 주소 일치(0x002B0180)** 하나 — 통째로 복사하든 나눠 복사하든
  소스를 제자리로 칠하므로 결과가 같고, 멱등이다.
"""
try:                                    # 패키지로도, 단독으로도 쓰인다
    from .sh2asm import Asm
    from . import btn_data as bd
    from . import btn_glyph as bg
    from . import title_data as td
except ImportError:
    from sh2asm import Asm
    import btn_data as bd
    import btn_glyph as bg
    import title_data as td

MEMMOVE = 0x06011C24            # 원본 범용 복사 루틴
LITERAL_ADDR = 0x06017778       # 업로더가 읽는 memmove 포인터(여기를 트램폴린으로)

SAVED = ("r8", "r9", "r10", "r11", "r12", "r13", "r14")
SAVED_T = ("r8", "r9", "r10")                   # 타이틀 경로가 쓰는 콜리 저장 레지스터


def build_tramp(tramp_addr, hdr_addr, stub_addr):
    a = Asm(tramp_addr)
    a.defl("HDRP", hdr_addr)
    a.defl("MAGIC", int.from_bytes(bd.MAGIC, "big"))
    a.defl("STUB", stub_addr)
    a.defl("MEMMOVE", MEMMOVE)
    a.movl_pc("HDRP", "r0")
    a.movl_load("r0", "r1")
    a.movl_pc("MAGIC", "r2")
    a.cmpeq("r2", "r1")
    a.bf("pass")
    a.movl_pc("STUB", "r0")
    a.jmp("r0")
    a.nop()
    a.label("pass")
    a.movl_pc("MEMMOVE", "r0")
    a.jmp("r0")
    a.nop()
    return a.assemble()


def build_stub(stub_addr, hdr_addr):
    a = Asm(stub_addr)
    a.defw("N100", 0x0100)
    a.defw("LIMIT", bd.COUNT * bd.STRIDE)        # 0x2a00
    a.defw("TFIRST", td.FIRST_OFF)               # 425 = 덧칠 첫 행의 텍스처 내 오프셋
    a.defl("POOLB", bd.POOL_BASE)
    a.defl("HDRP", hdr_addr)
    a.defl("MEMMOVE", MEMMOVE)

    # --- 관문 F: 소스가 **우리 데이터 영역**과 겹치나 (세션13-g 노이즈 보정) ---
    # ★우리가 쓴 GMDT 제로런은 실은 그래픽의 투명 꼬리다. 그 텍스처가 업로드되면 우리 바이트가
    #   화면에 노이즈로 뜬다(이동범위 오버레이·상황판). ⇒ 겹치면 **원본 memmove를 호출한 뒤
    #   목적지에서 그 범위만 0으로 덮는다**(원본이 0이었으므로 이는 원본 복원과 같다).
    a.movl_pc("HDRP", "r1")
    a.movi(bd.FIX_OFF, "r0")
    a.add("r0", "r1")                            # r1 = 영역표
    a.label("fix_scan")
    a.movl_postinc("r1", "r2")                   # r2 = start (0이면 끝)
    a.tst("r2", "r2")
    a.bt("fix_none")
    a.movl_postinc("r1", "r3")                   # r3 = len
    a.mov("r2", "r0")
    a.add("r3", "r0")                            # r0 = start+len
    a.cmphs("r0", "r5")                          # src >= start+len ?
    a.bt("fix_scan")
    a.mov("r5", "r0")
    a.add("r6", "r0")                            # r0 = src+size
    a.cmphi("r2", "r0")                          # src+size > start ?
    a.bf("fix_scan")
    a.bra("fix_do")
    a.nop()
    a.label("fix_none")

    # --- 관문 0: 설정 타이틀 텍스처인가 (소스 주소 일치) ---
    # ★타이틀 본체는 코드 맨 뒤에 둔다. bt/bf는 ±256B라 여기서 바로 못 뛰므로
    #   "아니면 건너뛰기 + bra"로 뒤집었다(bra는 ±4KB).
    a.movl_pc("HDRP", "r1")
    a.movi(bd.TSRC_OFF, "r0")
    a.movl_r0m("r1", "r2")                       # r2 = title_src
    a.cmpeq("r2", "r5")
    a.bf("notitle")
    a.bra("title")
    a.nop()
    a.label("notitle")

    # --- 관문 1: 크기가 텍스처 한 장(0x100)인가 ---
    a.movw_pc("N100", "r0")
    a.cmpeq("r0", "r6")
    a.bf("passthru")

    # --- 관문 2: 소스가 버튼 풀 안이고 0x100 경계인가 ---
    a.movl_pc("POOLB", "r1")
    a.mov("r5", "r2")
    a.sub("r1", "r2")                            # r2 = delta
    a.cmppz("r2")
    a.bf("passthru")
    a.mov("r2", "r0")
    a.andi(0xFF)
    a.tst("r0", "r0")
    a.bf("passthru")
    a.movw_pc("LIMIT", "r0")
    a.cmphs("r0", "r2")
    a.bt("passthru")

    # --- 관문 3: 이 라벨에 마스크가 있는가 ---
    a.movl_pc("HDRP", "r1")
    a.shlr8("r2")                                # r2 = slot
    a.shlr("r2")                                 # r2 = label (슬롯 2개가 한 라벨)
    a.mov("r2", "r0")
    a.shll2("r0")
    a.addi(bd.PTR_OFF, "r0")
    a.movl_r0m("r1", "r3")                       # r3 = mask_ptr[label]
    a.tst("r3", "r3")
    a.bt("passthru")

    # --- 여기서부터 실제 작업. 콜리 저장 레지스터를 쓰므로 퇴피 ---
    for r in SAVED:
        a.movl_predec(r, "r15")

    a.mov("r3", "r12")                           # r12 = 마스크 포인터
    a.mov("r1", "r13")
    a.addi(bd.VAL_OFF, "r13")                    # r13 = 2비트 코드 -> 색인 표

    # 배치 판별: 첫 바이트가 0이면 A(3,2), 아니면 B(2,1)
    a.movb_load("r5", "r0")
    a.tst("r0", "r0")
    a.bt("origin_a")
    a.movi(bg.ORIGIN_B[0], "r10")                # gx0
    a.movi(bg.ORIGIN_B[1], "r11")                # gy0
    a.bra("origin_done")
    a.nop()
    a.label("origin_a")
    a.movi(bg.ORIGIN_A[0], "r10")
    a.movi(bg.ORIGIN_A[1], "r11")
    a.label("origin_done")

    # r8 = 첫 행의 바이트 주소 = src + gy0*16 + (gx0>>1)   (gx0>>1은 2든 3이든 1)
    a.mov("r11", "r0")
    a.shll2("r0")
    a.shll2("r0")
    a.mov("r5", "r8")
    a.add("r0", "r8")
    a.addi(1, "r8")
    a.movi(bg.GH, "r9")                          # 남은 행 수

    a.label("row_loop")
    a.mov("r8", "r3")                            # r3 = 쓰는 바이트 주소
    a.mov("r10", "r0")
    a.andi(1)
    a.mov("r0", "r11")                           # r11 = 니블 위치(0=상위)
    a.movi(bd.ROW_BYTES, "r2")                   # 이 행의 마스크 바이트 수

    a.label("byte_loop")
    a.movb_postinc("r12", "r7")
    a.extub("r7", "r7")
    a.movi(4, "r14")                             # 바이트당 4픽셀

    a.label("px_loop")
    a.mov("r7", "r0")
    a.shlr2("r0")
    a.shlr2("r0")
    a.shlr2("r0")                                # r0 = 상위 2비트 코드
    a.movb_r0m("r13", "r1")                      # r1 = 팔레트 색인
    a.extub("r1", "r1")
    a.movb_load("r3", "r0")
    a.extub("r0", "r0")
    a.tst("r11", "r11")
    a.bf("lo_nibble")
    a.andi(0x0F)
    a.shll2("r1")
    a.shll2("r1")
    a.orr("r1", "r0")
    a.bra("wrote")
    a.nop()
    a.label("lo_nibble")
    a.andi(0xF0)
    a.orr("r1", "r0")
    a.label("wrote")
    a.movb_store("r0", "r3")
    a.shll2("r7")                                # 다음 픽셀로
    a.mov("r7", "r0")
    a.andi(0xFF)
    a.mov("r0", "r7")
    a.tst("r11", "r11")
    a.bt("was_hi")
    a.movi(0, "r11")                             # 하위였으면 다음은 상위 + 바이트 전진
    a.addi(1, "r3")
    a.bra("px_next")
    a.nop()
    a.label("was_hi")
    a.movi(1, "r11")
    a.label("px_next")
    a.dt("r14")
    a.bf("px_loop")
    a.dt("r2")
    a.bf("byte_loop")

    a.addi(16, "r8")                             # 다음 행
    a.dt("r9")
    a.bf("row_loop")

    for r in reversed(SAVED):
        a.movl_postinc("r15", r)

    a.label("passthru")
    a.movl_pc("MEMMOVE", "r0")
    a.jmp("r0")
    a.nop()

    # --- 보정 경로: memmove 호출 → 목적지에서 우리 영역만 0으로 → 복귀 ---
    #   스택 프레임: [pr][r4][r5][r6] 을 쌓고, 호출 뒤 반환값 r0 을 그 위에 쌓는다.
    #   인자는 pop 하지 않고 @(disp,r15) 로 읽어 프레임을 유지한다(반환 직전에 정리).
    a.label("fix_do")
    a.stspr_predec("r15")
    a.movl_predec("r4", "r15")
    a.movl_predec("r5", "r15")
    a.movl_predec("r6", "r15")
    a.movl_pc("MEMMOVE", "r0")
    a.jsr("r0")
    a.nop()
    a.movl_predec("r0", "r15")                   # 반환값 보존
    a.movi(4, "r0")
    a.movl_r0m("r15", "r6")                      # r6 = size
    a.movi(8, "r0")
    a.movl_r0m("r15", "r5")                      # r5 = src
    a.movi(12, "r0")
    a.movl_r0m("r15", "r4")                      # r4 = dst
    a.movl_pc("HDRP", "r1")
    a.movi(bd.FIX_OFF, "r0")
    a.add("r0", "r1")
    a.label("z_scan")
    a.movl_postinc("r1", "r2")                   # start
    a.tst("r2", "r2")
    a.bt("z_done")
    a.movl_postinc("r1", "r3")                   # len
    a.mov("r5", "r0")                            # ovl_start = max(src, start)
    a.cmphs("r2", "r0")
    a.bt("z_s")
    a.mov("r2", "r0")
    a.label("z_s")
    a.mov("r5", "r7")                            # ovl_end = min(src+size, start+len)
    a.add("r6", "r7")
    a.add("r2", "r3")                            # r3 = start+len
    a.cmphs("r3", "r7")
    a.bf("z_e")
    a.mov("r3", "r7")
    a.label("z_e")
    a.sub("r0", "r7")                            # r7 = count
    a.cmppl("r7")
    a.bf("z_scan")
    a.sub("r5", "r0")                            # r0 = dst 오프셋
    a.mov("r4", "r3")
    a.add("r0", "r3")                            # r3 = 쓸 주소
    a.shlr("r7")                                 # 워드 수 (VDP1은 바이트 접근을 피한다)
    a.label("z_loop")
    a.movi(0, "r0")
    a.movw_store("r0", "r3")
    a.addi(2, "r3")
    a.dt("r7")
    a.bf("z_loop")
    a.bra("z_scan")
    a.nop()
    a.label("z_done")
    a.movl_postinc("r15", "r0")                  # 반환값 복원
    a.addi(12, "r15")                            # r6,r5,r4 슬롯 버림
    a.ldspr_postinc("r15")
    a.rts()
    a.nop()

    # ---------------- 설정 타이틀(104x32) 덧칠 ----------------
    # 덧칠 원점이 짝수 픽셀이라 마스크가 곧 4bpp 픽셀이다 — 행당 32바이트를 그대로 복사한다.
    # (버튼 쪽 2bpp 언팩·니블 정렬이 전혀 필요 없다. 원본과 같은 16단계 계조를 그대로 싣는다.)
    # ⚠️쓰기 주소가 홀수(src+425)라 롱워드 복사는 못 쓴다 — 바이트 복사여야 한다.
    a.label("title")
    a.movl_pc("HDRP", "r1")
    a.movi(bd.TPTR_OFF, "r0")
    a.movl_r0m("r1", "r3")                       # r3 = 타이틀 마스크 포인터
    a.tst("r3", "r3")
    a.bt("passthru")                             # 마스크 없음 = 패치 안 함

    for r in SAVED_T:
        a.movl_predec(r, "r15")

    a.mov("r5", "r8")
    a.movw_pc("TFIRST", "r0")
    a.add("r0", "r8")                            # r8 = 첫 행의 쓰기 주소
    a.movi(td.PH, "r9")                          # 남은 행 수

    a.label("trow")
    a.mov("r8", "r10")                           # r10 = 이 행의 쓰기 포인터
    a.movi(td.ROW_BYTES, "r7")                   # 행당 바이트 수

    a.label("tbyte")
    a.movb_postinc("r3", "r1")
    a.movb_store("r1", "r10")
    a.addi(1, "r10")
    a.dt("r7")
    a.bf("tbyte")

    a.addi(td.ROW, "r8")                         # 다음 행
    a.dt("r9")
    a.bf("trow")

    for r in reversed(SAVED_T):
        a.movl_postinc("r15", r)
    a.bra("passthru")
    a.nop()
    return a.assemble()
