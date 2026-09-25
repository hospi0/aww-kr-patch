# -*- coding: utf-8 -*-
"""/GMDT 훈장·레벨업 풀 번역표 (세션17).

★발견 경위: 사용자 실기 스샷(`훈장수여.png`·`레벨업1~4.png`·`결과화면글자깨짐.png`)에서
  글자가 깨져 보였다. 역추적하니 **번역이 잘못된 게 아니라 미번역**이었고, 회수한 글리프를
  그 일본어가 그대로 참조해 엉뚱한 한글로 렌더된 것이었다.

★★진짜 원인 = **사본 함정(또 재발)**. 같은 내용이 `/KEKKA 0x20F8E~` 에도 있어서
  세션16이 그쪽만 번역했는데, **화면이 읽는 건 `/GMDT` 쪽**이다.
  ⇒ 훈장 이름·설명, 레벨업/능력획득 메시지가 통째로 일본어로 남아 있었다.

신규 번역은 3개뿐이고 나머지 80개는 `kekka_kr`·`ui16_kr` 의 기존 역어를 그대로 쓴다
(같은 문구를 두 화면에서 다르게 부르면 안 된다 — [[feedback_reuse_existing_work]]).
"""

# 원문 : 번역 — **여기 없는 것은 kekka_kr/ui16_kr 에서 자동으로 가져온다.**
# ⚠️length-locked: 번역 글자수 ≤ 원문 글자수(칸수).
NEW = {
    # 출격/설치 안내 (앞 레코드 「Fの出撃位置を選択して」 에 이어지는 둘째 줄)
    '下さい。国旗の位置から出撃できます。': '주세요。국기 위치에서 출격 가능。',   # 18칸
    'Fの空港を設置して下さい。':           'F의 공항을 설치하세요。',            # 13칸
    '国旗の位置に設置できます。':           '국기 위치에 설치 가능。',            # 13칸
    # 저장/불러오기 확인창 — `いいえ`(아니오)만 번역돼 있고 `は い` 는 빠져 있었다.
    #   원문이 공백을 낀 3칸이라 3칸을 유지한다(뒤는 널 패딩).
    'は い':                              '예',                                # 3칸
    # 결과화면 하단 설명문(/KEKKA 0x019D32) — {FD} 로 **두 줄로 쪼개져** 있어서
    #   kekka_kr 의 이어붙인 역어로는 매칭이 안 된다. 조각별로 넣는다.
    '勝利レベル／勝利得点などの情報を得ること': '승리등급／승리득점 등 정보를',        # 20칸
    'ができます。':                         '얻습니다。',                        # 6칸
    # 설정화면 아래쪽 옵션/디버그 항목 — 회수된 글자만 한글로 바뀌어 깨져 있었다
    #   (`操作制限`→`엔作制限`). build_ui16 의 설정 풀 범위 밖이라 빠졌다.
    '項目制限': '항목제한', '操作制限': '조작제한', '移動無限': '이동무한',
    '索敵表示': '색적표시', '金無制限': '자금무한', '生産無限': '생산무한',
    '通常':     '통상',
    # 값 목록 `無有通常雨1雪1雪2` — 無·有는 **1칸 필드**라 한 글자로만 들어간다.
    '無':       '무',   '有':       '유',
    # /GAME 전투맵 메시지 — 이 모듈은 build_ui16 이 브리핑 HUD 만 다뤄서 빠져 있었다.
    '敵国の援軍が到着しました。': '적국 원군 도착했습니다。',   # 13칸
    '味方の援軍が到着しました。': '아군 원군 도착했습니다。',   # 13칸
    '自動帰還ON。':              '자동귀환ON。',              # 7칸
    '未行動の航空機は、自動帰還を行います。': '미행동 항공기는 자동귀환합니다。',  # 19칸
}


def table():
    """원문 → 한글. kekka_kr(원문 매칭) + ui16_kr + NEW 를 합친다."""
    import json
    import os
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    root = os.path.dirname(here)

    out = {}
    # ① kekka_medal 풀의 (원문 → 한글) — 인덱스 기반 kekka_kr.KR 을 원문에 붙인 것
    import extract_pool as EP
    import kekka_kr as K
    import charmap
    from isoread import TRACK1, read_range
    from scan_files import files
    mod, _f, lo, hi, _d = EP.POOLS['kekka_medal']
    m = {q: (l, s) for q, l, s in files(skip_media=False)}
    lba, size = m[mod]
    with open(TRACK1, 'rb') as f:
        d = read_range(f, lba, size)
    recs = []
    for a, b in (EP.SPLIT.get('kekka_medal') or [(lo, hi)]):
        recs += EP.records(d, a, b, charmap.CHARS)
    for i, r in enumerate(recs):
        jp = r[2]
        if i in K.KR and jp:
            out.setdefault(jp, K.KR[i])
    # ② UI 라벨·메시지
    import ui16_kr as U
    for src in (U.LABELS, U.UNITINFO, U.SETTINGS, U.MESSAGES):
        for jp, kr in src.items():
            out.setdefault(jp, kr)
    # ③ 이 파일의 신규 번역이 최우선
    out.update(NEW)
    return out
