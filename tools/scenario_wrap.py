# -*- coding: utf-8 -*-
"""문단 → 원본 줄폭에 맞춘 줄바꿈 (세션16).

시나리오 풀은 **레코드 하나 = 화면 한 줄**이고, 풀 전체가 여유 0칸으로 꽉 차 있다
(sakusen_msg 8,934칸 = 원문 8,934자). 한국어는 띄어쓰기 때문에 줄 단위로는 넘치기 쉬우므로
**문단 단위로 번역하고 원본 줄폭에 다시 흘려 넣는다**.

★줄바꿈은 **띄어쓰기 우선, 안 되면 낱말 중간**에서 자른다.
  원문 일본어도 「本作戦は、分割された東プロイセンへの／生命線を確保すべく」처럼
  낱말 중간에서 그냥 끊는다(줄폭이 2~18칸으로 들쭉날쭉해 다른 방법이 없다).
  띄어쓰기만 고집하면 「마지막 줄 2칸에 4글자 낱말」 같은 배치 실패가 속출한다.
★줄바꿈 자리의 공백은 저장하지 않는다 → 줄 수만큼 여유가 조금 생긴다.
★남는 줄은 공백으로 둔다(원본도 짧은 줄에 널 패딩이 있었다).

⚠️**엔진이 숫자·이름을 끼워 넣는 레코드는 문단에 묶지 말 것.**
   예) sakusen `ターン以内に` 앞에는 런타임 턴 수가 그려진다. 묶어서 흘리면 자리가 어긋난다.
"""

# 띄어쓰기로 자르려고 뒤로 물러설 수 있는 최대 칸 수(이보다 많이 버려야 하면 낱말 중간에서 자른다)
BACKTRACK = 5


def wrap(text, widths):
    """평문을 widths에 흘려 넣는다. 다 못 넣으면 None.

    ★띄어쓰기로 끊으려고 뒤로 물러서면 그 줄 끝이 남아 **칸을 버린다**.
      풀이 여유 0칸이라 그 낭비 때문에 실패하는 문단이 많다 ⇒ 물러서는 폭을
      5→0으로 줄여 가며 재시도한다(들어가는 것이 먼저, 예쁜 줄바꿈은 그다음).
    """
    for bt in range(BACKTRACK, -1, -1):
        r = _wrap(text, widths, bt)
        if r is not None:
            return r
    return None


def _wrap(text, widths, back):
    s = text
    lines = []
    for w in widths:
        s = s.lstrip(' ')
        if not s:
            lines.append('')
            continue
        if len(s) <= w:
            lines.append(s)
            s = ''
            continue
        cut = w
        if s[cut] != ' ':                      # 낱말 중간에서 끊기게 생겼다
            sp = s.rfind(' ', 0, cut + 1)
            if sp > 0 and cut - sp <= back:
                cut = sp
        lines.append(s[:cut].rstrip(' '))
        s = s[cut:]
    return None if s.strip() else lines
