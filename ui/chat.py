"""
Streamlit 채팅 UI 컴포넌트
"""

import streamlit as st
from typing import List, Dict, Any
import time

from utils.config import AgentConfig


def render_chat_interface(config: AgentConfig) -> None:
    """
    메인 채팅 인터페이스 렌더링
    
    Args:
        config: Agent 설정
    """
    # 채팅 메시지 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # 채팅 기록 표시
    _render_chat_history()
    
    # 사용자 입력 처리
    _handle_user_input(config)


def _render_chat_history():
    """채팅 기록 표시"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                # Assistant 메시지의 경우 ReAct 단계 정보도 표시
                _render_assistant_message(message)
            else:
                # User 메시지
                st.write(message["content"])


def _render_assistant_message(message: Dict[str, Any]):
    """Assistant 메시지 렌더링 (ReAct 단계 포함)"""
    # 최종 답변 표시
    st.write(message["content"])
    
    # ReAct 단계 정보가 있는 경우 표시
    if "react_steps" in message and message["react_steps"]:
        _render_react_steps(message["react_steps"])
    
    # 실행 정보 표시
    if "iterations_used" in message:
        _render_execution_info(message)


def _render_react_steps(react_steps: List[Dict]):
    """ReAct 단계별 정보 표시"""
    with st.expander("🔍 ReAct 단계별 상세 정보", expanded=False):
        for i, step in enumerate(react_steps):
            step_type = step.get("type", "Unknown")
            step_content = step.get("content", "")
            
            # 단계별 아이콘 설정
            if step_type == "Orchestration":
                icon = "🎯"
                color = "blue"
            elif step_type == "Action":
                icon = "⚡"
                color = "green"
            elif step_type == "Observation":
                icon = "👁️"
                color = "orange"
            elif step_type == "Error":
                icon = "❌"
                color = "red"
            else:
                icon = "ℹ️"
                color = "gray"
            
            # 단계 정보 표시
            st.markdown(f"**{icon} {step_type}** (Step {i+1})")
            
            if step_type == "Error":
                st.error(step_content)
            else:
                # 모델 정보 표시
                if "model" in step:
                    model_name = _get_short_model_name(step["model"])
                    st.caption(f"Model: {model_name}")
                
                # 내용 표시 (길면 축약)
                if len(step_content) > 200:
                    with st.expander(f"내용 보기 ({len(step_content)}자)"):
                        st.text(step_content)
                else:
                    st.text(step_content)
                
                # 검색 결과가 있는 경우 표시
                if step_type == "Action" and "search_results" in step:
                    _render_search_results(step["search_results"])
            
            if i < len(react_steps) - 1:
                st.divider()


def _render_search_results(search_results: List[Dict]):
    """검색 결과 표시"""
    if not search_results:
        st.caption("검색 결과 없음")
        return
    
    st.caption(f"📚 검색 결과 ({len(search_results)}개)")
    
    for i, result in enumerate(search_results[:3]):  # 상위 3개만 표시
        with st.expander(f"결과 {i+1} (점수: {result.get('score', 0):.3f})"):
            st.write(result.get('content', '')[:300] + "...")
            if 'source' in result:
                st.caption(f"출처: {result['source']}")


def _render_execution_info(message: Dict[str, Any]):
    """실행 정보 표시"""
    iterations = message.get("iterations_used", 0)
    max_iterations = 5
    
    # 진행률 표시
    progress = iterations / max_iterations
    st.progress(progress, text=f"ReAct 반복: {iterations}/{max_iterations}회")
    
    # 안전장치 작동 여부 표시
    if message.get("safety_triggered", False):
        termination_reason = message.get("termination_reason", "알 수 없는 이유")
        st.warning(f"⚠️ 안전장치 작동: {termination_reason}")
    
    # 실행 시간 표시 (있는 경우)
    if "execution_time" in message:
        st.caption(f"⏱️ 실행 시간: {message['execution_time']:.2f}초")


def _handle_user_input(config: AgentConfig):
    """사용자 입력 처리"""
    # 채팅 입력
    if prompt := st.chat_input("메시지를 입력하세요..."):
        # 사용자 메시지 추가
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,
            "timestamp": time.time()
        })
        
        # 사용자 메시지 즉시 표시
        with st.chat_message("user"):
            st.write(prompt)
        
        # Assistant 응답 생성
        with st.chat_message("assistant"):
            _generate_assistant_response(prompt, config)


def _generate_assistant_response(user_input: str, config: AgentConfig):
    """Assistant 응답 생성 (실제 ReAct 엔진 사용)"""
    from agents.react_agent import ReActAgent
    
    # ReAct Agent 초기화
    react_agent = ReActAgent(config)
    
    # 대화 히스토리 가져오기 (현재 사용자 메시지 제외)
    # 최근 10개 메시지에서 현재 입력은 제외하고 이전 대화만 포함
    all_messages = st.session_state.messages
    conversation_history = all_messages[-10:] if len(all_messages) > 0 else []
    
    # 대화 히스토리를 더 구조화된 형태로 변환
    formatted_history = []
    for msg in conversation_history:
        if msg.get("role") in ["user", "assistant"]:
            formatted_history.append({
                "role": msg["role"],
                "content": msg["content"][:500],  # 너무 긴 메시지는 축약
                "timestamp": msg.get("timestamp", 0)
            })
    
    with st.spinner("🤖 ReAct Agent가 분석하고 있습니다..."):
        # 진행 상황 표시
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # 실제 ReAct 엔진 실행
        try:
            # 진행 상황 시뮬레이션
            progress_placeholder.progress(0.1, text="🎯 Orchestration: 쿼리 분석 중...")
            
            response = react_agent.run(user_input, formatted_history)
            
            progress_placeholder.progress(1.0, text="✅ 완료!")
            time.sleep(0.5)  # 잠시 표시
            progress_placeholder.empty()
            status_placeholder.empty()
            
            # 응답 표시
            st.write(response["content"])
            
            # ReAct 단계 정보 표시
            if response.get("react_steps"):
                _render_react_steps(response["react_steps"])
            
            # 실행 정보 표시
            _render_execution_info(response)
            
            # 응답을 세션에 저장
            st.session_state.messages.append(response)
            
        except Exception as e:
            progress_placeholder.empty()
            status_placeholder.empty()
            
            error_message = f"ReAct 엔진 실행 중 오류가 발생했습니다: {str(e)}"
            st.error(error_message)
            
            # 에러 응답도 세션에 저장
            error_response = {
                "role": "assistant",
                "content": error_message,
                "timestamp": time.time(),
                "error": True
            }
            st.session_state.messages.append(error_response)


def _get_short_model_name(model_id: str) -> str:
    """모델 ID를 짧은 이름으로 변환"""
    if "claude-sonnet-4" in model_id:
        return "Claude 4"
    elif "claude-3-7-sonnet" in model_id:
        return "Claude 3.7"
    elif "claude-3-5-sonnet" in model_id:
        return "Claude 3.5 Sonnet"
    elif "claude-3-5-haiku" in model_id:
        return "Claude 3.5 Haiku"
    elif "nova-lite" in model_id:
        return "Nova Lite"
    elif "nova-micro" in model_id:
        return "Nova Micro"
    else:
        return model_id.split(':')[0]
