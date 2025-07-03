@echo off
echo ========================================
echo AWS Strands Agents ReAct Chatbot 배포
echo ========================================

echo.
echo 1. Python 가상환경 활성화 중...
python -m venv venv
call venv\Scripts\activate.bat

echo.
echo 2. 의존성 설치 중...
pip install -r requirements.txt

echo.
echo 3. CDK 부트스트랩 확인...
cdk bootstrap

echo.
echo 4. 배포 미리보기...
cdk diff

echo.
echo 5. 배포를 계속하시겠습니까? (y/N)
set /p CONTINUE="계속하려면 'y'를 입력하세요: "

if /i "%CONTINUE%"=="y" (
    echo.
    echo 6. 배포 시작...
    cdk deploy
    echo.
    echo ========================================
    echo 배포 완료!
    echo 출력된 CloudFront URL로 접속하세요.
    echo ========================================
) else (
    echo 배포가 취소되었습니다.
)

pause
