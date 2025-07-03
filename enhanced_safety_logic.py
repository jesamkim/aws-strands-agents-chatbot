"""
강화된 무한루프 방지 및 안전장치 로직
"""

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
        
        # 3. 반복된 액션 체크
        action_signature = self._get_action_signature(action_result)
        if action_signature in self.repeated_actions:
            return False, "동일한 액션이 반복되어 루프를 중단합니다."
        
        # 4. 검색 키워드 반복 체크
        if action_result.get("search_keywords"):
            keywords = set(action_result["search_keywords"])
            if keywords.issubset(self.used_keywords):
                return False, "동일한 검색 키워드가 반복되어 루프를 중단합니다."
            self.used_keywords.update(keywords)
        
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


class EnhancedReActAgent:
    """안전장치가 강화된 ReAct Agent"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-west-2')
        self.kb_client = boto3.client('bedrock-agent-runtime', region_name='us-west-2')
        
    def run(self, user_query: str, conversation_history: List[Dict]) -> Dict:
        """안전장치가 적용된 ReAct 루프 실행"""
        safety_controller = SafetyController(max_iterations=5)
        current_iteration = 0
        
        context = {
            "original_query": user_query,
            "conversation_history": conversation_history,
            "kb_results": []
        }
        
        react_steps = []
        termination_reason = ""
        
        while True:
            current_iteration += 1
            
            try:
                # 1. Orchestration 단계
                orchestration_result = self.orchestration_step(context, react_steps)
                react_steps.append(orchestration_result)
                
                # 2. Action 단계
                action_result = self.action_step(orchestration_result, context)
                react_steps.append(action_result)
                
                # 에러 카운트 리셋 (성공적인 액션)
                safety_controller.reset_error_count()
                
                # 3. Observation 단계
                observation_result = self.observation_step(action_result, context)
                react_steps.append(observation_result)
                
                # 자연스러운 종료 조건 확인
                if observation_result.get("should_stop", False):
                    termination_reason = "목표 달성으로 정상 종료"
                    break
                
                # 안전장치 체크
                should_continue, reason = safety_controller.should_continue(
                    current_iteration, action_result
                )
                
                if not should_continue:
                    termination_reason = reason
                    break
                    
            except Exception as e:
                # 에러 발생 시 기록
                safety_controller.record_error()
                error_step = {
                    "type": "Error",
                    "content": f"단계 실행 중 오류 발생: {str(e)}",
                    "iteration": current_iteration
                }
                react_steps.append(error_step)
                
                # 에러 한계 체크
                should_continue, reason = safety_controller.should_continue(
                    current_iteration, {}
                )
                
                if not should_continue:
                    termination_reason = reason
                    break
        
        # 최종 답변 생성
        final_answer = self._generate_final_answer(
            react_steps, termination_reason, current_iteration
        )
        
        return {
            "role": "assistant",
            "content": final_answer,
            "react_steps": react_steps,
            "iterations_used": current_iteration,
            "termination_reason": termination_reason,
            "safety_triggered": termination_reason != "목표 달성으로 정상 종료"
        }
    
    def _generate_final_answer(self, react_steps: List[Dict], 
                             termination_reason: str, iterations: int) -> str:
        """최종 답변 생성"""
        
        # 마지막 observation에서 답변 추출 시도
        for step in reversed(react_steps):
            if step.get("type") == "Observation" and step.get("final_answer"):
                return step["final_answer"]
        
        # KB 검색 결과가 있다면 그것을 기반으로 답변 생성
        kb_results = []
        for step in react_steps:
            if step.get("type") == "Action" and step.get("search_results"):
                kb_results.extend(step["search_results"])
        
        if kb_results:
            # KB 결과를 기반으로 간단한 답변 생성
            context_summary = " ".join([result.get("content", "")[:100] 
                                      for result in kb_results[:3]])
            return f"검색된 정보를 바탕으로: {context_summary}... (총 {iterations}회 반복 후 {termination_reason})"
        
        # 기본 답변
        return f"죄송합니다. {iterations}회 시도 후 충분한 정보를 찾지 못했습니다. ({termination_reason})"


# Streamlit UI에서 안전장치 상태 표시
def display_safety_status(response: Dict):
    """안전장치 상태를 UI에 표시"""
    
    if response.get("safety_triggered"):
        st.warning(f"⚠️ 안전장치 작동: {response.get('termination_reason')}")
    
    # 반복 횟수 표시
    iterations = response.get("iterations_used", 0)
    max_iterations = 5
    
    progress_bar = st.progress(iterations / max_iterations)
    st.caption(f"ReAct 반복: {iterations}/{max_iterations}회")
    
    # 각 단계별 상세 정보 (접을 수 있는 형태로)
    with st.expander("🔍 ReAct 단계별 상세 정보"):
        for i, step in enumerate(response.get("react_steps", [])):
            step_type = step.get("type", "Unknown")
            
            if step_type == "Error":
                st.error(f"❌ {step_type} (반복 {step.get('iteration', '?')}): {step.get('content', '')}")
            elif step_type in ["Orchestration", "Action", "Observation"]:
                st.info(f"🔄 {step_type}: {step.get('content', '')[:100]}...")
            else:
                st.text(f"ℹ️ {step_type}: {step.get('content', '')[:100]}...")
