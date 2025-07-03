"""
Streamlit 사이드바 UI 컴포넌트
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
    
    # Knowledge Base 설정 섹션
    _render_kb_settings()
    
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


def _render_kb_settings():
    """Knowledge Base 설정 UI"""
    st.sidebar.header("🔍 Knowledge Base")
    
    kb_id = st.sidebar.text_input(
        "Knowledge Base ID",
        value=st.session_state.get('kb_id', ''),
        placeholder="예: ABCDEFGHIJ",
        help="Amazon Bedrock Knowledge Base ID (선택사항)"
    )
    st.session_state['kb_id'] = kb_id
    
    if kb_id:
        st.sidebar.info("✅ KB 검색 기능이 활성화됩니다")
        st.sidebar.caption("• 검색 타입: Hybrid")
        st.sidebar.caption("• 최대 결과: 5개")
    else:
        st.sidebar.warning("KB ID가 없으면 검색 기능을 사용할 수 없습니다")


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
                        if searcher.test_kb_connection(kb_id):
                            st.success("✅ KB 연결 성공!")
                        else:
                            st.error("❌ KB 연결 실패")
                    except Exception as e:
                        st.error(f"❌ 테스트 오류: {str(e)}")
        else:
            st.button("KB 테스트", disabled=True, help="KB ID를 먼저 입력하세요")


def _render_reset_button():
    """대화 리셋 버튼"""
    st.sidebar.header("🔄 Actions")
    
    if st.sidebar.button("대화 초기화", type="primary", help="모든 대화 기록을 삭제합니다"):
        # 대화 관련 세션 상태 초기화
        if 'messages' in st.session_state:
            del st.session_state['messages']
        if 'conversation_history' in st.session_state:
            del st.session_state['conversation_history']
        
        st.success("✅ 대화가 초기화되었습니다!")
        st.rerun()


def _render_config_summary():
    """현재 설정 요약 표시"""
    st.sidebar.header("📊 Current Config")
    
    config = AgentConfig.from_streamlit_session()
    
    with st.sidebar.expander("설정 요약 보기"):
        st.write("**모델 설정:**")
        st.caption(f"• Orchestration: {_get_model_name(config.orchestration_model)}")
        st.caption(f"• Action: {_get_model_name(config.action_model)}")
        st.caption(f"• Observation: {_get_model_name(config.observation_model)}")
        
        st.write("**파라미터:**")
        st.caption(f"• Temperature: {config.temperature}")
        st.caption(f"• Max Tokens: {config.max_tokens:,}")
        
        st.write("**기능:**")
        st.caption(f"• KB 검색: {'✅' if config.is_kb_enabled() else '❌'}")
        st.caption(f"• 시스템 프롬프트: {'✅' if config.system_prompt else '❌'}")


def _render_model_recommendations():
    """권장 모델 조합 표시"""
    with st.sidebar.expander("💡 권장 모델 조합"):
        st.write("**🚀 고성능 조합**")
        st.caption("• Orchestration: Claude Sonnet 4")
        st.caption("• Action: Claude 3.7 Sonnet")
        st.caption("• Observation: Claude 3.5 Sonnet v2")
        
        if st.button("고성능 조합 적용", key="high_perf"):
            st.session_state['orchestration_model'] = "us.anthropic.claude-sonnet-4-20250514-v1:0"
            st.session_state['action_model'] = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            st.session_state['observation_model'] = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            st.success("✅ 고성능 조합이 적용되었습니다!")
            st.rerun()
        
        st.write("**⚖️ 균형 조합 (권장)**")
        st.caption("• Orchestration: Claude 3.5 Haiku")
        st.caption("• Action: Nova Lite")
        st.caption("• Observation: Claude 3.5 Haiku")
        
        if st.button("균형 조합 적용", key="balanced"):
            st.session_state['orchestration_model'] = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            st.session_state['action_model'] = "us.amazon.nova-lite-v1:0"
            st.session_state['observation_model'] = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            st.success("✅ 균형 조합이 적용되었습니다!")
            st.rerun()
        
        st.write("**💰 경제적 조합**")
        st.caption("• Orchestration: Claude 3.5 Haiku")
        st.caption("• Action: Nova Micro")
        st.caption("• Observation: Claude 3.5 Haiku")
        
        if st.button("경제적 조합 적용", key="cost_effective"):
            st.session_state['orchestration_model'] = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            st.session_state['action_model'] = "us.amazon.nova-micro-v1:0"
            st.session_state['observation_model'] = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            st.success("✅ 경제적 조합이 적용되었습니다!")
            st.rerun()
