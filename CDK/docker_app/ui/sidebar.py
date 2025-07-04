"""
KB 설명 입력이 추가된 Streamlit 사이드바 UI 컴포넌트
"""

import streamlit as st
from typing import Dict, Any

from utils.config import AVAILABLE_MODELS, MODEL_CHARACTERISTICS, AgentConfig
from utils.bedrock_client import BedrockClient
from utils.kb_search import KnowledgeBaseSearcher


def _get_model_name(model_id: str) -> str:
    """모델 ID에서 표시명 추출"""
    for name, id in AVAILABLE_MODELS.items():
        if id == model_id:
            return name
    return model_id.split(':')[0]  # 축약된 형태로 표시


def render_sidebar() -> AgentConfig:
    """
    사이드바 렌더링 및 설정 반환
    
    Returns:
        AgentConfig: 사용자가 설정한 Agent 구성
    """
    st.sidebar.title("🤖 ReAct Agent 설정")
    
    # 모델 선택 섹션
    _render_model_selection()
    
    # 시스템 프롬프트 섹션
    _render_system_prompt()
    
    # Knowledge Base 설정 섹션 (개선됨)
    _render_enhanced_kb_settings()
    
    # 파라미터 설정 섹션
    _render_parameters()
    
    # 연결 테스트 섹션
    _render_connection_tests()
    
    # 대화 리셋 버튼
    _render_reset_button()
    
    # 설정 요약 표시
    _render_config_summary()
    
    return AgentConfig.from_streamlit_session()


def _render_model_selection():
    """모델 선택 UI"""
    st.sidebar.header("🧠 Model Configuration")
    
    # Claude 모델만 (복잡한 추론 필요한 단계용)
    claude_models = [
        "Claude Sonnet 4",
        "Claude 3.7 Sonnet", 
        "Claude 3.5 Sonnet v2",
        "Claude 3.5 Haiku"
    ]
    claude_model_ids = [AVAILABLE_MODELS[name] for name in claude_models]
    
    # 모든 모델 (Action 단계용)
    all_model_names = list(AVAILABLE_MODELS.keys())
    all_model_ids = list(AVAILABLE_MODELS.values())
    
    # Orchestration 모델 (Claude만)
    orchestration_idx = st.sidebar.selectbox(
        "🎯 Orchestration Model",
        range(len(claude_models)),
        format_func=lambda x: claude_models[x],
        index=3,  # Claude 3.5 Haiku 기본값
        help="쿼리 분석 및 실행 계획 수립 (Claude 모델 권장)"
    )
    st.session_state['orchestration_model'] = claude_model_ids[orchestration_idx]
    
    # Action 모델 (모든 모델)
    action_idx = st.sidebar.selectbox(
        "⚡ Action Model", 
        range(len(all_model_names)),
        format_func=lambda x: all_model_names[x],
        index=5,  # Nova Micro 기본값 (경제적)
        help="실제 액션(KB 검색 등) 수행 (모든 모델 사용 가능)"
    )
    st.session_state['action_model'] = all_model_ids[action_idx]
    
    # Observation 모델 (Claude만)
    observation_idx = st.sidebar.selectbox(
        "👁️ Observation Model",
        range(len(claude_models)),
        format_func=lambda x: claude_models[x], 
        index=3,  # Claude 3.5 Haiku 기본값
        help="결과 분석 및 최종 답변 생성 (Claude 모델 권장)"
    )
    st.session_state['observation_model'] = claude_model_ids[observation_idx]
    
    # 권장 조합 표시
    _render_model_recommendations()


def _render_system_prompt():
    """시스템 프롬프트 설정 UI"""
    st.sidebar.header("📝 System Instructions")
    
    system_prompt = st.sidebar.text_area(
        "System Prompt",
        value=st.session_state.get('system_prompt', ''),
        height=100,
        placeholder="Agent의 역할과 행동 방식을 정의하는 시스템 프롬프트를 입력하세요...",
        help="Agent가 어떻게 동작해야 하는지 지시하는 프롬프트"
    )
    st.session_state['system_prompt'] = system_prompt


def _render_enhanced_kb_settings():
    """개선된 Knowledge Base 설정 UI"""
    st.sidebar.header("🔍 Knowledge Base")
    
    # KB ID 입력
    kb_id = st.sidebar.text_input(
        "Knowledge Base ID",
        value=st.session_state.get('kb_id', ''),
        placeholder="예: ABCDEFGHIJ",
        help="Amazon Bedrock Knowledge Base ID (선택사항)"
    )
    st.session_state['kb_id'] = kb_id
    
    # KB 설명 입력 (새로 추가)
    kb_description = st.sidebar.text_area(
        "KB Description",
        value=st.session_state.get('kb_description', ''),
        height=80,
        placeholder="예: Anycompany 비즈니스 참조\n예: 기술 문서 및 API 가이드\n예: HR 정책 및 절차 매뉴얼",
        help="KB에 포함된 내용에 대한 간단한 설명 (KB 검색 판단에 활용)"
    )
    st.session_state['kb_description'] = kb_description
    
    # KB 설정 상태 표시
    if kb_id and kb_description:
        st.sidebar.success("✅ KB 검색 기능 완전 활성화")
        st.sidebar.info(f"📚 KB 내용: {kb_description}")
        st.sidebar.caption("• 검색 타입: Hybrid")
        st.sidebar.caption("• 최대 결과: 5개")
        st.sidebar.caption("• 지능적 검색 판단: 활성화")
    elif kb_id:
        st.sidebar.warning("⚠️ KB 설명을 추가하면 더 정확한 검색 판단이 가능합니다")
        st.sidebar.caption("• 기본 검색 로직 사용")
    else:
        st.sidebar.info("💡 KB ID와 설명을 입력하면 지능적 검색이 활성화됩니다")
    
    # KB 검색 규칙 설명
    if kb_id:
        with st.sidebar.expander("🔍 KB 검색 규칙", expanded=False):
            st.write("**1. KB 설명 기반 판단**")
            st.write("- 질문이 KB 설명과 관련있으면 검색")
            st.write("- 예: 'Anycompany 비즈니스' → 회사 관련 질문 검색")
            
            st.write("**2. 모델 지식 한계 인식**")
            st.write("- 모델이 모르는 내용이면 KB 검색")
            st.write("- 예: 특정 회사 정책, 내부 절차 등")
            
            st.write("**3. 일반 상식 제외**")
            st.write("- 무지개 색깔, 수학 계산 등은 KB 검색 안함")


def _render_parameters():
    """파라미터 설정 UI"""
    st.sidebar.header("⚙️ Parameters")
    
    # Temperature 설정
    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.get('temperature', 0.1),
        step=0.1,
        help="응답의 창의성 조절 (0: 일관성, 1: 창의성)"
    )
    st.session_state['temperature'] = temperature
    
    # Max Tokens 설정 (모델별 제한 고려)
    selected_models = [
        st.session_state.get('orchestration_model', ''),
        st.session_state.get('action_model', ''),
        st.session_state.get('observation_model', '')
    ]
    
    # 선택된 모델 중 하나라도 Nova가 있으면 5K 제한
    has_nova = any('nova' in model.lower() for model in selected_models)
    max_limit = 5000 if has_nova else 8000
    
    max_tokens = st.sidebar.slider(
        f"Max Tokens ({'Nova 제한: 5K' if has_nova else 'Claude 제한: 8K'})",
        min_value=1000,
        max_value=max_limit,
        value=min(st.session_state.get('max_tokens', 4000), max_limit),
        step=100,
        help=f"모델이 생성할 수 있는 최대 토큰 수 (현재 제한: {max_limit:,})"
    )
    st.session_state['max_tokens'] = max_tokens


def _render_connection_tests():
    """연결 테스트 UI"""
    st.sidebar.header("🔧 Connection Tests")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("Bedrock 테스트", help="Amazon Bedrock 연결 테스트"):
            with st.spinner("Bedrock 연결 테스트 중..."):
                try:
                    client = BedrockClient()
                    if client.test_connection():
                        st.success("✅ Bedrock 연결 성공!")
                    else:
                        st.error("❌ Bedrock 연결 실패")
                except Exception as e:
                    st.error(f"❌ 테스트 오류: {str(e)}")
    
    with col2:
        kb_id = st.session_state.get('kb_id', '')
        if kb_id:
            if st.button("KB 테스트", help="Knowledge Base 연결 테스트"):
                with st.spinner("KB 연결 테스트 중..."):
                    try:
                        searcher = KnowledgeBaseSearcher()
                        test_results = searcher.search(
                            kb_id=kb_id,
                            query="테스트",
                            max_results=1
                        )
                        if test_results:
                            st.success(f"✅ KB 연결 성공! ({len(test_results)}개 결과)")
                        else:
                            st.warning("⚠️ KB 연결됨, 테스트 결과 없음")
                    except Exception as e:
                        st.error(f"❌ KB 테스트 실패: {str(e)}")
        else:
            st.caption("KB ID를 입력하면 테스트 가능")


def _render_model_recommendations():
    """권장 모델 조합 표시"""
    with st.sidebar.expander("💡 권장 모델 조합", expanded=False):
        st.write("**🚀 고성능 조합**")
        st.write("• Orchestration: Claude Sonnet 4")
        st.write("• Action: Claude 3.7 Sonnet")
        st.write("• Observation: Claude 3.5 Sonnet v2")
        
        st.write("**⚖️ 균형 조합**")
        st.write("• Orchestration: Claude 3.5 Haiku")
        st.write("• Action: Nova Lite")
        st.write("• Observation: Claude 3.5 Haiku")
        
        st.write("**💰 경제적 조합 (기본)**")
        st.write("• Orchestration: Claude 3.5 Haiku")
        st.write("• Action: Nova Micro")
        st.write("• Observation: Claude 3.5 Haiku")


def _render_reset_button():
    """대화 리셋 버튼"""
    st.sidebar.header("🔄 Reset")
    
    if st.sidebar.button("대화 기록 초기화", help="모든 대화 기록을 삭제합니다"):
        if 'messages' in st.session_state:
            st.session_state.messages = []
        st.success("✅ 대화 기록이 초기화되었습니다!")
        st.rerun()


def _render_config_summary():
    """설정 요약 표시"""
    with st.sidebar.expander("📋 현재 설정 요약", expanded=False):
        # 모델 정보
        st.write("**🧠 선택된 모델:**")
        st.write(f"• Orchestration: {_get_model_name(st.session_state.get('orchestration_model', ''))}")
        st.write(f"• Action: {_get_model_name(st.session_state.get('action_model', ''))}")
        st.write(f"• Observation: {_get_model_name(st.session_state.get('observation_model', ''))}")
        
        # KB 정보
        kb_id = st.session_state.get('kb_id', '')
        kb_desc = st.session_state.get('kb_description', '')
        st.write("**🔍 Knowledge Base:**")
        if kb_id:
            st.write(f"• ID: {kb_id}")
            if kb_desc:
                st.write(f"• 설명: {kb_desc}")
            else:
                st.write("• 설명: 없음")
        else:
            st.write("• 비활성화")
        
        # 파라미터 정보
        st.write("**⚙️ 파라미터:**")
        st.write(f"• Temperature: {st.session_state.get('temperature', 0.1)}")
        st.write(f"• Max Tokens: {st.session_state.get('max_tokens', 4000):,}")
        
        # 시스템 프롬프트
        system_prompt = st.session_state.get('system_prompt', '')
        st.write("**📝 System Prompt:**")
        if system_prompt:
            st.write(f"• 설정됨 ({len(system_prompt)}자)")
        else:
            st.write("• 없음")
