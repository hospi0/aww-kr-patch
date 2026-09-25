# -*- coding: utf-8 -*-
"""화면에 「깨진 한글」로 뜬 문자열 → 원본 일본어 역추적.

원리: 한글화는 원본 글리프 슬롯을 회수해 그 자리에 한글을 그린다.
      회수한 슬롯을 **아직 참조하는 미발견 일본어 텍스트**는
      그 자리의 한글로 렌더된다.
      ⇒ 보이는 한글 → 슬롯 인덱스 → 원본 문자 로 되돌리면
        「그 자리에 있던 진짜 일본어」를 알 수 있다.

사용: python tools/degarble.py "줄詰입" [폰트]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import charmap

# 폰트별 「한글 → 슬롯」 등록부 (여러 개면 합친다)
REGISTRIES = {
    "ASC16CG": ["asc16_slots.json", "shared_unit_slots.json"],
    "SAKUCG":  ["sakucg_slots.json"],
    "ASCIMCG": ["ascimcg_slots.json"],
    "ASCMSCG": ["museum_slots.json", "shared_unit_slots.json"],
    "ASCGSCG": ["brief_slots.json", "chrono_slots.json"],
    "SCHOOL":  ["school_slots.json"],
}


def load_rev(font):
    """한글 -> [슬롯...]"""
    rev = {}
    for fn in REGISTRIES[font]:
        p = os.path.join(ROOT, "work", fn)
        if not os.path.exists(p):
            continue
        for syl, idx in json.load(open(p, encoding="utf-8")).items():
            rev.setdefault(syl, []).append((int(idx), fn))
    return rev


def degarble(s, font="ASC16CG"):
    rev = load_rev(font)
    out = []
    for ch in s:
        cands = rev.get(ch)
        if not cands:
            out.append((ch, None, ch, "원본그대로"))
            continue
        for idx, src in cands:
            out.append((ch, idx, charmap.CHARS.get(idx, "?"), src))
    return out


if __name__ == "__main__":
    text = sys.argv[1]
    fonts = [sys.argv[2]] if len(sys.argv) > 2 else list(REGISTRIES)
    for font in fonts:
        rows = degarble(text, font)
        jp = "".join(r[2] for r in rows)
        print("[%s] %s  ->  %s" % (font, text, jp))
        for ch, idx, jpc, src in rows:
            print("    %s  slot=%s  원본=%s  (%s)" % (ch, idx, jpc, src))
