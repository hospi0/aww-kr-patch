# -*- coding: utf-8 -*-
"""`/ITMSN` 압축 = **Philip Gage 의 BPE(Byte Pair Encoding)** — 디코더/인코더.

⚠️LZ 가 아니라 **바이트쌍 사전** 방식이다. LZ 로 가정하고 파싱하면 끝없이 헤맨다.
세션20 에 해독·전수 검증(254개 중 253/253 왕복 무손실)했으나 도구를 스크래치패드에
두고 프로젝트에 옮기지 않아 잃었다 → 세션21 재구현. **여기(tools/)에 둔다.**

포맷 (실측 확정, Gage 원본 그대로):
```
블록 반복:
  페어 사전 (c = 0..255):
     count = 다음바이트
     count > 127 → c += count-127, count = 0     (그만큼 항등으로 건너뜀)
     c == 256 → 사전 끝
     i = 0..count:  left[c] = 다음바이트
                    left[c] != c 이면 right[c] = 다음바이트   ← 자기참조는 right 생략
  블록크기 = 빅엔디언 16비트
  확장 = 스택에 left/right 를 밀어가며 재귀, left[c]==c 면 리터럴 출력
```
파라미터 실측: **BLOCKSIZE=5000, MAXCHARS=200, THRESHOLD=3** (전부 Gage 기본값).
블록이 5000보다 짧게 끊기는 것은 「블록 안 서로 다른 바이트 수가 200 에 닿으면
조기 종료」하기 때문이다.

→ [[reference_aww_bpe_codec]]
"""
import collections
import hashlib
import os

BLOCKSIZE = 5000
MAXCHARS = 200
THRESHOLD = 3


MAX_OUT = 8 << 20          # 8MB — 게임 최대 파일(세계지도)이 131KB 라 넉넉하다
MAX_STACK = 4096           # 사전 체인 깊이는 최대 255 여야 정상


class BpeError(ValueError):
    """망가진 스트림(순환 참조·크기 폭주)을 **즉시** 실패로 만든다."""


def decompress(data, max_out=MAX_OUT, max_stack=MAX_STACK):
    """BPE 스트림 전체를 푼다.

    ★★상한이 **안전장치가 아니라 필수**다 — 세션21 인코더가 사전에 순환 참조를
      만들었을 때 이 함수가 **무한 루프 + 메모리 27.8GB**(2시간 방치 후 강제 종료)
      까지 갔다. 잘못된 데이터는 폭주하지 말고 BpeError 로 즉시 죽어야 한다.
    """
    out = bytearray()
    p = 0
    n = len(data)
    while p < n:
        left = list(range(256))
        right = [0] * 256
        count = data[p]
        p += 1
        c = 0
        while True:
            if count > 127:                     # 항등 구간 건너뛰기
                c += count - 127
                count = 0
            if c >= 256:
                break
            for _ in range(count + 1):
                if c >= 256:
                    break
                left[c] = data[p]
                p += 1
                if c != left[c]:
                    right[c] = data[p]
                    p += 1
                c += 1
            if c >= 256 or p >= n:
                break
            count = data[p]
            p += 1
        if p + 1 >= n:
            break
        size = (data[p] << 8) | data[p + 1]
        p += 2
        stack = []
        left_ = left
        while True:
            if stack:
                c = stack.pop()
            else:
                if size == 0:
                    break
                size -= 1
                if p >= n:
                    break
                c = data[p]
                p += 1
            if c == left_[c]:
                out.append(c)
                if len(out) > max_out:
                    raise BpeError('출력 %d바이트 초과 — 사전이 망가졌다(순환 참조?)'
                                   % max_out)
            else:
                stack.append(right[c])
                stack.append(left_[c])
                if len(stack) > max_stack:
                    raise BpeError('전개 스택 깊이 %d 초과 — 사전 순환 참조'
                                   % max_stack)
    return bytes(out)


def serialize_dict(left, right, gap_inline=1):
    """사전을 **디코더 규칙의 정확한 역순**으로 직렬화한다.

    🐞🐞세션21 인코더가 망가진 지점이 바로 여기다. 디코더는 이렇게 읽는다:

        count = 다음바이트
        count > 127 →  c += count-127 ;  count = 0     ← 항등 구간 건너뛰기
        c >= 256 → 끝
        for i in 0..count:  left[c] 읽기, (c != left[c] 면 right[c] 도)  ; c += 1
        c >= 256 → 끝, 아니면 count 를 **다시** 읽는다

    ★★핵심 = **건너뛰기 바이트 뒤에는 길이 바이트가 없다.** `count=0` 이 되므로
      페어가 **정확히 1개** 곧바로 따라온다. 세션21 판은 건너뛰기 뒤에 길이 바이트를
      또 썼고, 디코더는 그 길이 바이트를 left 로 오독했다 ⇒ 사전에 **순환 참조**가
      생겨 전개가 무한 루프(메모리 27.8GB)로 갔다.

    비용 계산(항등 원소를 어떻게 처리할지):
      · 페어 런 안에 그냥 두면  = 항등 1칸당 **1바이트**
      · 건너뛰기로 처리하면     = 건너뛰기 1B + 강제 페어 1개 + 다음 count 1B
    ⇒ 탁상 계산으로는 「3칸 이상일 때만 건너뛰기가 이득」이지만, **실측은 반대다**
      ⇒ **기본값 1** — 원본 사전 661개를 재직렬화해 맞춰 본 결과가 근거다:
      gap_inline 0/1/2 → 바이트 동일 25.7% / **57.6%** / 15.4%, 길이차 합
      +789 / **+82** / +223. 즉 게임 인코더는 「빈칸 1개는 런에 포함, 2개부터
      건너뛰기」다(런은 128칸에서 끊고, 항등이 껴 있어도 이어붙인다). 추정 말고 쟀다.
    """
    out = bytearray()
    c = 0
    while c < 256:
        run = 0
        while c + run < 256 and left[c + run] == c + run:
            run += 1
        if run > gap_inline:
            skip = min(run, 128)            # count 최대 255 → 건너뛰기 최대 128
            out.append(127 + skip)
            c += skip
            if c >= 256:
                break
            # ★건너뛰기 직후에는 **길이 바이트 없이** 페어가 딱 1개 온다
            out.append(left[c])
            if left[c] != c:
                out.append(right[c])
            c += 1
            continue
        # 페어 런 — 최대 128개. 짧은 항등 빈칸(gap_inline 이하)은 런에 포함한다.
        L = 1
        while c + L < 256 and L < 128:
            if left[c + L] != c + L:
                L += 1
                continue
            k = L
            while c + k < 256 and left[c + k] == c + k:
                k += 1
            if k - L > gap_inline or c + k >= 256:
                break
            L = k
        out.append(L - 1)
        for i in range(L):
            out.append(left[c + i])
            if left[c + i] != c + i:
                out.append(right[c + i])
        c += L
    return bytes(out)


def _compress_block(buf, maxchars, threshold, gap_inline=1):
    """한 블록을 Gage 방식으로 압축해 (사전+크기+데이터) 바이트열을 만든다.

    ⚠️쌍 세기를 파이썬 Counter 로 하면 78KB 한 장에 15분+ 가 걸린다(실측 timeout).
      **numpy bincount** 로 바꾸면 같은 결과를 수십 배 빠르게 얻는다.
    """
    import numpy as np
    data = np.frombuffer(bytes(buf), dtype=np.uint8).astype(np.int32)
    left = list(range(256))
    right = [0] * 256
    used = [False] * 256
    for b in set(data.tolist()):
        used[b] = True

    # 🐞🐞`maxchars` 는 **블록을 끊는 기준**이지 치환 횟수 상한이 아니다.
    #   이전 판은 `while nchars < maxchars` 로 묶어, 고유 바이트가 146개인
    #   지도 블록에서 치환을 54번밖에 못 해 **원본보다 12KB 커졌다**.
    #   원본 게임 블록은 페어 코드를 **110개**까지 쓴다(=빈 코드를 전부 쓴다).
    #   ⇒ 조건은 「빈 코드가 있는 동안 + 최빈 쌍이 threshold 이상」이다.
    while data.size >= 2:
        pairs = (data[:-1] << 8) | data[1:]
        cnt = np.bincount(pairs, minlength=65536)
        idx = int(cnt.argmax())
        best = int(cnt[idx])
        if best < threshold:
            break
        bl, br = idx >> 8, idx & 0xFF
        try:
            code = used.index(False)
        except ValueError:
            break
        used[code] = True
        left[code], right[code] = bl, br
        # 치환 — 겹치지 않게 왼쪽부터(Gage 원본과 같은 순서)
        d = data.tolist()
        new = []
        i, L = 0, len(d)
        while i < L:
            if i + 1 < L and d[i] == bl and d[i + 1] == br:
                new.append(code)
                i += 2
            else:
                new.append(d[i])
                i += 1
        data = np.array(new, dtype=np.int32)
    data = data.tolist()

    out = bytearray(serialize_dict(left, right, gap_inline))
    out.append((len(data) >> 8) & 0xFF)
    out.append(len(data) & 0xFF)
    out += bytes(data)
    return bytes(out)


def _noop_block(size):
    """**출력이 0바이트인 정식 블록**을 정확히 `size` 바이트로 만든다 (5~258).

    사전은 c 를 256까지 밀고 끝내고, 블록 크기 필드는 0 이다 ⇒ 전개 결과가 안 늘어난다.
    뼈대는 `건너뛰기(k) + 강제 엔트리` 라운드 m 번 + 마지막 건너뛰기 1번:
      길이 = 2m + 1 + p + 2   (p=1 이면 엔트리 하나를 페어로 써서 1바이트 늘린다)
    """
    d = size - 2                              # 사전 바이트 수
    if d < 3 or d > 256:
        raise ValueError('종료 블록 크기 범위 밖: %d' % size)
    p = 1 - (d % 2)                           # 짝수면 페어 엔트리 1개로 홀짝 맞춤
    m = (d - 1 - p) // 2                      # 라운드 수
    total = 256 - m                           # 건너뛰기 합 (엔트리 m 개가 m 칸 전진)
    slots = m + 1
    ks = []
    for i in range(slots):
        left_slots = slots - i - 1
        k = max(1, min(128, total - left_slots))
        ks.append(k)
        total -= k
    assert total == 0 and all(1 <= k <= 128 for k in ks)
    out = bytearray()
    c = 0
    for i in range(m):
        out.append(127 + ks[i])
        c += ks[i]
        if i < p:                             # 페어 엔트리(1바이트 더 먹는다)
            out.append((c + 1) & 0xFF)
            out.append(0)
        else:                                 # 항등 엔트리
            out.append(c & 0xFF)
        c += 1
    out.append(127 + ks[m])
    c += ks[m]
    assert c == 256 and len(out) == d, (c, len(out), d)
    out += b'\x00\x00'                        # 블록 크기 0
    return bytes(out)


def padding(n):
    """압축본 뒤 남는 `n` 바이트를 **디코더가 안전하게 먹는 종료 블록들**로 채운다.

    🐞🐞원본 꼬리를 그대로 두거나 0 으로 채우면 안 된다. BPE 스트림에는 종료
      표시가 없어서 디코더가 꼬리를 **다음 블록으로 계속 읽는다** — 이 세션에
      CGMMPO 가 78,848B 대신 82,657B 로 전개되고 CGMMFR 은 사전 순환 참조로
      죽었다. 0 패딩도 안전하지 않다(잘린 사전을 읽다 범위를 벗어난다).
    """
    if n == 0:
        return b''
    if n < 5:
        raise ValueError('남는 공간 %d바이트로는 종료 블록을 못 만든다' % n)
    out = bytearray()
    while n:
        s = min(258, n)
        if 0 < n - s < 5:
            s -= 5
        out += _noop_block(s)
        n -= s
    return bytes(out)


def split_blocks(raw, blocksize=BLOCKSIZE, maxchars=MAXCHARS):
    """블록을 **게이지 원본과 같은 규칙**으로 끊는다.

    한 블록은 `blocksize` 바이트까지 담되, **서로 다른 바이트가 maxchars 에 닿으면
    거기서 끊는다.** 이래야 사전에 쓸 **빈 코드가 최소 56개** 남는다 — 다양한
    이미지에서 블록이 5000보다 짧게 끊기는 게 이 규칙 때문이다(원본 실측).
    """
    out = []
    i, n = 0, len(raw)
    while i < n:
        seen = set()
        j = i
        while j < n and j - i < blocksize:
            if raw[j] not in seen:
                if len(seen) >= maxchars:
                    break
                seen.add(raw[j])
            j += 1
        out.append(raw[i:j])
        i = j
    return out


def compress(raw, blocksize=BLOCKSIZE, maxchars=MAXCHARS, threshold=THRESHOLD,
             gap_inline=1):
    out = bytearray()
    for blk in split_blocks(raw, blocksize, maxchars):
        out += _compress_block(blk, maxchars, threshold, gap_inline)
    return bytes(out)


CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'work', 'bpecache')


def compress_cached(raw, blocksize=BLOCKSIZE, maxchars=MAXCHARS,
                    threshold=THRESHOLD, gap_inline=1):
    """압축 결과를 **입력 해시로 캐시**한다.

    이 인코더는 78KB 한 장에 수십 분이 걸린다. 지명을 안 바꾸면 결과가 같으므로
    한 번 만든 것을 재사용한다(내용이 바뀌면 해시가 달라져 자동으로 다시 압축).
    캐시는 되읽기 검증(전개 == 원본)까지 통과한 것만 쓴다.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = '%s_%d_%d_%d_%d.bpe' % (hashlib.sha1(raw).hexdigest()[:16],
                                  blocksize, maxchars, threshold, gap_inline)
    path = os.path.join(CACHE_DIR, key)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            c = f.read()
        if decompress(c) == raw:
            return c, True
    c = compress(raw, blocksize, maxchars, threshold, gap_inline)
    if decompress(c) == raw:
        with open(path, 'wb') as f:
            f.write(c)
    return c, False


def compress_fit(raw, limit):
    """원본 크기(limit) 안에 들어가는 결과를 찾는다.

    세션20 실측: 250개는 1차(5000,200,3)에서 통과하고, 초과하는 3건은
    (8192, th=2) → (4096, th=3) 순 재시도로 해결됐다.
    """
    best = None
    for bs, th, gi in ((BLOCKSIZE, THRESHOLD, 1), (BLOCKSIZE, THRESHOLD, 0),
                       (8192, 2, 1), (8192, 2, 0), (4096, 3, 1), (2048, 2, 1)):
        c, hit = compress_cached(raw, bs, MAXCHARS, th, gi)
        if best is None or len(c) < len(best[0]):
            best = (c, (bs, th, gi, 'cache' if hit else 'new'))
        # ★남는 공간이 1~4바이트면 **종료 블록을 못 만든다** ⇒ 다른 파라미터로.
        if len(c) <= limit and not (0 < limit - len(c) < 5)                 and decompress(c) == raw:
            return c, (bs, th, gi, 'cache' if hit else 'new')
    return None, best
