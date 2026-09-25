# -*- coding: utf-8 -*-
"""부대명·장군명 174종 한글 번역표 (세션15-e, 사용자 결정 「174종 전부 한글」).

세션9가 로마자화했던 것(`イタリア8A`→`It-8A`)을 한글로 되돌린다.
필드 = 16×16 **8글리프 고정**(build_general16). 소형 8×8 사본은 칸이 없어 로마자 유지 —
⚠️그래서 HUD `〈이름〉 휘하`(소형)와 좌패널(16×16) 표기가 어긋난다(사용자 수용).

구성: person 38(실존 인물 음차) + force 135(국가+번호, 규칙 생성) + 헤더 1
"""

# ── 실존 인물 38종 (음차) ──────────────────────────────────────────────
PERSON = {
    'ガーランド': '갈란트',        'ホト': '호트',            'クルーゲ': '클루게',
    'ケッセルリンク': '케셀링',     'グデーリアン': '구데리안',  'ロンメル': '롬멜',
    'リヒトホーヘン': '리히트호펜', 'ヘープナー': '회프너',      'マンシュタイン': '만슈타인',
    'パウルス': '파울루스',        'ヴァイクス': '바이크스',    'ライヘナウ': '라이헤나우',
    'リヒトフォーヘン': '리히트호펜', 'メルダース': '묄더스',    'クルーベル': '클뤼버',
    'モーデル': '모델',           'クライスト': '클라이스트',  'ラインハルト': '라인하르트',
    'マジノFort': '마지노요새',    'ガーランドAf': '갈란트공군', 'レーダー': '레더',
    'Hブタイ': 'H부대',           'トリエステD': '트리에스테', 'アリエテTk': '아리에테전차',
    'ボローニャD': '볼로냐사단',    'ブレッシアD': '브레시아',   'サボナD': '사보나사단',
    'トレントD': '트렌토사단',     'パビアD': '파비아사단',     'アルニム': '아르님',
    'スコルッツニー': '스코르체니', 'マントイフェル': '만토이펠', 'デートリッヒ': '디트리히',
    'ポポフTk': '포포프전차',      'ハウサー': '하우서',        'ケンプ': '켐프',
    'ヴェーラー': '뵐러',         'ロドリゲス': '로드리게스',
}

# ── force 규칙 ────────────────────────────────────────────────────────
NATION = {
    'ソビエト': '소련', 'ルーマニア': '루마니아', 'イタリア': '이탈리아', 'ドイツ': '독일',
    'ベルギー': '벨기에', 'フランス': '프랑스', 'イギリス': '영국', 'アメリカ': '미국',
    'カナダ': '캐나다', 'チチュウカイ': '지중해', 'ナンキョク': '남극', 'Rハンター': '룬헌터',
}
# 접미(긴 것부터) — A=Army, AF=공군, SA=충격군, GA=근위군, TkA/TA=전차군, Tk=전차,
#   Pz=기갑, D=사단, GD=근위사단, Cp=군단, Gp=집단, AB/AD/GD 등 영국·미국 편제
SUFFIX = [
    ('AF1', '공군1'), ('AF2', '공군2'),
    ('GTk', '근위전차'), ('TkA', '전차군'), ('ACp', '기갑군단'), ('Cp', '군단'),
    ('GA', '근위군'), ('GD', '근위사단'), ('SA', '충격군'), ('AF', '공군'),
    ('AB', '공수'), ('AD', '기갑사단'), ('Gp', '집단'), ('HQ', '사령부'),
    ('MA', '주력군'), ('FT', '전선'), ('Tk', '전차'), ('Pz', '기갑'),
    ('Tr', '수송'), ('D', '사단'), ('A', '군'),
]
# 규칙으로 안 풀리는 것 — 직접 지정
FORCE_FIX = {
    'テキ': '적군',            'Team.PP': 'Team.PP',      '14th.AFt': '14thAFt',
    'ヨビグン1': '예비군1',     'ヨビグン2': '예비군2',     'ヨビグン3': '예비군3',
    'ソビエトホウヘイ': '소련보병', 'ソビエトヨビヘイ': '소련예비',
    'ヨビヘイダン': '예비군단',  'BEF': 'BEF',             'RAF': 'RAF',
    'RAF1': 'RAF1',           'RAF2': 'RAF2',
    '70thD': '70thD',         '32Arm': '32Arm',          '4thArm': '4thArm',
    '7thArm': '7thArm',       '22ndGd': '22ndGd',        '1stSAD': '1stSAD',
    '4thIND': '4thIND',       '2ndNZD': '2ndNZD',
    'ベルギーDfCp': '벨기에방어', 'ベルギーCp': '벨기에군단',
    'ソビエトCGp': '소련기병단',
}


def force_kr(name):
    """부대명 → 한글. 못 풀면 None."""
    if name in FORCE_FIX:
        return FORCE_FIX[name]
    for jp, kr in NATION.items():
        if name.startswith(jp):
            rest = name[len(jp):]
            if not rest:
                return kr + '군'
            for suf, ksuf in SUFFIX:
                if rest.endswith(suf):
                    num = rest[:-len(suf)]
                    return kr + num + ksuf
            return kr + rest
    return None


def build():
    """{원문: 한글} 전체."""
    import csv, os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rows = list(csv.reader(open(os.path.join(root, 'work', 'generals_romaji.tsv'),
                                encoding='utf-8'), delimiter='\t'))[1:]
    out, miss = {}, []
    for r in rows:
        jp, kind = r[0], r[1]
        if kind == 'person':
            kr = PERSON.get(jp)
        else:
            kr = force_kr(jp)
        if kr is None:
            miss.append(jp)
        else:
            out[jp] = kr
    return out, miss


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    m, miss = build()
    over = [(a, b, len(b)) for a, b in m.items() if len(b) > 8]
    print('번역 %d종 / 미해결 %d / 8칸초과 %d' % (len(m), len(miss), len(over)))
    if miss:
        print('  미해결:', miss)
    if over:
        print('  초과:', over)
    for a, b in list(m.items())[:20]:
        print('   %-16s %s' % (a, b))
