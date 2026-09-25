# -*- coding: utf-8 -*-
"""16×16 텍스트 글리프 — **원본식 외곽선** vs 현행 AA 비교 (세션17).

문제: 밝은 회색 패널 위에서 한글 획 주변이 지저분하다(사용자 스샷 `글자테두리*.png`).
원인: NBG3 팔레트 pal0 이 `1=밝은회색(0x788078) … 15=검정` 내림 램프인데,
      우리 글리프는 **획 15 + AA 4~14(전부 어두운 회색)** 만 쓰고 밝은 외곽선(1)을 안 쓴다.
      ⇒ 밝은 배경 위에서 획 둘레에 흐린 어두운 띠가 생긴다.
원본: 일본어 글리프는 **획 15 + 1px 외곽선 1** 로 배경과 확실히 분리한다(`現` 실측:
      15가 57픽셀, 1이 72픽셀). 한자도 획이 촘촘한데 외곽선이 들어간다.
⇒ 획을 조금 가늘게 하고 원본과 같은 구조로 그리면 배경과 무관하게 깨끗해질 수 있다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hangul import REGULAR, CELL

INK, OUTLINE = 15, 1


def coverage(ch, px, ss=4, dy=0):
    from PIL import Image, ImageDraw, ImageFont
    S = CELL * ss
    font = ImageFont.truetype(REGULAR, px * ss)
    img = Image.new('L', S if isinstance(S, tuple) else (S, S), 0)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S - w) / 2 - bb[0], (S - h) / 2 - bb[1] + dy * ss), ch, font=font, fill=255)
    small = img.resize((CELL, CELL), Image.LANCZOS)
    p = small.load()
    return [[p[x, y] / 255.0 for x in range(CELL)] for y in range(CELL)]


def outline_levels(ch, px=13, thr=0.45, soft=0.0):
    """원본 구조: 획=15, 그 둘레 1px=1(밝은 회색), 나머지 0.

    soft>0 이면 획 가장자리에 중간 계조를 조금 남긴다(원본도 5·9·12·14 를 조금 쓴다).
    """
    cov = coverage(ch, px)
    ink = [[cov[y][x] >= thr for x in range(CELL)] for y in range(CELL)]
    lv = [[0] * CELL for _ in range(CELL)]
    for y in range(CELL):
        for x in range(CELL):
            if ink[y][x]:
                lv[y][x] = INK
            else:
                near = any(0 <= y + dy < CELL and 0 <= x + dx < CELL and ink[y + dy][x + dx]
                           for dy in (-1, 0, 1) for dx in (-1, 0, 1))
                if near:
                    if soft > 0 and cov[y][x] >= soft:
                        lv[y][x] = 9          # 획에 가까운 쪽은 중간 계조
                    else:
                        lv[y][x] = OUTLINE
    return lv


def dark_levels(ch):
    """현행 방식(hangul.to_glyph_dark) 계조."""
    from hangul import render_kr
    g = render_kr(ch, ramp='dark')
    lv = [[0] * CELL for _ in range(CELL)]
    for t in range(4):
        cx, cy = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(8):
                i = t * 32 + y * 4 + x // 2
                lv[cy + y][cx + x] = (g[i] >> 4) if x % 2 == 0 else (g[i] & 0xF)
    return lv
