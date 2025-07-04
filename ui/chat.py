"""
수정된 Streamlit 채팅 UI 컴포넌트
ReAct Agent 응답 구조와 호환성 개선
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
                content = message.get("content", "")
                if content:
                    st.write(content)
                else:
                    st.write("(메시지 내용 없음)")


def _render_assistant_message(message: Dict[str, Any]):
    """Assistant 메시지 렌더링 (ReAct 단계 포함)"""
    # 최종 답변 표시 (안전한 방식)
    content = message.get("content", message.get("final_answer", "응답을 생성할 수 없습니다."))
    st.write(content)
    
    # ReAct 단계 정보가 있는 경우 표시
    react_steps = message.get("react_steps", message.get("steps", []))
    if react_steps:
        _render_react_steps(react_steps)
    
    # 실행 정보 표시
    _render_execution_info(message)


def _render_react_steps(react_steps: List[Dict]):
    """ReAct 단계별 정보 표시"""
    if not react_steps:
        return
        
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
                
                # 파싱된 결과가 있으면 우선 표시
                parsed_result = step.get("parsed_result", {})
                if parsed_result and not parsed_result.get("error", False):
                    _render_parsed_result(step_type, parsed_result)
                
                # 원본 내용 표시 (길면 축약) - expander 중첩 방지
                if step_content and len(step_content) > 50:
                    st.markdown("**원본 응답:**")
                    if len(step_content) > 500:
                        st.text(step_content[:500] + "...")
                        st.caption(f"(전체 {len(step_content)}자 중 500자 표시)")
                    else:
                        st.text(step_content)
                
                # 검색 결과가 있는 경우 표시
                if step_type == "Action":
                    search_results = step.get("search_results", parsed_result.get("search_results", []))
                    if search_results:
                        _render_search_results(search_results)
            
            if i < len(react_steps) - 1:
                st.divider()


def _render_parsed_result(step_type: str, parsed_result: Dict):
    """파싱된 결과 표시"""
    if step_type == "Orchestration":
        intent = parsed_result.get("intent", "")
        keywords = parsed_result.get("search_keywords", [])
        confidence = parsed_result.get("confidence", 0)
        
        if intent:
            st.markdown(f"**의도**: {intent}")
        if keywords:
            st.markdown(f"**검색 키워드**: {', '.join(keywords)}")
        if confidence:
            st.markdown(f"**신뢰도**: {confidence:.2f}")
    
    elif step_type == "Action":
        search_type = parsed_result.get("search_type", "")
        search_keywords = parsed_result.get("search_keywords", [])
        
        if search_type:
            st.markdown(f"**검색 유형**: {search_type}")
        if search_keywords:
            st.markdown(f"**사용된 키워드**: {', '.join(search_keywords)}")
    
    elif step_type == "Observation":
        is_final = parsed_result.get("is_final_answer", False)
        final_answer = parsed_result.get("final_answer", "")
        
        if is_final:
            st.success("✅ 최종 답변 생성 완료")
        if final_answer and len(final_answer) > 100:
            st.markdown("**생성된 답변 미리보기**:")
            st.text(final_answer[:100] + "...")


def _render_search_results(search_results: List[Dict]):
    """검색 결과 표시"""
    if not search_results:
        st.caption("검색 결과 없음")
        return
    
    st.caption(f"📚 검색 결과 ({len(search_results)}개)")
    
    for i, result in enumerate(search_results[:3]):  # 상위 3개만 표시
        score = result.get('score', 0)
        st.markdown(f"**결과 {i+1}** (점수: {score:.3f})")
        
        content = result.get('content', result.get('text', ''))
        if content:
            if len(content) > 200:
                st.text(content[:200] + "...")
            else:
                st.text(content)
        
        source = result.get('source', result.get('metadata', {}).get('source', ''))
        if source:
            st.caption(f"출처: {source}")
        
        if i < len(search_results[:3]) - 1:
            st.markdown("---")


def _render_execution_info(message: Dict[str, Any]):
    """실행 정보 표시"""
    # 메타데이터에서 정보 추출
    metadata = message.get("metadata", {})
    
    iterations = metadata.get("total_iterations", message.get("iterations_used", 0))
    max_iterations = 5
    
    if iterations > 0:
        # 진행률 표시
        progress = min(iterations / max_iterations, 1.0)
        st.progress(progress, text=f"ReAct 반복: {iterations}/{max_iterations}회")
    
    # 안전장치 작동 여부 표시
    termination_reason = metadata.get("termination_reason", message.get("termination_reason", ""))
    if "안전장치" in termination_reason or "중단" in termination_reason:
        st.warning(f"⚠️ {termination_reason}")
    elif termination_reason and termination_reason != "정상 완료":
        st.info(f"ℹ️ {termination_reason}")
    
    # 실행 시간 표시
    total_time = metadata.get("total_time", message.get("execution_time", 0))
    if total_time > 0:
        st.caption(f"⏱️ 실행 시간: {total_time:.2f}초")
    
    # 최적화 정보 표시
    if metadata.get("optimization_level"):
        st.caption(f"🚀 최적화 레벨: {metadata['optimization_level']}")


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
    try:
        from agents.react_agent import ReActAgent
        
        # ReAct Agent 초기화
        react_agent = ReActAgent(config)
        
        # 대화 히스토리 가져오기 (현재 사용자 메시지 제외)
        all_messages = st.session_state.messages[:-1]  # 마지막 메시지(현재 입력) 제외
        conversation_history = all_messages[-10:] if len(all_messages) > 0 else []
        
        # 대화 히스토리를 더 구조화된 형태로 변환
        formatted_history = []
        for msg in conversation_history:
            if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                formatted_history.append({
                    "role": msg["role"],
                    "content": str(msg["content"])[:500],  # 문자열로 변환 후 축약
                    "timestamp": msg.get("timestamp", 0)
                })
        
        with st.spinner("🤖 ReAct Agent가 분석하고 있습니다..."):
            # 진행 상황 표시
            progress_placeholder = st.empty()
            
            # 실제 ReAct 엔진 실행
            progress_placeholder.progress(0.1, text="🎯 Orchestration: 쿼리 분석 중...")
            
            response = react_agent.run(user_input, formatted_history)
            
            progress_placeholder.progress(1.0, text="✅ 완료!")
            time.sleep(0.5)  # 잠시 표시
            progress_placeholder.empty()
            
            # 응답 구조 정규화
            final_answer = response.get("final_answer", "응답을 생성할 수 없습니다.")
            
            # 응답 표시
            st.write(final_answer)
            
            # ReAct 단계 정보 표시
            react_steps = response.get("steps", [])
            if react_steps:
                _render_react_steps(react_steps)
            
            # 실행 정보 표시
            _render_execution_info(response)
            
            # 응답을 세션에 저장 (정규화된 형태)
            assistant_message = {
                "role": "assistant",
                "content": final_answer,
                "timestamp": time.time(),
                "steps": react_steps,
                "metadata": response.get("metadata", {}),
                "error": False
            }
            st.session_state.messages.append(assistant_message)
            
    except Exception as e:
        # 에러 처리
        error_message = f"ReAct 엔진 실행 중 오류가 발생했습니다: {str(e)}"
        st.error(error_message)
        
        # 디버그 정보 표시
        with st.expander("🔧 디버그 정보", expanded=False):
            st.text(f"에러 타입: {type(e).__name__}")
            st.text(f"에러 메시지: {str(e)}")
            
            # 스택 트레이스 표시
            import traceback
            st.text("스택 트레이스:")
            st.code(traceback.format_exc())
        
        # 에러 응답도 세션에 저장
        error_response = {
            "role": "assistant",
            "content": "죄송합니다. 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "timestamp": time.time(),
            "error": True,
            "error_details": str(e)
        }
        st.session_state.messages.append(error_response)


def _get_short_model_name(model_id: str) -> str:
    """모델 ID를 짧은 이름으로 변환"""
    if not model_id:
        return "Unknown"
        
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
        return model_id.split(':')[0] if ':' in model_id else model_id
