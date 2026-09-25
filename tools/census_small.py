"""소형 8x8 폰트 텍스트 전수 추출 + 한글 수요 / 로마자 대상 실측.

대상 테이블:
  무기명    GMDT 0x74c4  rec 0~180   (한글 대상)
  지형·시설 GMDT 0x74c4  rec 181~191 (한글 대상)
  지명      GMDT 0x74c4  rec 192~436 (로마자 대상)
  유닛명    MUSEUM 0x7e3c2 stride 0x52 × 645  이름=선두 8B (로마자 대상)
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smallfont as sf
from translit import translit

EXTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'work', 'extract')


def load(n):
    with open(os.path.join(EXTRACT, n), 'rb') as f:
        return f.read()


def rec(buf, off, n=8):
    return sf.decode(buf, off, n, stop=False).rstrip('\x00 ').replace('\x00', '')


def dump_table(buf, off, count, stride=8):
    return [rec(buf, off + i * stride, 8) for i in range(count)]


def hangul_syllables(strings):
    s = set()
    for t in strings:
        for ch in t:
            if '가' <= ch <= '힣':
                s.add(ch)
    return s


def main():
    gmdt = load('GMDT')
    museum = load('MUSEUM')

    weapons = dump_table(gmdt, 0x74c4, 181)
    terrain = dump_table(gmdt, 0x74c4 + 181 * 8, 11)   # 181~191
    places = dump_table(gmdt, 0x74c4 + 192 * 8, 437 - 192)  # 192~436
    units = dump_table(museum, 0x7e3c2, 645, 0x52)

    print('무기명 181개 (한글 대상):')
    for i, w in enumerate(weapons):
        print('  %3d  %s' % (i, w))
    print('\n지형·시설 11개 (한글 대상):')
    for i, t in enumerate(terrain):
        print('  %3d  %s' % (181 + i, t))

    print('\n지명 %d개 (로마자 대상) — 앞 40개 표본:' % len(places))
    for i, p in enumerate(places[:40]):
        print('  %3d  %-10s -> 음차 %s' % (192 + i, p, translit(p)))

    print('\n유닛명 645개 (로마자 대상) — 앞 40개 표본:')
    for i, u in enumerate(units[:40]):
        print('  %3d  %-10s -> 음차 %s' % (i, u, translit(u)))

    # ----- 수요/공급 -----
    print('\n' + '=' * 60)
    hz_wt = hangul_syllables([translit(x) for x in weapons + terrain])  # 음차 기준(추정)
    print('무기+지형 음차시 고유 한글 음절: %d종' % len(hz_wt))

    # 가나 사용 현황: 각 범주가 쓰는 가나 글리프 인덱스
    def kana_idx(strings):
        s = set()
        for t in strings:
            for ch in t:
                k = sf.REV.get(ch)
                if k is not None and 63 <= k <= 143:  # 가나 영역
                    s.add(k)
        return s

    kw = kana_idx(weapons + terrain)
    ku = kana_idx(units)
    kp = kana_idx(places)
    all_kana = kw | ku | kp
    print('가나 글리프 사용: 무기+지형 %d, 유닛 %d, 지명 %d, 합집합 %d/81'
          % (len(kw), len(ku), len(kp), len(all_kana)))
    # 유닛·지명을 로마자화하면 그들이 쓰던 가나 중, 무기+지형이 안 쓰는 것이 해방
    freed = (ku | kp) - kw
    print('유닛+지명 로마자화 시 해방되는 가나 슬롯: %d칸' % len(freed))
    print('  (무기+지형이 계속 쓰는 가나 %d칸은 남겨야 함)' % len(kw))

    # 로마자 길이 초과 검사 (8칸 고정폭)
    over_u = [(i, u, translit(u)) for i, u in enumerate(units)]
    print('\n로마자 8칸 제약: 유닛명 음차 최대 길이 %d, 지명 음차 최대 길이 %d'
          % (max(len(translit(u)) for u in units), max(len(translit(p)) for p in places)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
