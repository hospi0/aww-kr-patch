# -*- coding: utf-8 -*-
"""카타카나 → 라틴 음차 (Hepburn 근사). 실명 맵에 없는 희귀/가상 지명·유닛의 폴백.

목적: 가나를 라틴으로 돌려 슬롯을 해방(한글 아님). 8칸 축약. 표기 완벽이 목적 아님.
"""
_K = {
    'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
    'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
    'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
    'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
    'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
    'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
    'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
    'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
    'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
    'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n', 'ヴ': 'vu',
    'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
    'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
    'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
    'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
    'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
}
_SMALL = {'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo', 'ァ': 'a', 'ィ': 'i', 'ゥ': 'u', 'ェ': 'e', 'ォ': 'o'}


def kata_to_latin(s, maxlen=8):
    out = []
    prev = ''
    for ch in s:
        if ch in _SMALL:
            # 요음: 앞 음절의 자음 + 소문자 모음 (예: シ+ャ = sha)
            if out and out[-1] and out[-1][-1] in 'aiueo':
                base = out[-1]
                out[-1] = base[:-1] + _SMALL[ch] if base[-1] == 'i' else base + _SMALL[ch]
            else:
                out.append(_SMALL[ch])
        elif ch == 'ッ':          # 촉음: 다음 자음 중복 (근사로 생략)
            continue
        elif ch == 'ー':          # 장음: 생략
            continue
        elif ch in ('・', '·'):    # 중점 구분 유지 안 함
            continue
        elif ch in _K:
            out.append(_K[ch])
        else:
            out.append(ch)        # 숫자·라틴·기호 유지
    res = ''.join(out)
    # 첫 글자 대문자
    if res and res[0].islower():
        res = res[0].upper() + res[1:]
    return res[:maxlen]


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for t in ['アロクマ', 'ラハガセ', 'コロブヌイ', 'ヴォロシロフグラ', 'ズリーニィ', 'ケーリアン']:
        print('%-16s -> %s' % (t, kata_to_latin(t)))
