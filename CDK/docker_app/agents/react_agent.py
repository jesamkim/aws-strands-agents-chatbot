"""
ReAct Agent 메인 클래스
AWS Strands Agents 기반 ReAct 패턴 구현
"""

import time
from typing import Dict, List, Any
from utils.config import AgentConfig
from .orchestration import OrchestrationAgent
from .action import ActionAgent
from .observation import ObservationAgent


class SafetyController:
    """ReAct 루프의 안전장치를 관리하는 클래스"""
    
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.used_keywords = set()  # 사용된 검색 키워드 추적
        self.repeated_actions = []  # 반복된 액션 추적
        self.error_count = 0  # 연속 에러 카운트
        self.max_errors = 3  # 최대 허용 에러 수
        
    def should_continue(self, current_iteration: int, action_result: dict) -> tuple[bool, str]:
        """
        루프 계속 여부를 판단
        Returns: (should_continue, reason)
        """
        # 1. 최대 반복 횟수 체크
        if current_iteration >= self.max_iterations:
            return False, f"최대 반복 횟수({self.max_iterations})에 도달했습니다."
        
        # 2. 연속 에러 체크
        if self.error_count >= self.max_errors:
            return False, f"연속 에러가 {self.max_errors}회 발생했습니다."
        
        # 3. 검색 키워드 반복 체크 (더 엄격하게)
        if action_result.get("search_keywords"):
            keywords = set(action_result["search_keywords"])
            
            # 완전히 동일한 키워드 세트인지 확인
            if keywords and keywords.issubset(self.used_keywords) and len(keywords) > 2:
                # 키워드가 3개 이상이고 모두 이전에 사용된 경우만 중복으로 판단
                return False, "동일한 검색 키워드가 반복되어 루프를 중단합니다."
            
            # 새로운 키워드가 있으면 계속 진행
            self.used_keywords.update(keywords)
        
        # 4. 반복된 액션 체크 (완화)
        action_signature = self._get_action_signature(action_result)
        
        # 동일한 시그니처가 3번 이상 반복되는 경우만 중단
        signature_count = self.repeated_actions.count(action_signature)
        if signature_count >= 2:  # 3번째 반복부터 중단
            return False, "동일한 액션이 3회 반복되어 루프를 중단합니다."
        
        # 액션 기록
        self.repeated_actions.append(action_signature)
        
        return True, ""
    
    def record_error(self):
        """에러 발생 기록"""
        self.error_count += 1
    
    def reset_error_count(self):
        """에러 카운트 리셋 (성공적인 액션 후)"""
        self.error_count = 0
    
    def _get_action_signature(self, action_result: dict) -> str:
        """액션의 고유 시그니처 생성"""
        return f"{action_result.get('type', 'unknown')}_{hash(str(action_result.get('search_keywords', [])))}"


class ReActAgent:
    """
    AWS Strands Agents 기반 ReAct 패턴 구현 클래스
    
    Orchestration → Action → Observation 반복 루프를 통해
    사용자 쿼리에 대한 지능적인 응답을 생성합니다.
    """
    
    def __init__(self, config: AgentConfig):
        """
        ReAct Agent 초기화
        
        Args:
            config: Agent 설정
        """
        self.config = config
        self.orchestration_agent = OrchestrationAgent(config)
        self.action_agent = ActionAgent(config)
        self.observation_agent = ObservationAgent(config)
    
    def run(self, user_query: str, conversation_history: List[Dict]) -> Dict:
        """
        ReAct 루프 실행 (최대 5회 반복으로 무한루프 방지)
        
        Args:
            user_query: 사용자 쿼리
            conversation_history: 대화 히스토리
            
        Returns:
            응답 딕셔너리 (content, react_steps, iterations_used 등 포함)
        """
        start_time = time.time()
        safety_controller = SafetyController(max_iterations=5)
        current_iteration = 0
        
        context = {
            "original_query": user_query,
            "conversation_history": conversation_history,
            "kb_results": []
        }
        
        react_steps = []
        termination_reason = ""
        final_answer = None
        
        try:
            while True:
                current_iteration += 1
                
                try:
                    # 1. Orchestration 단계
                    orchestration_result = self.orchestration_agent.orchestrate(context, react_steps)
                    react_steps.append(orchestration_result)
                    
                    # Orchestration 오류 체크
                    if orchestration_result.get("parsed_result", {}).get("error"):
                        safety_controller.record_error()
                    else:
                        safety_controller.reset_error_count()
                    
                    # 2. Action 단계
                    action_result = self.action_agent.act(orchestration_result, context)
                    react_steps.append(action_result)
                    
                    # Action 오류 체크
                    if action_result.get("error"):
                        safety_controller.record_error()
                    else:
                        safety_controller.reset_error_count()
                    
                    # 3. Observation 단계
                    observation_result = self.observation_agent.observe(action_result, context)
                    react_steps.append(observation_result)
                    
                    # Observation 오류 체크
                    if observation_result.get("error"):
                        safety_controller.record_error()
                    else:
                        safety_controller.reset_error_count()
                    
                    # 자연스러운 종료 조건 확인
                    observation_parsed = observation_result.get("parsed_result", {})
                    
                    if observation_parsed.get("should_stop", False):
                        raw_answer = observation_parsed.get("final_answer")
                        if raw_answer:
                            # Citation 참조 목록 추가
                            search_results_for_citations = []
                            for step in react_steps:
                                if step.get("type") == "Action" and step.get("search_results"):
                                    search_results_for_citations.extend(step["search_results"])
                            
                            final_answer = self._add_citation_references(raw_answer, search_results_for_citations)
                            termination_reason = "목표 달성으로 정상 종료"
                            break
                        elif not observation_parsed.get("needs_retry", False):
                            termination_reason = "추가 정보 없이 종료"
                            final_answer = "죄송합니다. 충분한 정보를 찾을 수 없습니다."
                            break
                    
                    # 재시도가 필요한 경우 처리
                    if observation_parsed.get("needs_retry", False):
                        retry_keywords = observation_parsed.get("retry_keywords", [])
                        if retry_keywords:
                            # 새로운 키워드로 재시도 준비
                            context["retry_keywords"] = retry_keywords
                            # 다음 반복에서 Orchestration이 이를 고려하도록 함
                        else:
                            # 재시도 키워드가 없으면 종료
                            termination_reason = "재시도 키워드 없음으로 종료"
                            final_answer = "죄송합니다. 추가 검색할 키워드를 찾을 수 없습니다."
                            break
                    
                    # 안전장치 체크
                    should_continue, reason = safety_controller.should_continue(
                        current_iteration, action_result
                    )
                    
                    if not should_continue:
                        termination_reason = reason
                        # 현재까지의 최선의 답변 찾기
                        final_answer = self._extract_best_answer(react_steps)
                        break
                        
                except Exception as e:
                    # 단계 실행 중 예외 발생
                    safety_controller.record_error()
                    error_step = {
                        "type": "Error",
                        "content": f"단계 실행 중 오류 발생: {str(e)}",
                        "iteration": current_iteration,
                        "error": True
                    }
                    react_steps.append(error_step)
                    
                    # 에러 한계 체크
                    should_continue, reason = safety_controller.should_continue(
                        current_iteration, {}
                    )
                    
                    if not should_continue:
                        termination_reason = reason
                        final_answer = "시스템 오류로 인해 답변을 생성할 수 없습니다."
                        break
            
            # 최종 답변이 없는 경우 기본 답변 생성
            if not final_answer:
                final_answer = self._generate_fallback_answer(react_steps, user_query)
                if not termination_reason:
                    termination_reason = "기본 답변 생성"
            
            execution_time = time.time() - start_time
            
            return {
                "role": "assistant",
                "content": final_answer,
                "react_steps": react_steps,
                "iterations_used": current_iteration,
                "termination_reason": termination_reason,
                "safety_triggered": termination_reason != "목표 달성으로 정상 종료",
                "execution_time": execution_time,
                "timestamp": time.time()
            }
            
        except Exception as e:
            # 전체 실행 중 예외 발생
            execution_time = time.time() - start_time
            
            return {
                "role": "assistant",
                "content": f"ReAct 엔진 실행 중 오류가 발생했습니다: {str(e)}",
                "react_steps": react_steps,
                "iterations_used": current_iteration,
                "termination_reason": "시스템 오류",
                "safety_triggered": True,
                "execution_time": execution_time,
                "error": True,
                "timestamp": time.time()
            }
    
    def _extract_best_answer(self, react_steps: List[Dict]) -> str:
        """현재까지의 단계에서 최선의 답변 추출"""
        
        best_answer = ""
        search_results_for_citations = []
        
        # 답변 가능한 Observation에서 답변 찾기 (우선순위)
        for step in reversed(react_steps):
            if step.get("type") == "Observation":
                parsed = step.get("parsed_result", {})
                if parsed.get("can_answer") and parsed.get("final_answer"):
                    best_answer = parsed["final_answer"]
                    break
        
        # 답변 가능한 것이 없으면 마지막 Observation에서 답변 찾기
        if not best_answer:
            for step in reversed(react_steps):
                if step.get("type") == "Observation":
                    parsed = step.get("parsed_result", {})
                    if parsed.get("final_answer"):
                        best_answer = parsed["final_answer"]
                        break
        
        # 모든 검색 결과 수집 (citation용)
        for step in react_steps:
            if step.get("type") == "Action" and step.get("search_results"):
                search_results_for_citations.extend(step["search_results"])
        
        # 답변이 있으면 citation 참조 목록 추가
        if best_answer and search_results_for_citations:
            best_answer = self._add_citation_references(best_answer, search_results_for_citations)
            return best_answer
        
        # KB 검색 결과가 있다면 그것을 기반으로 간단한 답변 생성
        if search_results_for_citations:
            # 상위 결과들로 간단한 요약 생성
            summary_parts = []
            for result in search_results_for_citations[:3]:
                content = result.get("content", "")[:100]
                citation_id = result.get("citation_id", len(summary_parts) + 1)
                if content.strip():
                    summary_parts.append(f"• {content.strip()}... [{citation_id}]")
            
            if summary_parts:
                fallback_answer = f"검색된 정보를 바탕으로:\n\n" + "\n\n".join(summary_parts)
                return self._add_citation_references(fallback_answer, search_results_for_citations)
        
        return "죄송합니다. 충분한 정보를 수집하지 못했습니다."
    
    def _add_citation_references(self, answer: str, search_results: List[Dict]) -> str:
        """답변에 citation 참조 목록 추가"""
        
        # Citation이 사용되었는지 확인
        import re
        citations_used = re.findall(r'\[(\d+)\]', answer)
        
        if not citations_used:
            return answer
        
        # 사용된 citation만 참조 목록에 포함
        citation_references = []
        for citation_num in sorted(set(citations_used), key=int):
            citation_id = int(citation_num)
            
            # 해당 citation_id를 가진 검색 결과 찾기
            for result in search_results:
                if result.get('citation_id') == citation_id:
                    source = result.get('source', 'Unknown')
                    content_preview = result.get('content', '')[:100] + '...' if len(result.get('content', '')) > 100 else result.get('content', '')
                    
                    citation_references.append(f"[{citation_id}] {source}: {content_preview}")
                    break
        
        # 참조 목록을 답변에 추가
        if citation_references:
            answer += "\n\n**참조:**\n" + "\n".join(citation_references)
        
        return answer
    
    def _generate_fallback_answer(self, react_steps: List[Dict], user_query: str) -> str:
        """폴백 답변 생성"""
        
        # 실행된 단계 수 확인
        step_types = [step.get("type") for step in react_steps]
        orchestration_count = step_types.count("Orchestration")
        action_count = step_types.count("Action")
        observation_count = step_types.count("Observation")
        
        # 단계별 실행 정보 포함한 답변
        fallback = f"죄송합니다. {orchestration_count}회의 분석과 {action_count}회의 검색을 시도했지만 "
        fallback += f"'{user_query}'에 대한 충분한 답변을 생성하지 못했습니다.\n\n"
        
        # 검색 결과가 있었다면 언급
        has_search_results = any(
            step.get("search_results") for step in react_steps 
            if step.get("type") == "Action"
        )
        
        if has_search_results:
            fallback += "일부 관련 정보는 찾았지만 완전한 답변을 구성하기에는 부족했습니다. "
        
        fallback += "더 구체적인 질문을 해주시면 더 나은 답변을 드릴 수 있습니다."
        
        return fallback
    
    def get_agent_info(self) -> Dict[str, str]:
        """Agent 정보 반환"""
        return {
            "orchestration_model": self.orchestration_agent.get_model_name(),
            "action_model": self.action_agent.get_model_name(),
            "observation_model": self.observation_agent.get_model_name(),
            "kb_enabled": str(self.config.is_kb_enabled()),
            "kb_id": self.config.kb_id or "None"
        }
