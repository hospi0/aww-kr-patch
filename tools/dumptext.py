"""지정 파일의 텍스트 블록을 디코드해 출력."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isoread import TRACK1, read_range
from scan_files import files
from findtext import blocks
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
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    data = get(path)
    bs = blocks(data)
    print("# %s : %d blocks" % (path, len(bs)))
    for off, nw, ink in bs[:lim]:
        print("--- 0x%06x  %d words / %d chars" % (off, nw, ink))
        print(charmap.decode(data, off, nw))
