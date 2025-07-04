"""
AWS Bedrock 기반 ReAct 챗봇 메인 애플리케이션
Strands Agents 및 Legacy ReAct 시스템 지원
"""

import streamlit as st
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 강화된 타임아웃 설정을 가장 먼저 적용
print("🔧 강화된 타임아웃 설정 적용 중...")

# 1. 환경변수 기반 타임아웃 설정 (더 짧게)
os.environ['AWS_DEFAULT_READ_TIMEOUT'] = '60'      # 60초로 단축
os.environ['AWS_DEFAULT_CONNECT_TIMEOUT'] = '30'   # 30초로 단축
os.environ['AWS_MAX_ATTEMPTS'] = '2'               # 재시도 횟수 감소
os.environ['AWS_RETRY_MODE'] = 'standard'          # 표준 모드

# 2. urllib3 타임아웃 패치 (더 짧게)
try:
    import urllib3
    from urllib3.util.timeout import Timeout
    urllib3.util.timeout.DEFAULT_TIMEOUT = Timeout(connect=30.0, read=60.0)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("✅ urllib3 타임아웃 패치 완료 (연결: 30초, 읽기: 60초)")
except Exception as e:
    print(f"⚠️ urllib3 패치 실패: {e}")

# 3. boto3 기본 설정 패치 (더 짧게)
try:
    import boto3
    from botocore.config import Config
    
    default_config = Config(
        read_timeout=60,      # 60초로 단축
        connect_timeout=30,   # 30초로 단축
        retries={'max_attempts': 2, 'mode': 'standard'},  # 재시도 감소
        max_pool_connections=5
    )
    
    print("✅ boto3 타임아웃 설정 완료 (연결: 30초, 읽기: 60초)")
except Exception as e:
    print(f"⚠️ boto3 설정 실패: {e}")

# 4. 시스템 소켓 타임아웃
try:
    import socket
    socket.setdefaulttimeout(60)  # 60초
    print("✅ 시스템 소켓 타임아웃 설정 완료 (60초)")
except Exception as e:
    print(f"⚠️ 소켓 타임아웃 설정 실패: {e}")

# 5. requests 세션 패치
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    retry_strategy = Retry(
        total=1,  # 1회만 재시도
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = (20, 45)  # (연결, 읽기) 타임아웃
    
    print("✅ requests 세션 패치 완료 (연결: 20초, 읽기: 45초)")
except Exception as e:
    print(f"⚠️ requests 패치 실패: {e}")

from ui.sidebar import render_sidebar
from ui.chat import render_chat_interface
from utils.config import AgentConfig


def main():
    """메인 애플리케이션 함수"""
    
    # 페이지 설정
    st.set_page_config(
        page_title="ReAct Agent Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 시스템 선택 헤더
    _render_system_header()
    
    # 사이드바 렌더링 및 설정 가져오기
    config = render_sidebar()
    
    # 메인 채팅 인터페이스
    render_chat_interface(config)
    
    # 하단 정보
    _render_footer()


def _render_system_header():
    """시스템 선택 헤더"""
    st.title("🤖 AWS Bedrock ReAct Chatbot")
    
    # 시스템 선택
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown("### 🚀 **Strands Agents** + Legacy ReAct 지원")
    
    with col2:
        # 시스템 선택 (세션 상태로 관리)
        if 'use_strands' not in st.session_state:
            st.session_state.use_strands = True
        
        system_choice = st.selectbox(
            "시스템 선택",
            options=["Strands Agents", "Legacy ReAct"],
            index=0 if st.session_state.use_strands else 1,
            key="system_selector"
        )
        
        st.session_state.use_strands = (system_choice == "Strands Agents")
    
    with col3:
        # 시스템 상태 표시
        if st.session_state.use_strands:
            st.success("🚀 Strands Agents")
        else:
            st.info("🔄 Legacy ReAct")
    
    # 시스템 설명
    if st.session_state.use_strands:
        st.info("""
        **🚀 Strands Agents 모드**
        - AWS 공식 Strands Agents 프레임워크 사용
        - 자동화된 에이전트 오케스트레이션
        - 도구 기반 KB 검색 및 분석
        - 향상된 대화 맥락 인식
        """)
    else:
        st.info("""
        **🔄 Legacy ReAct 모드**
        - 기존 수동 ReAct 패턴 구현
        - 직접 구현한 Orchestration-Action-Observation 루프
        - 안정적이고 검증된 시스템
        """)
    
    st.markdown("---")


def _render_footer():
    """하단 정보 표시"""
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.caption("🔧 **기술 스택**")
        if st.session_state.get('use_strands', True):
            st.caption("• AWS Strands Agents")
            st.caption("• Agent Graph Topology")
        else:
            st.caption("• Custom ReAct Pattern")
            st.caption("• Manual Orchestration")
        st.caption("• Amazon Bedrock")
        st.caption("• Streamlit")
    
    with col2:
        st.caption("🧠 **지원 모델**")
        st.caption("• Claude 4, 3.7, 3.5")
        st.caption("• Nova Lite, Micro")
        st.caption("• 다중 모델 조합")
    
    with col3:
        st.caption("⚡ **ReAct 패턴**")
        if st.session_state.get('use_strands', True):
            st.caption("• Tool-based Orchestration")
            st.caption("• Automated KB Search")
            st.caption("• Citation Generation")
        else:
            st.caption("• Manual Orchestration")
            st.caption("• Direct Action")
            st.caption("• Manual Observation")
    
    with col4:
        st.caption("🎯 **주요 기능**")
        st.caption("• KB 우선순위 검색")
        st.caption("• 대화 맥락 인식")
        st.caption("• Citation 지원")
        st.caption("• 재시도 메커니즘")


if __name__ == "__main__":
    main()
