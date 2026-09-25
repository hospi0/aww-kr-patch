"""주입 스텁 검증용 초소형 SH-2 인터프리터.

스텁이 쓰는 명령만 구현한다. 지연 슬롯(bra/jmp)도 실제와 같이 처리한다.
모르는 명령을 만나면 바로 예외를 던지므로, 조용히 틀리는 일은 없다.
"""
import struct


class Mem:
    def __init__(self):
        self.regions = []                       # (base, bytearray)

    def map(self, base, data):
        self.regions.append((base, bytearray(data)))

    def _find(self, addr):
        for base, buf in self.regions:
            if base <= addr < base + len(buf):
                return buf, addr - base
        raise KeyError(f"unmapped address {addr:08x}")

    def r8(self, a):
        buf, o = self._find(a)
        return buf[o]

    def r16(self, a):
        buf, o = self._find(a)
        return struct.unpack_from(">H", buf, o)[0]

    def r32(self, a):
        buf, o = self._find(a)
        return struct.unpack_from(">I", buf, o)[0]

    def w8(self, a, v):
        buf, o = self._find(a)
        buf[o] = v & 0xFF

    def w16(self, a, v):
        buf, o = self._find(a)
        struct.pack_into(">H", buf, o, v & 0xFFFF)

    def w32(self, a, v):
        buf, o = self._find(a)
        struct.pack_into(">I", buf, o, v & 0xFFFFFFFF)


def _s8(v):
    return v - 0x100 if v & 0x80 else v


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def _s32(v):
    return v - 0x100000000 if v & 0x80000000 else v


class CPU:
    def __init__(self, mem, pc, regs=None, stack_top=0x06040000):
        self.m = mem
        self.r = [0] * 16
        self.r[15] = stack_top
        if regs:
            for k, v in regs.items():
                self.r[k] = v & 0xFFFFFFFF
        self.pc = pc
        self.t = 0
        self.macl = 0
        self.pr = 0

    def run(self, stop_pc, max_steps=2_000_000):
        steps = 0
        while self.pc != stop_pc:
            steps += 1
            if steps > max_steps:
                raise RuntimeError("runaway")
            self.step()
        return steps

    def step(self):
        w = self.m.r16(self.pc)
        pc = self.pc
        self.pc += 2
        self._exec(w, pc)

    def _delay(self, target):
        """지연 슬롯 1개를 실행한 뒤 분기."""
        w = self.m.r16(self.pc)
        slot_pc = self.pc
        self.pc += 2
        self._exec(w, slot_pc)
        self.pc = target

    def _exec(self, w, pc):
        r = self.r
        a, b, c, d = (w >> 12) & 15, (w >> 8) & 15, (w >> 4) & 15, w & 15
        imm8 = w & 0xFF

        if w == 0x0009:
            return
        if w == 0x000B:                                          # rts
            self._delay(self.pr); return
        if a == 0xE:                                            # mov #imm,Rn
            r[b] = _s8(imm8) & 0xFFFFFFFF
            return
        if a == 0x9:                                            # mov.w @(d,pc),Rn
            r[b] = _s16(self.m.r16(pc + 4 + imm8 * 2)) & 0xFFFFFFFF
            return
        if a == 0xD:                                            # mov.l @(d,pc),Rn
            r[b] = self.m.r32(((pc + 4) & ~3) + imm8 * 4)
            return
        if a == 0x6:
            if d == 0x0:
                r[b] = _s8(self.m.r8(r[c])) & 0xFFFFFFFF; return  # mov.b @Rm,Rn
            if d == 0x2:
                r[b] = self.m.r32(r[c]); return                   # mov.l @Rm,Rn
            if d == 0x3:
                r[b] = r[c]; return                               # mov Rm,Rn
            if d == 0x4:
                r[b] = _s8(self.m.r8(r[c])) & 0xFFFFFFFF
                r[c] = (r[c] + 1) & 0xFFFFFFFF; return                    # mov.b @Rm+,Rn
            if d == 0x6:
                r[b] = self.m.r32(r[c]); r[c] = (r[c] + 4) & 0xFFFFFFFF; return
            if d == 0xC:
                r[b] = r[c] & 0xFF; return                        # extu.b
            if d == 0xD:
                r[b] = r[c] & 0xFFFF; return                      # extu.w
        if a == 0x2:
            if d == 0x0:
                self.m.w8(r[b], r[c]); return                     # mov.b Rm,@Rn
            if d == 0x1:
                self.m.w16(r[b], r[c]); return                    # mov.w Rm,@Rn
            if d == 0x6:
                r[b] = (r[b] - 4) & 0xFFFFFFFF; self.m.w32(r[b], r[c]); return
            if d == 0x8:
                self.t = int((r[b] & r[c]) == 0); return          # tst
            if d == 0x9:
                r[b] &= r[c]; return
            if d == 0xB:
                r[b] |= r[c]; return
            if d == 0xE:
                self.macl = ((r[b] & 0xFFFF) * (r[c] & 0xFFFF)) & 0xFFFFFFFF; return
        if a == 0x3:
            if d == 0x0:
                self.t = int(r[b] == r[c]); return                # cmp/eq
            if d == 0x2:
                self.t = int(r[b] >= r[c]); return                # cmp/hs (unsigned)
            if d == 0x6:
                self.t = int(r[b] > r[c]); return                 # cmp/hi (unsigned)
            if d == 0x8:
                r[b] = (r[b] - r[c]) & 0xFFFFFFFF; return
            if d == 0xC:
                r[b] = (r[b] + r[c]) & 0xFFFFFFFF; return
        if a == 0x7:
            r[b] = (r[b] + _s8(imm8)) & 0xFFFFFFFF; return
        if a == 0x0 and d == 0xC:                                # mov.b @(R0,Rm),Rn
            r[b] = _s8(self.m.r8((r[0] + r[c]) & 0xFFFFFFFF)) & 0xFFFFFFFF
            return
        if a == 0x0 and d == 0xD:                                # mov.w @(R0,Rm),Rn
            r[b] = _s16(self.m.r16((r[0] + r[c]) & 0xFFFFFFFF)) & 0xFFFFFFFF
            return
        if a == 0x0 and d == 0xE:                                # mov.l @(R0,Rm),Rn
            r[b] = self.m.r32((r[0] + r[c]) & 0xFFFFFFFF)
            return
        if a == 0x0 and (w & 0xFF) == 0x1A:                      # sts macl,Rn
            r[b] = self.macl; return
        if a == 0x4:
            k = w & 0xFF
            if k == 0x00:
                self.t = (r[b] >> 31) & 1; r[b] = (r[b] << 1) & 0xFFFFFFFF; return
            if k == 0x01:
                self.t = r[b] & 1; r[b] >>= 1; return                    # shlr
            if k == 0x08:
                r[b] = (r[b] << 2) & 0xFFFFFFFF; return
            if k == 0x09:
                r[b] >>= 2; return                                       # shlr2
            if k == 0x19:
                r[b] = (r[b] >> 8) & 0xFFFFFFFF; return
            if k == 0x10:                                        # dt
                r[b] = (r[b] - 1) & 0xFFFFFFFF
                self.t = int(r[b] == 0); return
            if k == 0x11:                                        # cmp/pz
                self.t = int(_s32(r[b]) >= 0); return
            if k == 0x2B:                                        # jmp @Rn
                self._delay(r[b]); return
            if k == 0x0B:                                        # jsr @Rn
                target = r[b]
                self.pr = (pc + 4) & 0xFFFFFFFF
                self._delay(target); return
            if k == 0x22:                                        # sts.l pr,@-Rn
                r[b] = (r[b] - 4) & 0xFFFFFFFF
                self.m.w32(r[b], self.pr); return
            if k == 0x26:                                        # lds.l @Rn+,pr
                self.pr = self.m.r32(r[b])
                r[b] = (r[b] + 4) & 0xFFFFFFFF; return
            if k == 0x15:                                        # cmp/pl Rn
                self.t = int(_s32(r[b]) > 0); return
        if a == 0xC:
            if b == 0x8:
                self.t = int((r[0] & imm8) == 0); return
            if b == 0x9:
                r[0] &= imm8; return
        if a == 0x8 and b == 0x9:                                # bt
            if self.t:
                self.pc = pc + 4 + _s8(imm8) * 2
            return
        if a == 0x8 and b == 0xB:                                # bf
            if not self.t:
                self.pc = pc + 4 + _s8(imm8) * 2
            return
        if a == 0xA:                                             # bra
            disp = w & 0xFFF
            disp = disp - 4096 if disp & 0x800 else disp
            self._delay(pc + 4 + disp * 2)
            return
        raise NotImplementedError(f"opcode {w:04x} at {pc:08x}")
