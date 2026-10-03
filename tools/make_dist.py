# -*- coding: utf-8 -*-
r"""어드밴스드 월드 워 배포 묶음 — dist/AdvancedWorldWar_KR_<VER>/ :
   트랙 1 xdelta + xdelta.exe + readme.txt(CP949·CRLF) + 한글패치_적용.bat(CP949·CRLF) + 같은 이름 .zip
검증: 원본 트랙 1 → xdelta 적용 → md5 = 빌드 이미지 md5. 옛 버전 dist 폴더·zip 은 지운다.

v0.91 빌드 절차(2026-10-03):
  1) 원본 + v0.9 xdelta → build/v091/track01_v09.bin (md5 364070B5…)
  2) 복사 → build/v091/track01_v091.bin
     python tools/build_interm_title.py build/v091/track01_v091.bin --write   # 시나리오 타이틀 11장
     python tools/build_chuushi.py      build/v091/track01_v091.bin --write   # 군적 등록 「중지」
     python tools/fix_punct_space.py    build/v091/track01_v091.bin --write   # 문장부호 뒤 공백(제자리)
     python tools/build_exam.py         build/v091/track01_v091.bin --align-only --write   # 시험 숫자 정렬
  3) python tools/make_dist.py
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from isoread import TRACK1

VER = 'v0.91'
XDELTA = r'C:\claude\utils\xdelta.exe'
NAME = 'AdvancedWorldWar_KR_' + VER
BUILT = os.path.join(ROOT, 'build', 'v091', 'track01_v091.bin')
TITLE = '어드밴스드 월드 워 천년제국의 흥망 (세가 새턴 일본판) 한글 패치 ' + VER
ROMNAME = 'Advanced World War - Sennen Teikoku no Koubou - Last of the Millennium (Japan) (Rev B) (22M)'
TRACKS = 24


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 1 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 1 이름으로 바꿔 넣고, 나머지 트랙과 cue 는 그대로 쓰세요
     (트랙 1 크기는 그대로라 cue 는 고칠 필요 없습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 1" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ v0.91 에서 바뀐 것 ]

  - 시나리오 시작 화면의 큰 제목 11장 한글화
    (선전포고 / 서부전선1940 / 배틀오브브리튼 / 북아프리카전선 / 바르바로사 / 서부전선1944 /
     동부전선1945 / 제도붕괴 / 대륙상륙 / 잃어버린시대 / 동부전선)
    원본의 돌에 새긴 질감·검은 테두리·오른쪽 위 조명과 하이라이트를 그대로 살렸습니다.
  - 군적 등록(이름 입력) 화면의 "中止" 버튼 → "중지"
  - 문장부호 뒤 띄어쓰기 삭제(메시지·연표·사관학교 대사·시나리오 문장)
  - 사관학교 실기시험 화면의 제한 턴 값과 득점 "/N" 숫자 줄 오른쪽 맞춤


[ 알려진 점 ]

  - 아직 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 1 파일을 이 폴더에 넣어 주세요^(readme 참고^).
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다^(readme 의 원본md5 확인^).
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    dist = os.path.join(ROOT, 'dist')
    for old in glob.glob(os.path.join(dist, 'AdvancedWorldWar_KR_*')):
        if os.path.basename(old) not in (NAME, NAME + '.zip'):
            (shutil.rmtree if os.path.isdir(old) else os.remove)(old)
            print('옛 버전 삭제:', os.path.basename(old))
    d = os.path.join(dist, NAME)
    os.makedirs(d, exist_ok=True)
    b = ROMNAME + ' (Track 01).bin'
    assert os.path.basename(TRACK1) == b
    patch = NAME + '.xdelta'
    pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-B', str(1 << 29), '-s', TRACK1, BUILT, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-B', str(1 << 29), '-s', TRACK1, pp, chk], check=True)
    o, want, got = md5(TRACK1), md5(BUILT), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track 01) [KR].bin'
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want)
              + BODY.format(bin=b, patch=patch))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    zp = os.path.join(dist, NAME + '.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(d)):
            z.write(os.path.join(d, f), NAME + '/' + f)
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-40s %12d' % (f, os.path.getsize(os.path.join(d, f))))
    print('  zip %s %d B  md5 %s' % (os.path.basename(zp), os.path.getsize(zp), md5(zp)))


if __name__ == '__main__':
    main()
