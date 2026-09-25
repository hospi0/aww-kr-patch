"""아주 작은 SH-2 어셈블러 — 주입 스텁을 쓰기 위한 최소 명령만 지원.

라벨과 PC 상대 리터럴 풀을 다룬다. `lit_l(name)` / `lit_w(name)`으로 등록한
상수는 코드 뒤에 정렬해 배치되고 변위는 2패스로 계산한다.
"""
import struct

R = {f"r{i}": i for i in range(16)}


class Asm:
    def __init__(self, base):
        self.base = base            # 코드 첫 바이트의 RAM 주소
        self.items = []             # (kind, ...) 순서대로
        self.labels = {}
        self.lit_l = {}             # name -> u32
        self.lit_w = {}             # name -> u16

    # --- 기본 ---
    def label(self, name):
        self.items.append(("label", name))

    def w(self, code):
        self.items.append(("w", code))

    def defl(self, name, value):
        self.lit_l[name] = value

    def defw(self, name, value):
        self.lit_w[name] = value

    # --- 명령 ---
    def mov(self, m, n):        self.w(0x6003 | R[n] << 8 | R[m] << 4)
    def movi(self, i, n):       self.w(0xE000 | R[n] << 8 | (i & 0xFF))
    def add(self, m, n):        self.w(0x300C | R[n] << 8 | R[m] << 4)
    def addi(self, i, n):       self.w(0x7000 | R[n] << 8 | (i & 0xFF))
    def sub(self, m, n):        self.w(0x3008 | R[n] << 8 | R[m] << 4)
    def andr(self, m, n):       self.w(0x2009 | R[n] << 8 | R[m] << 4)
    def andi(self, i):          self.w(0xC900 | (i & 0xFF))
    def orr(self, m, n):        self.w(0x200B | R[n] << 8 | R[m] << 4)
    def tst(self, m, n):        self.w(0x2008 | R[n] << 8 | R[m] << 4)
    def cmpeq(self, m, n):      self.w(0x3000 | R[n] << 8 | R[m] << 4)
    def cmphs(self, m, n):      self.w(0x3002 | R[n] << 8 | R[m] << 4)
    def cmppz(self, n):         self.w(0x4011 | R[n] << 8)
    def shll(self, n):          self.w(0x4000 | R[n] << 8)
    def shll2(self, n):         self.w(0x4008 | R[n] << 8)
    def shlr(self, n):          self.w(0x4001 | R[n] << 8)
    def shlr2(self, n):         self.w(0x4009 | R[n] << 8)
    def shlr8(self, n):         self.w(0x4019 | R[n] << 8)
    def dt(self, n):            self.w(0x4010 | R[n] << 8)
    def extub(self, m, n):      self.w(0x600C | R[n] << 8 | R[m] << 4)
    def extuw(self, m, n):      self.w(0x600D | R[n] << 8 | R[m] << 4)
    def movb_load(self, m, n):  self.w(0x6000 | R[n] << 8 | R[m] << 4)
    def movb_store(self, m, n): self.w(0x2000 | R[n] << 8 | R[m] << 4)
    def movl_load(self, m, n):  self.w(0x6002 | R[n] << 8 | R[m] << 4)
    def movl_postinc(self, m, n): self.w(0x6006 | R[n] << 8 | R[m] << 4)
    def movl_predec(self, m, n):  self.w(0x2006 | R[n] << 8 | R[m] << 4)
    def movb_r0m(self, m, n):   self.w(0x000C | R[n] << 8 | R[m] << 4)   # mov.b @(R0,Rm),Rn
    def movw_r0m(self, m, n):   self.w(0x000D | R[n] << 8 | R[m] << 4)   # mov.w @(R0,Rm),Rn
    def movl_r0m(self, m, n):   self.w(0x000E | R[n] << 8 | R[m] << 4)   # mov.l @(R0,Rm),Rn
    def movb_postinc(self, m, n): self.w(0x6004 | R[n] << 8 | R[m] << 4)
    def muluw(self, m, n):      self.w(0x200E | R[n] << 8 | R[m] << 4)
    def sts_macl(self, n):      self.w(0x001A | R[n] << 8)
    def jmp(self, n):           self.w(0x402B | R[n] << 8)
    def jsr(self, n):           self.w(0x400B | R[n] << 8)
    def rts(self):              self.w(0x000B)
    def stspr_predec(self, n):  self.w(0x4022 | R[n] << 8)   # sts.l pr,@-Rn
    def ldspr_postinc(self, n): self.w(0x4026 | R[n] << 8)   # lds.l @Rn+,pr
    def cmppl(self, n):         self.w(0x4015 | R[n] << 8)   # cmp/pl Rn (>0, signed)
    def cmphi(self, m, n):      self.w(0x3006 | R[n] << 8 | R[m] << 4)  # T = Rn > Rm (unsigned)
    def movw_store(self, m, n): self.w(0x2001 | R[n] << 8 | R[m] << 4)  # mov.w Rm,@Rn
    def nop(self):              self.w(0x0009)

    # 분기/PC 상대 로드는 2패스가 필요하다
    def bt(self, lab):          self.items.append(("bt", lab))
    def bf(self, lab):          self.items.append(("bf", lab))
    def bra(self, lab):         self.items.append(("bra", lab))
    def movl_pc(self, name, n): self.items.append(("movl_pc", name, R[n]))
    def movw_pc(self, name, n): self.items.append(("movw_pc", name, R[n]))

    # --- 조립 ---
    def assemble(self):
        # 1패스: 주소 배정
        addr, layout = self.base, []
        for it in self.items:
            if it[0] == "label":
                self.labels[it[1]] = addr
                continue
            layout.append((addr, it))
            addr += 2
        code_end = addr

        wpool = {}                                  # name -> addr
        for name in self.lit_w:
            wpool[name] = addr
            addr += 2
        if addr % 4:
            addr += 2
        lpool = {}
        for name in self.lit_l:
            lpool[name] = addr
            addr += 4
        total = addr - self.base

        out = bytearray(total)

        def put(a, val, size):
            o = a - self.base
            struct.pack_into(">I" if size == 4 else ">H", out, o, val)

        for a, it in layout:
            k = it[0]
            if k == "w":
                put(a, it[1], 2)
            elif k in ("bt", "bf", "bra"):
                tgt = self.labels[it[1]]
                d = (tgt - (a + 4)) // 2
                if k == "bra":
                    assert -2048 <= d < 2048, it
                    put(a, 0xA000 | (d & 0xFFF), 2)
                else:
                    assert -128 <= d < 128, (it, d)
                    put(a, (0x8900 if k == "bt" else 0x8B00) | (d & 0xFF), 2)
            elif k == "movl_pc":
                tgt = lpool[it[1]]
                d = (tgt - ((a + 4) & ~3)) // 4
                assert 0 <= d < 256, (it, d)
                put(a, 0xD000 | it[2] << 8 | d, 2)
            elif k == "movw_pc":
                tgt = wpool[it[1]]
                d = (tgt - (a + 4)) // 2
                assert 0 <= d < 256, (it, d)
                put(a, 0x9000 | it[2] << 8 | d, 2)

        for name, a in wpool.items():
            put(a, self.lit_w[name] & 0xFFFF, 2)
        for name, a in lpool.items():
            put(a, self.lit_l[name] & 0xFFFFFFFF, 4)
        return bytes(out), code_end - self.base
