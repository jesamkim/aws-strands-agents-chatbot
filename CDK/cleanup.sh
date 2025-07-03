#!/bin/bash

echo "========================================"
echo "AWS 리소스 정리"
echo "========================================"

echo ""
echo "⚠️  경고: 이 스크립트는 배포된 모든 AWS 리소스를 삭제합니다."
echo "계속하기 전에 중요한 데이터를 백업했는지 확인하세요."
echo ""

read -p "정말로 모든 리소스를 삭제하시겠습니까? (yes/no): " CONFIRM

if [[ $CONFIRM == "yes" ]]; then
    echo ""
    echo "1. CDK 스택 삭제 중..."
    cdk destroy --force
    
    echo ""
    echo "2. ECR 이미지 정리 (선택사항)..."
    read -p "ECR 리포지토리의 이미지도 삭제하시겠습니까? (y/N): " DELETE_ECR
    
    if [[ $DELETE_ECR == "y" || $DELETE_ECR == "Y" ]]; then
        echo "ECR 이미지 삭제 중..."
        # ECR 리포지토리 이름 확인 후 삭제
        aws ecr describe-repositories --query 'repositories[?contains(repositoryName, `aws-strands-react-chatbot`)].repositoryName' --output text | while read repo; do
            if [ ! -z "$repo" ]; then
                echo "ECR 리포지토리 삭제: $repo"
                aws ecr delete-repository --repository-name "$repo" --force
            fi
        done
    fi
    
    echo ""
    echo "========================================"
    echo "정리 완료!"
    echo "========================================"
else
    echo "정리가 취소되었습니다."
fi
