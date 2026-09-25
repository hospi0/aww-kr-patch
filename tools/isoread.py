"""Track 01 (MODE1/2352) ISO9660 리더 - 읽기 전용 조사용."""
import os, struct, sys

ROM_DIR = r"C:\claude\roms\ss\Advanced World War - Sennen Teikoku no Koubou - Last of the Millennium (Japan) (Rev B) (22M)"
TRACK1 = os.path.join(ROM_DIR, "Advanced World War - Sennen Teikoku no Koubou - Last of the Millennium (Japan) (Rev B) (22M) (Track 01).bin")

RAW = 2352
HDR = 16          # MODE1: sync(12) + header(4)
USER = 2048


def read_sector(f, lba):
    f.seek(lba * RAW)
    raw = f.read(RAW)
    if len(raw) < RAW:
        return None
    return raw[HDR:HDR + USER]


def read_range(f, lba, nbytes):
    out = bytearray()
    while len(out) < nbytes:
        s = read_sector(f, lba)
        if s is None:
            break
        out += s
        lba += 1
    return bytes(out[:nbytes])


def parse_dir(data):
    """디렉터리 extent 바이트 -> 레코드 리스트."""
    recs = []
    off = 0
    while off < len(data):
        ln = data[off]
        if ln == 0:
            # 다음 논리 섹터 경계로
            off = (off // USER + 1) * USER
            if off >= len(data):
                break
            continue
        r = data[off:off + ln]
        try:
            lba = struct.unpack_from("<I", r, 2)[0]
            size = struct.unpack_from("<I", r, 10)[0]
            flags = r[25]
            nlen = r[32]
            name = r[33:33 + nlen]
        except Exception:
            break
        recs.append({"name": name, "lba": lba, "size": size, "flags": flags})
        off += ln
    return recs


def walk(f, lba, size, path="", out=None, depth=0):
    if out is None:
        out = []
    if depth > 8:
        return out
    data = read_range(f, lba, size)
    for r in parse_dir(data):
        nm = r["name"]
        if nm in (b"\x00", b"\x01"):
            continue
        name = nm.decode("shift_jis", "replace").split(";")[0]
        full = path + "/" + name
        if r["flags"] & 2:
            out.append({"path": full, "lba": r["lba"], "size": r["size"], "dir": True})
            walk(f, r["lba"], r["size"], full, out, depth + 1)
        else:
            out.append({"path": full, "lba": r["lba"], "size": r["size"], "dir": False})
    return out


def main():
    with open(TRACK1, "rb") as f:
        # 부트 헤더
        s0 = read_sector(f, 0)
        print("=== SYSTEM ID (sector 0) ===")
        print(s0[:0x100].decode("shift_jis", "replace"))

        pvd = read_sector(f, 16)
        print("=== PVD ===")
        print("type", pvd[0], "id", pvd[1:6])
        print("volume:", pvd[40:72].decode("ascii", "replace").strip())
        vol_lba = struct.unpack_from("<I", pvd, 80)[0]
        print("volume space size (sectors):", vol_lba)
        root = pvd[156:156 + 34]
        rlba = struct.unpack_from("<I", root, 2)[0]
        rsize = struct.unpack_from("<I", root, 10)[0]
        print("root lba", rlba, "size", rsize)

        files = walk(f, rlba, rsize)
        print("=== FILES: %d ===" % len(files))
        for e in files:
            print("%-40s lba=%-8d size=%-10d %s" % (e["path"], e["lba"], e["size"], "DIR" if e["dir"] else ""))


if __name__ == "__main__":
    main()
