# -*- coding: utf-8 -*-
"""번역문 공통 규칙 — 모든 한글 인코더가 **쓰는 순간** 거친다(2026-10-03).

squeeze: 표준 문장부호 뒤 공백(반각·전각) **1칸** 삭제. 2칸 이상은 칸 맞춤이라 둔다.
         ([[feedback_no_space_after_punct]] 전프로젝트 규칙 — 표에만 적지 말고 빌더에서.)
"""
import re

PUNCT = ",.!?:;)]}'\"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥"
_PAT = re.compile('([' + re.escape(PUNCT) + '])[ 　](?![ 　])')


def squeeze(t):
    return _PAT.sub(r'\1', t)
