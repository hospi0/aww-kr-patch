# -*- coding: utf-8 -*-

"""전투맵 16×16 UI 라벨 한글 번역표 (세션8-a, 1단계).

대상 = **ASC16CG를 로드하는 화면**만. 로드 지점 역산 결과:
    GAME(브리핑·전투맵)·KEKKA(결과) = ASC16CG   ← 여기만 건드린다
    SAKUSEN = SAKUCG / INTERM = ASCIMCG / MUSEUM = ASCMSCG / GMSELDT = ASCGSCG
⚠️같은 라벨이 SAKUSEN·MUSEUM 등에도 사본으로 있지만 **폰트가 달라 손대면 깨진다**.
  (이 프로젝트에서 「사본 함정」이 이미 세 번 터졌다 — 세션8 참조.)

★length-locked가 자연스럽다: 한자어는 음절 1:1이라 陸軍将軍(4)→육군장군(4) 그대로 맞는다.
  짧아지는 건 널 패딩으로 흡수(配下ユニット 6 → 휘하부대 4).

풀 위치(원문 바이트 대조로 확정, 하드코딩 금지):
    GAME 0x0969E8~0x096A68  브리핑 HUD (現在/終了/天候/累積度/날씨/시간대)
    GMDT 0x016944~0x0169CC  장군 화면 라벨
    GMDT 0x024C1A~0x024C64  전투 상태·시간대·날씨
"""

# ── 1단계 라벨 ────────────────────────────────────────────────────────────
# 원문 : 번역.  같은 원문이 여러 풀에 나오면 전부 같은 값으로 바뀐다.
LABELS = {
    # 브리핑 HUD
    '現在':   '현재',
    '終了':   '종료',
    '天候':   '날씨',
    '累積度': '누적도',
    'ターン': '턴',
    # 날씨
    '晴れ':   '맑음',
    '曇り':   '흐림',
    '雨':     '비',
    '雪':     '눈',
    '無し':   '없음',
    '泥沼':   '진창',
    # 시간대
    '朝':     '아침',
    '昼':     '낮',
    '夕方':   '저녁',
    '夜':     '밤',
    '深夜':   '심야',
    # 장군 화면
    '陸軍将軍':     '육군장군',
    '海軍将軍':     '해군장군',
    '空軍将軍':     '공군장군',
    '配下兵器':     '휘하병기',
    '特殊技能':     '특수기능',
    '勲章一覧':     '훈장',   # 세션11: 람 확보(훈은 훈장에 남음). 4글리프 필드 fit.
    '将軍選択':     '장군선택',
    '指揮修正':     '지휘수정',
    '攻撃力':       '공격력',
    '防御力':       '방어력',
    '速度':         '속도',
    '配下ユニット': '휘하부대',
    '撃破数':       '격추수',   # 세션11: 파 확보('추'는 추락에 있음, 새음절0). 撃破→격추.
    # 장군선택 화면 하단 프롬프트 — 세션10이 POOLS 앵커로만 쓰고 번역표엔 안 넣어 일본어로 남았다.
    # 8음절 전부 기존 슬롯(예산0) · 필드 11글리프. (세션11에 실기 스샷으로 사용자가 지적)
    '将軍を選択してください': '장군을 선택하세요',
    # 전투 상태
    '中止':   '중지',
    '占領':   '점령',
    '墜落':   '추락',
    '空港':   '공항',
}

# 손대지 않는다 — 옆 라벨이 전부 영문(VP/GND/MOV/SGT/FPW)이라 일관되고, 예산도 아낀다.
KEEP = ['本体RAM', 'カートリッジRAM', '3D戦闘', 'VP', 'FPW']


def syllables(text):
    return [c for c in text if '가' <= c <= '힣']


def budget():
    uniq = set()
    for kr in LABELS.values():
        uniq.update(syllables(kr))
    return sorted(uniq)


def budget_all():
    """1단계 라벨 + 3단계 메시지 전체 음절 — **라벨 것을 앞에** 둔다.

    앞쪽(확장 슬롯 825~)에 라벨 음절이 그대로 놓이므로 세션8-a 1단계와 배정이 겹치고,
    새로 늘어난 메시지 음절만 뒤(남은 확장 슬롯 + 재사용 슬롯)로 밀린다.
    """
    lab = budget()
    msg = set()
    for kr in MESSAGES.values():
        msg.update(syllables(kr))
    for kr in UNITINFO.values():          # 세션11: 부대정보 라벨 음절도 슬롯 배정(색적력 '색')
        msg.update(syllables(kr))
    for kr in SETTINGS.values():          # 세션11: 설정화면 라벨 음절
        msg.update(syllables(kr))
    return lab + sorted(msg - set(lab))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    u = budget()
    print('라벨 %d개 / 신규 한글 음절 %d개' % (len(LABELS), len(u)))
    print(''.join(u))
    print('\n공급 = 900 − 825 = 75칸  →  %s' %
          ('OK 여유 %d' % (75 - len(u)) if len(u) <= 75 else '초과 %d' % (len(u) - 75)))


# -- B안(세션12): 시스템 메시지 = 전보식 영문 (필드가 조밀한 CJK라 자연영문 불가).
#   영문 = Latin 글리프(0~824)라 신규 음절 0 = 예산 무비용.  가용부호 = A-Za-z0-9 하이픈 어퍼스트로피 + 전각물음표/슬래시.
#   마침표.쉼표.콜론은 폰트에 없어 생략.  버튼 세이브/로드(3칸)엔 Save/Load(4) 불가 -> 저장/로드 한글 유지.
#   時間/その他는 설정계열이라 제거(SETTINGS 비움과 함께 일본어 복귀).
#   자연스러운 한글본은 archive/ui16_kr_ko964.py (1024 천장 열리면 복원).
MESSAGES = {
    '使用できません。': 'Unusable',
    '修復できません。': 'Cant fix',
    '攻撃できません。': 'No atk',
    '爆撃できません。': 'No bomb',
    '移動できません。': 'No move',
    '降下できません。': 'No drop',
    'ないため、変更できません。': 'so no change',
    '入ることができません。': 'no entry',
    '攻撃には使用できません。': 'no atk use',
    '移動後は補充できません。': 'moved no res',
    '空港には着陸できません。': 'no base land',
    '行うことができません。': 'cannot do',
    '作業することができません。': 'cannot work',
    '移動することはできません。': 'cannot move',
    '離陸することはできません。': 'no takeoff',
    '既に行動を終了しています。': 'already acted',
    '燃料タンクで攻撃することはできません。': 'No fuel-tank attack',
    'ユニットに対する攻撃はできません。': 'No unit attack',
    '移動後は間接攻撃できません。': 'No indir fire',
    '存在していないため、攻撃できません。': 'no target',
    '物資不足のため、補給できません。': 'Low supplies',
    '将軍に隣接していないと、補充できません。': 'Need gen adjacent',
    '補充は1ターンに一度しかできません。': 'Resupplied once',
    'これ以上補充することはできません。': 'Resupply full',
    'VP不足のため、補給できません。': 'Low VP',
    '空港内でしか補充できません。': 'Resup at base',
    '陸上ユニットは武装変更できません。': 'Land no rearm',
    '空港内でしか、武装変更できません。': 'Rearm base only',
    'この場所では変型できません。': 'No xform here',
    'この兵器ユニットは変型できません。': 'Unit no xform',
    'この将軍、変型できません。': 'Gen no xform',
    '空港内でしか、変型できません。': 'Xform base only',
    '自軍の空港は爆撃できません。': 'No bomb own AF',
    'FPW不足で、修復することができません。': 'Low FPW to repair',
    '大河に架橋する事はできません。': 'No river bridge',
    '資材不足のため、架橋できません。': 'Low material',
    '空港のある場所でしか離着陸できません。': 'Fly at base only',
    '陸上部隊は離着陸できません。': 'Land no flight',
    '牽引砲は、移動後に攻撃できません。': 'No fire if moved',
    '空港内で、戦闘はできません。': 'No base combat',
    '天候が雨、雪の時には、爆撃できません。': 'No bomb rain snow',
    '天候が雨、雪の時には、対空射撃できません。': 'No AA in rain snow',
    '天候が雨、雪の時には、対地射撃できません。': 'No strike rain snow',
    'これ以上、着陸できません。': 'No more land',
    'この場所には、降下できません。': 'No drop here',
    '自軍以外の空母には、着艦できません。': 'Own carrier only',
    'ターン終了しますか？': 'End turn？',
    '占領しますか？': 'Seize？',
    '各ユニットの補給を行います。': 'Resupply all',
    'ユニットの補給を行います。': 'Resupply unit',
    '未行動ユニットは、自動休息を行います。': 'Idle units rest',
    '自動補充ON。補給・補充を自動で行います。': 'Auto-resupply ON',
    'この航空ユニットは、空母に着艦できません。': 'Air no CV land',
    'これ以上、着艦できません。': 'CV land full',
    '雪の時には、使用できません。': 'No use in snow',
    '選択した武器は、移動後に攻撃できません。': 'Weapon no fire moved',
    '空き容量がありません。': 'No space',
    '更新することになります。': 'will update',
    'セーブしますか？': 'Save？',
    '更新すると、前回の記録は失われます。': 'Old record lost',
    '正しくセーブできない場合があります。': 'save may fail',
    'ロードしますか？': 'Load？',
    '記録をロードしています。': 'Loading',
    'どちらにセーブしますか？': 'Save which？',
    'どちらからロードしますか？': 'Load which？',
    'もう一度やり直して下さい。': 'Please retry',
    '記録を正しくロードできませんでした。': 'Load failed',
    'この記録でゲームをスタートできません。': 'Bad record no start',
    'セーブされた記録がありません。': 'No saved record',
    'ゲームを終了しますか？': 'Quit game？',
    'ゲームをスタートします。': 'Start game',
    'ゲームを続ける。': 'Continue',
    'ゲームを終了する。': 'Quit game',
    'セープ': '저장',
    'ロード': '로드',
    'いいえ': 'No',
    '本体RAM': 'MainRAM',
    'カートリッジRAM': 'CartRAM',
    '武器が装備されていないため、': 'No weapon',
    '建造物攻撃専用の武器です。': 'Anti-bldg wpn',
    '反撃専用の武器です。': 'Ctr weapon',
    '選択兵器の射程内に敵ユニットが': 'No enemy range',
    'このユニットには、武装タイプが1つしか': 'One weapon type',
    '将軍は空港内に一人しか': 'Gen limit 1',
    '攻撃可能範囲に建造物がないため、': 'No bldg in range',
    '崩壊した橋に隣接していないため、': 'No broken bridge',
    'その場所へは、移動力不足で': 'Low movement',
    '他部隊のいる場所には、': 'Occupied',
    '特殊作業の能力がないため、': 'No work skill',
    '反撃用の武器しか装備していないため、': 'Counter wpn only',
    '今の場所では、特殊作業を': 'No spec work',
    '輸送機に変型しないと、': 'To TP form',
    '選択したユニットは、': 'This unit',
    '現在、格納数最大です。': 'Store full',
    '夜間または、天候が雨、雪の時には、': 'Night rain snow',
    '自軍または、同盟軍以外の': 'Non-allied',
    '朝ターンになりました。': 'Morning trn',
    '選択した武器は、夜間または、天候が雨、': 'Weapon night rain',
    '新しい記録をセーブするための': 'For a new save',
    '空き容量が不足しているため、前回の記録を': 'Low space old record',
    '更新しますか？': 'Update？',
    'セーブ中です。セーブ中に電源を切ると、': 'Saving no power off',
    '本体RAMとカートリッジRAMの': 'Main or Cart RAM',
    '記録を正しくセーブできませんでした。': 'Save failed',
    '記録のロードが終りました。': 'Load complete',
}


# ── 부대정보 화면 라벨 (세션11) ──────────────────────────────────────────
# GMDT 0x016560~ 델리미터({Ff}) 구분 풀. GAME→ASC16CG 렌더(장군화면 防御力과 다른 사본).
# 索敵力→색적력만 새 음절(색), 나머지 9개는 기존 음절(무료). '은' 확보로 색 자리 확보.
# ⚠️길이 ≤ 원문(델리미터 바로 붙어 널패딩 없음). 유닛 타입값(偵察車 등)은 별도 영문화.
UNITINFO = {
    '兵器タイプ': '병기타입',
    '移動タイプ': '이동타입',
    '移動力':     '이동력',
    '索敵力':     '색적력',
    '武装変更':   '무장변경',   # ★武装보다 길어 longest-first로 먼저 매칭
    '武装':       '무장',
    '防御力':     '방어력',
    '兵器表示':   '무기보기',
    '将軍修正':   '장군수정',
    '将軍能力':   '장군능력',
}


# ── 설정화면 라벨 (세션11) ────────────────────────────────────────────────
# GMDT 0x025be0~0x025d20 델리미터풀(4글리프 필드가 대부분). 값 1~4/BGM/GP/VP는 유지.
# ★예산: 신규 7음절(귀·맹·설·악·조·환·효). 확보 7 = 4의역(명·으·큰·거) + 격추수(파) + 훈장일람→Medals(훈·람).
# ⚠️필드 4글리프라 MUSIC(5)/Control(7) 불가 → 音響효과=SE·面=Stage(cap5)만 영문, 操作/音楽은 한글(4글리프 fit).
SETTINGS = {}  # B안: 설정화면 일본어 복귀(예산 확보). 한글본은 archive 참조.
