#!/bin/bash

echo "========================================"
echo "로컬 Docker 테스트"
echo "========================================"

cd docker_app

echo ""
echo "1. Docker 이미지 빌드 중..."
docker build -t react-chatbot:local .

echo ""
echo "2. 컨테이너 실행 중..."
echo "브라우저에서 http://localhost:8501 로 접속하세요."
echo "종료하려면 Ctrl+C를 누르세요."
echo ""

docker run -it --rm \
  -p 8501:8501 \
  -e AWS_REGION=${AWS_REGION:-us-west-2} \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN} \
  -v ~/.aws:/root/.aws:ro \
  react-chatbot:local
