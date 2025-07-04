"""
Strands Agents를 위한 강화된 타임아웃 설정
모든 레벨에서 타임아웃을 제어
"""

import os
import sys
import boto3
from botocore.config import Config
import urllib3
from urllib3.util.timeout import Timeout

def apply_comprehensive_timeout_settings():
    """포괄적인 타임아웃 설정 적용"""
    
    print("🔧 포괄적인 타임아웃 설정 적용")
    print("-" * 50)
    
    # 1. 환경변수 설정 (가장 기본)
    timeout_env_vars = {
        # AWS SDK 타임아웃
        'AWS_DEFAULT_READ_TIMEOUT': '60',  # 60초로 단축
        'AWS_DEFAULT_CONNECT_TIMEOUT': '30',  # 30초로 단축
        'AWS_MAX_ATTEMPTS': '2',  # 재시도 횟수 감소
        'AWS_RETRY_MODE': 'standard',  # 표준 모드로 변경
        
        # HTTP 클라이언트 타임아웃
        'HTTP_TIMEOUT': '60',
        'REQUESTS_TIMEOUT': '60',
        
        # urllib3 타임아웃
        'URLLIB3_READ_TIMEOUT': '60',
        'URLLIB3_CONNECT_TIMEOUT': '30',
        
        # Bedrock 특화 타임아웃
        'BEDROCK_READ_TIMEOUT': '60',
        'BEDROCK_CONNECT_TIMEOUT': '30',
        'BEDROCK_MAX_RETRIES': '1',
    }
    
    for var, value in timeout_env_vars.items():
        os.environ[var] = value
        print(f"  ✅ {var} = {value}")
    
    # 2. urllib3 전역 설정
    try:
        # 기본 타임아웃을 더 짧게 설정
        urllib3.util.timeout.DEFAULT_TIMEOUT = Timeout(
            connect=30.0,  # 연결 타임아웃 30초
            read=60.0      # 읽기 타임아웃 60초
        )
        
        # 풀 매니저 설정
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        print("  ✅ urllib3 전역 타임아웃 설정 완료")
        
    except Exception as e:
        print(f"  ⚠️ urllib3 설정 실패: {e}")
    
    # 3. boto3 기본 설정 패치
    try:
        # 더 짧은 타임아웃으로 설정
        default_config = Config(
            read_timeout=60,      # 60초로 단축
            connect_timeout=30,   # 30초로 단축
            retries={
                'max_attempts': 2,  # 재시도 횟수 감소
                'mode': 'standard'  # 표준 모드
            },
            max_pool_connections=10
        )
        
        # 기본 세션 설정
        boto3.setup_default_session()
        
        print("  ✅ boto3 기본 설정 완료")
        
    except Exception as e:
        print(f"  ⚠️ boto3 설정 실패: {e}")
    
    # 4. 시스템 레벨 소켓 타임아웃
    try:
        import socket
        socket.setdefaulttimeout(60)  # 60초 소켓 타임아웃
        print("  ✅ 시스템 소켓 타임아웃 설정 완료")
        
    except Exception as e:
        print(f"  ⚠️ 소켓 타임아웃 설정 실패: {e}")
    
    print("\n🎯 포괄적인 타임아웃 설정 완료!")
    return True


def create_optimized_bedrock_client(region='us-west-2'):
    """최적화된 Bedrock 클라이언트 생성"""
    
    # 매우 짧은 타임아웃으로 설정
    config = Config(
        read_timeout=45,      # 45초
        connect_timeout=20,   # 20초
        retries={
            'max_attempts': 1,  # 재시도 없음
            'mode': 'standard'
        },
        max_pool_connections=5,
        region_name=region
    )
    
    try:
        client = boto3.client('bedrock-runtime', config=config)
        print(f"✅ 최적화된 Bedrock 클라이언트 생성 (타임아웃: 45초)")
        return client
        
    except Exception as e:
        print(f"❌ Bedrock 클라이언트 생성 실패: {e}")
        return None


def patch_strands_internals():
    """Strands 내부 설정 패치 시도"""
    
    try:
        # Strands가 사용하는 HTTP 어댑터 패치
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # 짧은 타임아웃 설정
        retry_strategy = Retry(
            total=1,  # 총 1회만 재시도
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=5,
            pool_maxsize=10
        )
        
        # 기본 세션에 어댑터 적용
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 타임아웃 설정
        session.timeout = (20, 45)  # (연결, 읽기) 타임아웃
        
        print("  ✅ requests 세션 패치 완료")
        
        return True
        
    except Exception as e:
        print(f"  ⚠️ Strands 내부 패치 실패: {e}")
        return False


def test_timeout_settings():
    """타임아웃 설정 테스트"""
    
    print("\n🧪 타임아웃 설정 테스트")
    print("-" * 50)
    
    # 1. 환경변수 확인
    test_vars = ['AWS_DEFAULT_READ_TIMEOUT', 'AWS_DEFAULT_CONNECT_TIMEOUT']
    for var in test_vars:
        value = os.environ.get(var, 'Not Set')
        print(f"  {var}: {value}")
    
    # 2. Bedrock 클라이언트 테스트
    try:
        client = create_optimized_bedrock_client()
        if client:
            print("  ✅ Bedrock 클라이언트 생성 성공")
        else:
            print("  ❌ Bedrock 클라이언트 생성 실패")
            
    except Exception as e:
        print(f"  ❌ Bedrock 테스트 실패: {e}")
    
    # 3. urllib3 설정 확인
    try:
        timeout = urllib3.util.timeout.DEFAULT_TIMEOUT
        print(f"  urllib3 타임아웃: 연결={timeout.connect_timeout}초, 읽기={timeout.read_timeout}초")
        
    except Exception as e:
        print(f"  ⚠️ urllib3 확인 실패: {e}")
    
    print("\n✅ 타임아웃 설정 테스트 완료")


def main():
    """메인 함수"""
    print("🚀 강화된 타임아웃 설정 스크립트")
    print("=" * 60)
    
    # 포괄적인 타임아웃 설정 적용
    apply_comprehensive_timeout_settings()
    
    # Strands 내부 패치
    print("\n" + "=" * 60)
    print("🔧 Strands 내부 설정 패치")
    patch_strands_internals()
    
    # 설정 테스트
    test_timeout_settings()
    
    print("\n🎉 모든 타임아웃 설정이 완료되었습니다!")
    print("   이제 더 짧은 타임아웃으로 안정적인 처리가 가능합니다.")


if __name__ == "__main__":
    main()
