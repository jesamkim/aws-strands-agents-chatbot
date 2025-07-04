"""
AWS Bedrock 기반 ReAct 챗봇 메인 애플리케이션
"""

import streamlit as st
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    
    # 메인 타이틀
    st.title("🤖 AWS Bedrock ReAct Chatbot")
    st.markdown("---")
    
    # 사이드바 렌더링 및 설정 가져오기
    config = render_sidebar()
    
    # 메인 채팅 인터페이스
    render_chat_interface(config)
    
    # 하단 정보
    _render_footer()


def _render_footer():
    """하단 정보 표시"""
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("🔧 **기술 스택**")
        st.caption("• Custom ReAct Pattern")
        st.caption("• Amazon Bedrock")
        st.caption("• Streamlit")
    
    with col2:
        st.caption("🧠 **지원 모델**")
        st.caption("• Claude 4, 3.7, 3.5")
        st.caption("• Nova Lite, Micro")
    
    with col3:
        st.caption("⚡ **ReAct 패턴**")
        st.caption("• Orchestration")
        st.caption("• Action")
        st.caption("• Observation")


if __name__ == "__main__":
    main()
