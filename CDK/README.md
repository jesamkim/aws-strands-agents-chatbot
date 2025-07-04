# 🚀 AWS Bedrock ReAct Chatbot - CDK Deployment

이 디렉토리는 AWS CDK를 사용하여 AWS Bedrock ReAct Chatbot을 AWS 클라우드에 배포하기 위한 인프라 코드를 포함합니다.

## 🏗️ 배포 아키텍처

```
Internet → CloudFront → ALB → ECS Fargate → Streamlit App
                                ↓
                        Amazon Bedrock (Claude, Nova Models)
                                ↓
                        Knowledge Base (Optional)
```

### 주요 구성 요소

- **ECS Fargate**: 컨테이너화된 Streamlit 애플리케이션 실행
- **Application Load Balancer (ALB)**: 트래픽 분산 및 헬스체크
- **CloudFront**: CDN을 통한 글로벌 배포 및 보안 강화
- **VPC**: 격리된 네트워크 환경
- **IAM Roles**: Bedrock 및 Knowledge Base 접근 권한

## 📋 사전 요구사항

### 1. 개발 환경
- **Python**: 3.10 이상 (AWS Strands Agents 필수 요구사항)
- **Node.js**: 18.x 이상 (CDK CLI용)
- **AWS CLI**: 최신 버전
- **Docker**: 컨테이너 빌드용

### 2. AWS 계정 설정
- AWS 계정 및 적절한 권한
- AWS CLI 자격 증명 구성
- Amazon Bedrock 모델 접근 권한
  - Claude 3.5 Haiku (필수)
  - Claude 3.5 Sonnet, Nova Lite/Micro (권장)

### 3. CDK 설치
```bash
npm install -g aws-cdk
```

## 🛠️ 배포 단계

### 1. 의존성 설치
```bash
cd CDK
pip install -r requirements.txt
```

### 2. CDK 부트스트랩 (최초 1회만)
```bash
cdk bootstrap
```

### 3. 설정 확인 및 수정
`docker_app/config_file.py`에서 스택 이름과 보안 헤더 값을 확인하세요:

```python
class Config:
    STACK_NAME = "aws-strands-react-chatbot"  # 원하는 스택 이름으로 변경
    CUSTOM_HEADER_VALUE = "ReAct_Chatbot_Security_Header_2024"  # 보안을 위한 랜덤 값
```

### 4. 배포 미리보기
```bash
cdk diff
```

### 5. 배포 실행
```bash
cdk deploy
```

배포 완료 후 CloudFront URL이 출력됩니다:
```
Outputs:
aws-strands-react-chatbot.CloudFrontDistributionURL = https://d1234567890abc.cloudfront.net
```

## 🔧 배포 후 설정

### 1. 애플리케이션 접속
배포 완료 후 출력된 CloudFront URL로 접속하여 애플리케이션을 확인합니다.

### 2. Knowledge Base 설정 (선택사항)
- AWS 콘솔에서 Bedrock Knowledge Base를 생성
- 애플리케이션 사이드바에서 Knowledge Base ID 입력

### 3. 모델 권한 확인
AWS 콘솔 → Bedrock → Model access에서 필요한 모델들이 활성화되어 있는지 확인:
- Claude 3.5 Haiku
- Claude 3.5 Sonnet v2
- Claude 3.7 Sonnet
- Nova Lite
- Nova Micro

## 📊 리소스 사양

### ECS Fargate 태스크
- **CPU**: 2 vCPU (2048 CPU units)
- **메모리**: 4GB (4096 MiB)
- **포트**: 8501 (Streamlit 기본 포트)

### 네트워크 구성
- **VPC CIDR**: 10.0.0.0/16
- **가용 영역**: 2개
- **NAT 게이트웨이**: 1개
- **보안 그룹**: ECS 및 ALB용 별도 구성

### 비용 최적화
- **NAT 게이트웨이**: 1개만 사용 (비용 절약)
- **ECS 배포**: 50% 최소 정상 상태 유지
- **CloudFront**: 캐싱 비활성화 (동적 콘텐츠)

## 🛡️ 보안 기능

### 1. CloudFront 보안
- HTTPS 리디렉션 강제
- 커스텀 헤더를 통한 ALB 직접 접근 차단

### 2. 네트워크 보안
- ECS 태스크는 프라이빗 서브넷에 배치
- 필요한 포트만 개방 (8501, 443)
- 보안 그룹을 통한 트래픽 제어

### 3. IAM 권한
- 최소 권한 원칙 적용
- Bedrock 및 Knowledge Base 접근만 허용

## 🔍 모니터링 및 로깅

### CloudWatch 로그
ECS 태스크의 로그는 CloudWatch Logs에 자동으로 전송됩니다:
- 로그 그룹: `/aws/ecs/ReactChatbotLogs`

### 헬스체크
- ALB 헬스체크: 30초 간격
- 경로: `/`
- 정상 응답 코드: 200

## 🚨 문제 해결

### 1. 배포 실패
```bash
# 스택 상태 확인
aws cloudformation describe-stacks --stack-name aws-strands-react-chatbot

# 이벤트 로그 확인
aws cloudformation describe-stack-events --stack-name aws-strands-react-chatbot
```

### 2. 컨테이너 시작 실패
```bash
# ECS 태스크 로그 확인
aws logs describe-log-groups --log-group-name-prefix "/aws/ecs/ReactChatbotLogs"
```

### 3. Bedrock 권한 오류
- AWS 콘솔에서 Bedrock 모델 접근 권한 확인
- IAM 역할의 정책 확인

### 4. 애플리케이션 접속 불가
- CloudFront 배포 상태 확인 (완료까지 15-20분 소요)
- ALB 타겟 그룹 헬스체크 상태 확인

## 🗑️ 리소스 정리

배포된 리소스를 삭제하려면:

```bash
cdk destroy
```

> ⚠️ **주의**: 이 명령은 모든 리소스를 삭제합니다. 데이터 백업이 필요한 경우 미리 수행하세요.

## 📈 성능 최적화

### 1. 스케일링
현재 설정은 단일 태스크로 구성되어 있습니다. 트래픽 증가 시 Auto Scaling을 추가할 수 있습니다.

### 2. 캐싱
정적 리소스에 대해서는 CloudFront 캐싱을 활성화할 수 있습니다.

### 3. 리전 선택
사용자와 가까운 리전에 배포하여 지연 시간을 최소화하세요.

## 🔗 관련 문서

- [AWS CDK 개발자 가이드](https://docs.aws.amazon.com/cdk/v2/guide/)
- [Amazon ECS 사용자 가이드](https://docs.aws.amazon.com/AmazonECS/latest/userguide/)
- [Amazon Bedrock 사용자 가이드](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [AWS CloudFront 개발자 가이드](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/)

---

배포 관련 문의사항이나 문제가 있으시면 GitHub Issues를 통해 문의해 주세요.
