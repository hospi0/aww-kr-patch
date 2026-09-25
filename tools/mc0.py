"""Mednafen .mc0 savestate reader (gzip'd MDFNSVST) — section extraction.

Sections are stored as `<u8 namelen><name><u32le size><data>`; the Saturn state
carries VDP1 VRAM first, then VDP2 VRAM, CRAM, and the SH-2 work RAM ("RAM",
stored byte-swapped in 16-bit words).
"""
import gzip
import struct
import sys


def load(path):
    with open(path, "rb") as f:
        head = f.read(2)
    raw = gzip.open(path, "rb").read() if head == b"\x1f\x8b" else open(path, "rb").read()
    return raw


def find_sections(raw, names=(b"VRAM", b"CRAM", b"RAM")):
    """Scan for `<len><name><u32le size>` headers. Returns list of (name, off, size)."""
    out = []
    for nm in names:
        pos = 0
        while True:
            i = raw.find(bytes([len(nm)]) + nm, pos)
            if i < 0:
                break
            pos = i + 1
            hdr = i + 1 + len(nm)
            if hdr + 4 > len(raw):
                continue
            size = struct.unpack_from("<I", raw, hdr)[0]
            if 0x1000 <= size <= 0x200000 and hdr + 4 + size <= len(raw):
                out.append((nm.decode(), hdr + 4, size))
    out.sort(key=lambda t: t[1])
    return out


def section(raw, name, index=0):
    hits = [s for s in find_sections(raw, (name.encode(),)) if s[0] == name]
    nm, off, size = hits[index]
    return raw[off:off + size]


if __name__ == "__main__":
    raw = load(sys.argv[1])
    print(f"blob {len(raw)} bytes")
    for nm, off, size in find_sections(raw):
        print(f"  {nm:6s} @0x{off:x}  size 0x{size:x} ({size})")
