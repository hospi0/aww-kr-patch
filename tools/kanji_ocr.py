"""16x16 비트맵 글리프 -> 한자 후보 매칭기 (회색조 정규상관).

★검증 필수: charmap 으로 이미 판독된 글리프에 돌려 top-1 정확도를 먼저 측정한다.
   실패한 시도 2개(같은 실수를 반복하지 않도록 기록):
     1차 이진화 IoU        -> 0%   (획 많은 한자로 전부 쏠림)
     2차 글자별 bbox 정규화 -> 1%   (「・」같은 작은 글자가 통짜 블록이 돼 만점)
   ⇒ 핵심은 **글자별로 늘리지 말 것**. 폰트 공통 em 박스를 한 번 구해 모든 후보에 같은 크롭을 쓴다.
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageFont, ImageDraw

GSZ = 128
N = 16
BOX = 64          # 후보 렌더 해상도


def _vec(img):
    """N x N 회색조 -> 평균0/단위노름 벡터."""
    if img.size != (N, N):
        img = img.resize((N, N), Image.LANCZOS)
    v = [p / 255.0 for p in img.getdata()]
    m = sum(v) / len(v)
    v = [x - m for x in v]
    nrm = math.sqrt(sum(x * x for x in v))
    if nrm < 0.5:          # 잉크가 거의 없는 글리프는 버린다
        return None
    return [x / nrm for x in v]


def glyph_img(font_data, idx):
    """게임 폰트 4bpp 16x16 글리프 -> PIL 이미지(크롭 없음)."""
    g = font_data[idx * GSZ:(idx + 1) * GSZ]
    img = Image.new("L", (16, 16), 0)
    px = img.load()
    for y in range(16):
        for x in range(16):
            b = g[y * 8 + x // 2]
            v = (b >> 4) if x % 2 == 0 else (b & 15)
            px[x, y] = v * 17
    return img


def glyph_vec(font_data, idx):
    return _vec(glyph_img(font_data, idx))


class Renderer:
    """폰트 공통 em 박스를 한 번 정하고, 모든 후보에 같은 크롭을 적용한다."""

    def __init__(self, ttf):
        self.ttf = ttf
        # 전각 꽉 채우는 글자들로 공통 박스 산출
        boxes = []
        for ref in "国鬱曇議闘囲":
            im = Image.new("L", (BOX * 2, BOX * 2), 0)
            ImageDraw.Draw(im).text((BOX // 2, BOX // 2), ref, fill=255, font=ttf)
            bb = im.getbbox()
            if bb:
                boxes.append(bb)
        l = min(b[0] for b in boxes); t = min(b[1] for b in boxes)
        r = max(b[2] for b in boxes); btm = max(b[3] for b in boxes)
        # 정사각으로 맞춘다
        w, h = r - l, btm - t
        s = max(w, h)
        cx, cy = (l + r) // 2, (t + btm) // 2
        self.crop = (cx - s // 2, cy - s // 2, cx - s // 2 + s, cy - s // 2 + s)

    def vec(self, ch):
        im = Image.new("L", (BOX * 2, BOX * 2), 0)
        ImageDraw.Draw(im).text((BOX // 2, BOX // 2), ch, fill=255, font=self.ttf)
        return _vec(im.crop(self.crop))


def score(a, b):
    return sum(x * y for x, y in zip(a, b))


def build_candidates(ttf, chars):
    r = Renderer(ttf)
    out = {}
    for ch in chars:
        v = r.vec(ch)
        if v:
            out[ch] = v
    return out


def jis_chars():
    """JIS 한자 + 가나 후보 집합(cp932 인코딩 가능한 것)."""
    cs = []
    for lo, hi in ((0x4E00, 0x9FA6), (0x3040, 0x30FF)):
        for cp in range(lo, hi):
            ch = chr(cp)
            try:
                ch.encode("cp932")
            except Exception:
                continue
            cs.append(ch)
    return cs


def topk(vec, cands, k=5):
    scored = [(score(vec, v), ch) for ch, v in cands.items()]
    scored.sort(reverse=True)
    return scored[:k]
