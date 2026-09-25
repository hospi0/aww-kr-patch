"""Minimal SH-2 (big-endian) disassembler — enough to read loader/copy routines.

Unknown opcodes print as `.word`. Only the forms this project actually needs are
decoded; PC-relative loads resolve their literal target and value.
"""
import struct
import sys


def _r(n):
    return f"r{n}"


def disasm_one(code, off, base):
    """Return (text, extra) for the instruction at `off`. base = RAM address of code[0]."""
    w = struct.unpack_from(">H", code, off)[0]
    pc = base + off
    a, b, c, d = (w >> 12) & 15, (w >> 8) & 15, (w >> 4) & 15, w & 15
    imm8 = w & 0xFF
    simm8 = imm8 - 256 if imm8 & 0x80 else imm8
    disp12 = w & 0xFFF
    sdisp12 = disp12 - 4096 if disp12 & 0x800 else disp12

    def lit_l(disp):
        tgt = ((pc + 4) & ~3) + disp * 4
        o = tgt - base
        if 0 <= o + 4 <= len(code):
            return tgt, struct.unpack_from(">I", code, o)[0]
        return tgt, None

    def lit_w(disp):
        tgt = pc + 4 + disp * 2
        o = tgt - base
        if 0 <= o + 2 <= len(code):
            return tgt, struct.unpack_from(">H", code, o)[0]
        return tgt, None

    if a == 0xD:
        tgt, val = lit_l(imm8)
        return f"mov.l @({imm8:x},pc),{_r(b)}", f"[{tgt:08x}] = {val:08x}" if val is not None else ""
    if a == 9:
        tgt, val = lit_w(imm8)
        return f"mov.w @({imm8:x},pc),{_r(b)}", f"[{tgt:08x}] = {val:04x}" if val is not None else ""
    if a == 0xE:
        return f"mov #{simm8:#x},{_r(b)}", ""
    if a == 6:
        m = {0: "mov.b @%s,%s", 1: "mov.w @%s,%s", 2: "mov.l @%s,%s", 3: "mov %s,%s",
             4: "mov.b @%s+,%s", 5: "mov.w @%s+,%s", 6: "mov.l @%s+,%s", 7: "not %s,%s",
             8: "swap.b %s,%s", 9: "swap.w %s,%s", 0xA: "negc %s,%s", 0xB: "neg %s,%s",
             0xC: "extu.b %s,%s", 0xD: "extu.w %s,%s", 0xE: "exts.b %s,%s", 0xF: "exts.w %s,%s"}
        if d in m:
            return m[d] % (_r(c), _r(b)), ""
    if a == 2:
        m = {0: "mov.b %s,@%s", 1: "mov.w %s,@%s", 2: "mov.l %s,@%s",
             4: "mov.b %s,@-%s", 5: "mov.w %s,@-%s", 6: "mov.l %s,@-%s",
             8: "tst %s,%s", 9: "and %s,%s", 0xA: "xor %s,%s", 0xB: "or %s,%s",
             0xC: "cmp/str %s,%s", 0xD: "xtrct %s,%s", 0xE: "mulu.w %s,%s", 0xF: "muls.w %s,%s"}
        if d in m:
            return m[d] % (_r(c), _r(b)), ""
    if a == 3:
        m = {0: "cmp/eq %s,%s", 2: "cmp/hs %s,%s", 3: "cmp/ge %s,%s", 4: "div1 %s,%s",
             5: "dmulu.l %s,%s", 6: "cmp/hi %s,%s", 7: "cmp/gt %s,%s", 8: "sub %s,%s",
             0xA: "subc %s,%s", 0xB: "subv %s,%s", 0xC: "add %s,%s", 0xD: "dmuls.l %s,%s",
             0xE: "addc %s,%s", 0xF: "addv %s,%s"}
        if d in m:
            return m[d] % (_r(c), _r(b)), ""
    if a == 7:
        return f"add #{simm8:#x},{_r(b)}", ""
    if a == 1:
        return f"mov.l {_r(c)},@({d*4:#x},{_r(b)})", ""
    if a == 5:
        return f"mov.l @({d*4:#x},{_r(c)}),{_r(b)}", ""
    if a == 8:
        if b == 0:
            return f"mov.b {_r(0)},@({d:#x},{_r(c)})", ""
        if b == 1:
            return f"mov.w {_r(0)},@({d*2:#x},{_r(c)})", ""
        if b == 4:
            return f"mov.b @({d:#x},{_r(c)}),r0", ""
        if b == 5:
            return f"mov.w @({d*2:#x},{_r(c)}),r0", ""
        if b == 8:
            return f"cmp/eq #{simm8:#x},r0", ""
        if b == 9:
            return f"bt {pc + 4 + simm8 * 2:08x}", ""
        if b == 0xB:
            return f"bf {pc + 4 + simm8 * 2:08x}", ""
        if b == 0xD:
            return f"bt/s {pc + 4 + simm8 * 2:08x}", ""
        if b == 0xF:
            return f"bf/s {pc + 4 + simm8 * 2:08x}", ""
    if a == 0xA:
        return f"bra {pc + 4 + sdisp12 * 2:08x}", ""
    if a == 0xB:
        return f"bsr {pc + 4 + sdisp12 * 2:08x}", ""
    if a == 0xC:
        m = {0: f"mov.b r0,@({imm8:#x},gbr)", 4: f"mov.b @({imm8:#x},gbr),r0",
             8: f"tst #{imm8:#x},r0", 9: f"and #{imm8:#x},r0",
             0xA: f"xor #{imm8:#x},r0", 0xB: f"or #{imm8:#x},r0"}
        if b in m:
            return m[b], ""
        if b == 7:
            return f"mova @({imm8:#x},pc),r0  ; {((pc + 4) & ~3) + imm8 * 4:08x}", ""
    if a == 0 and d == 0xC:
        return f"mov.b @({_r(0)},{_r(c)}),{_r(b)}", ""
    if a == 0 and d == 0xE:
        return f"mov.l @({_r(0)},{_r(c)}),{_r(b)}", ""
    if a == 0 and d == 4:
        return f"mov.b {_r(c)},@({_r(0)},{_r(b)})", ""
    if a == 0 and d == 6:
        return f"mov.l {_r(c)},@({_r(0)},{_r(b)})", ""
    if a == 0 and d == 5:
        return f"mov.w {_r(c)},@({_r(0)},{_r(b)})", ""
    if a == 0 and d == 0xD:
        return f"mov.w @({_r(0)},{_r(c)}),{_r(b)}", ""
    if a == 0 and d == 7:
        return f"mul.l {_r(c)},{_r(b)}", ""
    if a == 0 and d == 3 and c == 0:
        return f"bsrf {_r(b)}", ""
    if a == 0 and d == 3 and c == 2:
        return f"braf {_r(b)}", ""
    if w == 0x000B:
        return "rts", ""
    if w == 0x0009:
        return "nop", ""
    if w == 0x0028:
        return "clrmac", ""
    if w == 0x0019:
        return "div0u", ""
    if a == 4:
        m = {0x0B: "jsr @%s", 0x2B: "jmp @%s", 0x0E: "ldc %s,sr", 0x1E: "ldc %s,gbr",
             0x0A: "lds %s,mach", 0x1A: "lds %s,macl", 0x2A: "lds %s,pr",
             0x00: "shll %s", 0x01: "shlr %s", 0x04: "rotl %s", 0x05: "rotr %s",
             0x08: "shll2 %s", 0x09: "shlr2 %s", 0x18: "shll8 %s", 0x19: "shlr8 %s",
             0x28: "shll16 %s", 0x29: "shlr16 %s", 0x10: "dt %s", 0x11: "cmp/pz %s",
             0x15: "cmp/pl %s", 0x20: "shal %s", 0x21: "shar %s",
             0x26: "lds.l @%s+,pr", 0x22: "sts.l pr,@-%s", 0x0F: "mac.w @%s+,@%s+"}
        key = w & 0xFF
        if key in m:
            return m[key] % _r(b), ""
    if a == 0 and (w & 0xFF) == 0x2A:
        return f"sts pr,{_r(b)}", ""
    if a == 0 and (w & 0xFF) == 0x0A:
        return f"sts mach,{_r(b)}", ""
    if a == 0 and (w & 0xFF) == 0x1A:
        return f"sts macl,{_r(b)}", ""
    if a == 0 and (w & 0xFF) == 0x02:
        return f"stc sr,{_r(b)}", ""
    return f".word {w:04x}", ""


def dump(code, start_off, count, base, out=sys.stdout):
    for i in range(count):
        o = start_off + i * 2
        if o + 2 > len(code):
            break
        w = struct.unpack_from(">H", code, o)[0]
        text, extra = disasm_one(code, o, base)
        print(f"{base + o:08x}  {w:04x}  {text:<34}{extra}", file=out)


if __name__ == "__main__":
    path, off, cnt = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    base = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
    dump(open(path, "rb").read(), off, cnt, base - off if base else 0)
