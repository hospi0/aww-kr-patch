"""8x8 한글 글리프 렌더 후보 비교.

소형 폰트(무기명·지명)는 8x8 4bpp **2색(0/15)** 하드엣지다. 16x16용 정본
(맑은고딕 14px 4배 슈퍼샘플링 + 감마 0.75, [[project_aww_ss_kr]])은 계조 폰트용이라
여기엔 그대로 못 쓴다 — 여기선 임계값으로 1비트화해야 한다.

이 파일은 "무엇이 읽히는가"를 눈으로 고르기 위한 비교 도구다. 정본이 정해지면 render8()만 남긴다.
"""
import os
from PIL import Image, ImageFont, ImageDraw

WIN = r'C:\Windows\Fonts'

CANDIDATES = [
    # (라벨, 폰트파일, ttc index, 픽셀크기, 슈퍼샘플배율, 임계값)
    ('gulimche8',  'gulim.ttc', 3, 8,  1, 128),
    ('gulimche9',  'gulim.ttc', 3, 9,  1, 128),
    ('dotumche8',  'gulim.ttc', 1, 8,  1, 128),
    ('malgun8',    'malgun.ttf', 0, 8, 1, 128),
    ('malgun_ss10','malgun.ttf', 0, 10, 4, 120),
    ('malgun_ss12','malgun.ttf', 0, 12, 4, 120),
    ('malgunbd_ss12','malgunbd.ttf', 0, 12, 4, 130),
    ('batang_ss12','batang.ttc', 0, 12, 4, 120),
]


def render8(ch, fontfile, index, size, ss, thr, dx=0, dy=0):
    """한 글자를 8x8 1비트(0/1) 리스트로."""
    f = ImageFont.truetype(os.path.join(WIN, fontfile), size * ss, index=index)
    big = Image.new('L', (8 * ss * 2, 8 * ss * 2), 0)
    d = ImageDraw.Draw(big)
    bbox = d.textbbox((0, 0), ch, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ox = (8 * ss * 2 - w) // 2 - bbox[0]
    oy = (8 * ss * 2 - h) // 2 - bbox[1]
    d.text((ox, oy), ch, font=f, fill=255)
    # 잉크 bbox 로 재중심 후 8x8 로 축소
    bb = big.getbbox()
    if bb is None:
        return [[0] * 8 for _ in range(8)]
    crop = big.crop(bb)
    cw, ch_ = crop.size
    s = min(8 * ss / cw, 8 * ss / ch_)
    nw, nh = max(1, int(round(cw * s))), max(1, int(round(ch_ * s)))
    crop = crop.resize((nw, nh), Image.LANCZOS if ss > 1 else Image.NEAREST)
    cell = Image.new('L', (8 * ss, 8 * ss), 0)
    cell.paste(crop, ((8 * ss - nw) // 2 + dx, (8 * ss - nh) // 2 + dy))
    if ss > 1:
        cell = cell.resize((8, 8), Image.LANCZOS)
    return [[1 if cell.getpixel((x, y)) >= thr else 0 for x in range(8)] for y in range(8)]
