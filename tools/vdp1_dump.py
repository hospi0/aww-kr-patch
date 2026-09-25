# -*- coding: utf-8 -*-
"""세션13 — 세이브스테이트의 VDP1 커맨드 리스트를 파싱해 **모든 스프라이트 텍스처**를 덤프한다.

용도: 화면의 어떤 글자가 「폰트 텍스트가 아니라 스프라이트(텍스처)」일 때, 그 텍스처의
VDP1 주소·크기·팔레트를 찾아낸다. 찾은 바이트열을 WorkRAML/H에서 역검색하면 **패치할 소스**가
나온다(세션7 버튼 풀 0x2AD780, 세션12 설정타이틀 0x2B0180이 이 방식으로 확정됐다).

VDP1 커맨드 = 32B: CTRL/LINK/PMOD/COLR/SRCA/SIZE/XA/YA/...
  · CTRL 하위 4비트 = 0 normal / 1 scaled / 2,3 distorted(텍스처 있음), 4~ 폴리곤·라인(텍스처 없음)
  · CTRL bit15 = END, bit12~14 = jump mode(0=next, 1=assign(LINK), 2=call, 3=return)
  · SRCA<<3 = 텍스처 주소, SIZE = ((>>8)&0x3F)*8 폭 / (&0xFF) 높이
  · PMOD bit3~5 = 색모드(0=16색 뱅크, 1=16색 LUT, 2/3/4=64/128/256색, 5=RGB)
사용: python tools/vdp1_dump.py <state경로|state키> [--min-h 8]
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from state_analyze import rzip_decompress, swap16

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STDIR = r"D:\hospi\RetroArch\screenshots"
BASE = ('Advanced World War - Sennen Teikoku no Koubou - '
        'Last of the Millennium (Japan) (Rev B) (22M)')


def sections(blob):
    """<u8 len><name><u32le size> 헤더를 전수 열거 → {name: [(off,size)]}"""
    out = {}
    i = 0
    while i < len(blob) - 8:
        n = blob[i]
        if 3 <= n <= 24:
            nm = blob[i + 1:i + 1 + n]
            if all(32 <= c < 127 for c in nm):
                sz = struct.unpack_from('<I', blob, i + 1 + n)[0]
                if 4 <= sz <= len(blob) - (i + 5 + n):
                    out.setdefault(nm.decode(), []).append((i + 5 + n, sz))
                    i += 1 + n + 4 + sz
                    continue
        i += 1
    return out


def load(path):
    blob, _ = rzip_decompress(path)
    sec = sections(blob)
    v1o, v1s = sec['VRAM'][0]                      # VDP1 VRAM (512KB)
    v2o, v2s = sec['VRAM'][1]                      # VDP2 VRAM
    cro, crs = sec['CRAM'][0]
    wlo, wls = sec['WorkRAML'][0]
    who, whs = sec['WorkRAMH'][0]
    return {
        'vdp1': swap16(blob[v1o:v1o + v1s]),
        'vdp2': swap16(blob[v2o:v2o + v2s]),
        'cram': blob[cro:cro + crs],
        'wl': swap16(blob[wlo:wlo + wls]),
        'wh': swap16(blob[who:who + whs]),
    }


def cram_color(cram, idx):
    if (idx + 1) * 2 > len(cram):
        return (255, 0, 255)
    w = struct.unpack_from('<H', cram, idx * 2)[0]
    return ((w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8)


def commands(v1, limit=3000):
    """(addr, ctrl, pmod, colr, srca, size, xa, ya) 목록."""
    out = []
    addr = 0
    seen = set()
    for _ in range(limit):
        if addr in seen or addr + 32 > len(v1):
            break
        seen.add(addr)
        w = [struct.unpack_from('>H', v1, addr + i * 2)[0] for i in range(16)]
        ctrl = w[0]
        if ctrl & 0x8000:                           # END
            break
        out.append((addr, ctrl, w[2], w[3], w[4], w[5], w[6], w[7]))
        jm = (ctrl >> 12) & 7
        if jm == 0:
            addr += 32
        elif jm in (1, 2):
            addr = w[1] * 8
        else:
            break
    return out


def texture(v1, cram, pmod, colr, srca, size):
    w = ((size >> 8) & 0x3F) * 8
    h = size & 0xFF
    if w == 0 or h == 0:
        return None, 0, 0
    cm = (pmod >> 3) & 7
    base = srca * 8
    img = Image.new('RGB', (w, h), (0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if cm == 0 or cm == 1:                  # 4bpp
                o = base + y * (w // 2) + x // 2
                if o >= len(v1):
                    continue
                b = v1[o]
                n = (b >> 4) if x % 2 == 0 else (b & 15)
                px[x, y] = cram_color(cram, (colr & 0x7FF0) | n)
            elif cm in (2, 3, 4):                   # 8bpp
                o = base + y * w + x
                if o >= len(v1):
                    continue
                px[x, y] = cram_color(cram, (colr & 0x7F00) | v1[o])
            else:                                   # RGB
                o = base + (y * w + x) * 2
                if o + 1 >= len(v1):
                    continue
                c = struct.unpack_from('>H', v1, o)[0]
                px[x, y] = ((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8)
    return img, w, h


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else '.state1'
    path = key if os.path.exists(key) else os.path.join(STDIR, BASE + key)
    min_h = 8
    if '--min-h' in sys.argv:
        min_h = int(sys.argv[sys.argv.index('--min-h') + 1])
    S = load(path)
    cmds = commands(S['vdp1'])
    print('VDP1 커맨드 %d개' % len(cmds))
    shots = []
    for addr, ctrl, pmod, colr, srca, size, xa, ya in cmds:
        kind = ctrl & 0xF
        if kind > 3:
            continue
        img, w, h = texture(S['vdp1'], S['cram'], pmod, colr, srca, size)
        if img is None or h < min_h:
            continue
        shots.append((addr, srca * 8, w, h, colr, pmod, xa, ya, img))
    print('텍스처 스프라이트 %d개' % len(shots))
    for i, (addr, src, w, h, colr, pmod, xa, ya, img) in enumerate(shots):
        print('  #%-3d cmd@0x%05x  tex@0x%05x  %3dx%-3d colr=%04x pmod=%04x  화면(%d,%d)'
              % (i, addr, src, w, h, colr, pmod, xa & 0x3FF, ya & 0x3FF))
    if shots:
        cols = 8
        cw = max(s[2] for s in shots) + 4
        ch = max(s[3] for s in shots) + 12
        rows = (len(shots) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * cw, rows * ch), (20, 20, 24))
        for i, s in enumerate(shots):
            sheet.paste(s[8], ((i % cols) * cw + 2, (i // cols) * ch + 8))
        sheet = sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST)
        out = os.path.join(ROOT, 'work', 'vdp1_%s.png' % key.strip('.'))
        sheet.save(out)
        print('->', out, '(격자 %d열, 좌상단부터 #0)' % cols)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
