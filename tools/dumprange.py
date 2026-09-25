"""파일의 지정 바이트 범위를 글리프인덱스 텍스트로 디코드해 출력.

사용: python tools/dumprange.py /SCHOOL 0x39000 0x400
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
import charmap


def get(path):
    for p, lba, size in files(skip_media=False):
        if p == path:
            with open(TRACK1, "rb") as f:
                return read_range(f, lba, size)
    raise SystemExit("no such file: " + path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    path = sys.argv[1]
    off = int(sys.argv[2], 0)
    ln = int(sys.argv[3], 0)
    data = get(path)
    for i in range(0, ln, 32):
        chunk = charmap.decode(data, off + i, min(16, (ln - i) // 2))
        print("0x%06x  %s" % (off + i, chunk.replace("\n", "\\n")))
