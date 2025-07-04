"""
지능적 ReAct Agent v5 - KB 설명 기반 동적 검색
"""

import time
from typing import Dict, List, Any
from utils.config import AgentConfig
from .orchestration import OptimizedOrchestrationAgent  # KB 우선순위 기반 초고속
from .action import ActionAgent
from .observation import ObservationAgent


class SafetyController:
    """ReAct 루프의 안전장치를 관리하는 클래스"""
    
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.used_keywords = set()
        self.repeated_actions = []
        self.error_count = 0
        self.max_errors = 3
        
    def should_continue(self, current_iteration: int, action_result: dict) -> tuple[bool, str]:
        if current_iteration >= self.max_iterations:
            return False, f"최대 반복 횟수({self.max_iterations})에 도달했습니다."
        
        if self.error_count >= self.max_errors:
            return False, f"연속 에러가 {self.max_errors}회 발생했습니다."
        
        if action_result.get("search_keywords"):
            keywords = set(action_result["search_keywords"])
            if keywords and keywords.issubset(self.used_keywords) and len(keywords) > 2:
                return False, "동일한 검색 키워드가 반복되어 루프를 중단합니다."
            self.used_keywords.update(keywords)
        
        action_signature = self._get_action_signature(action_result)
        signature_count = self.repeated_actions.count(action_signature)
        if signature_count >= 2:
            return False, "동일한 액션이 3회 반복되어 루프를 중단합니다."
        
        self.repeated_actions.append(action_signature)
        return True, ""
    
    def record_error(self):
        self.error_count += 1
    
    def reset_error_count(self):
        self.error_count = 0
    
    def _get_action_signature(self, action_result: dict) -> str:
        return f"{action_result.get('type', 'unknown')}_{hash(str(action_result.get('search_keywords', [])))}"


class IntelligentReActAgent:
    """지능적 ReAct Agent v5 - KB 설명 기반 동적 검색"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        # KB 우선순위 기반 초고속 Orchestration Agent 사용
        self.orchestration_agent = OptimizedOrchestrationAgent(config)
        self.action_agent = ActionAgent(config)
        self.observation_agent = ObservationAgent(config)
    
    def run(self, user_query: str, conversation_history: List[Dict]) -> Dict:
        """지능적 KB 검색이 적용된 ReAct 루프 실행"""
        start_time = time.time()
        
        safety_controller = SafetyController(max_iterations=self.config.max_iterations)
        
        context = {
            "original_query": user_query,
            "conversation_history": conversation_history,
            "kb_id": self.config.kb_id,
            "kb_description": self.config.kb_description,
            "start_time": start_time
        }
        
        steps = []
        final_answer = None
        termination_reason = "정상 완료"
        
        try:
            for iteration in range(self.config.max_iterations):
                print(f"\n🔄 ReAct 반복 {iteration + 1}/{self.config.max_iterations}")
                
                # 1. Intelligent Orchestration
                print("🧠 Intelligent Orchestration 단계...")
                orchestration_start = time.time()
                
                orchestration_result = self.orchestration_agent.orchestrate(context)
                steps.append(orchestration_result)
                
                orchestration_time = time.time() - orchestration_start
                print(f"   완료 ({orchestration_time:.2f}초)")
                
                # 지능적 판단 결과 표시
                parsed_result = orchestration_result.get("parsed_result", {})
                if parsed_result.get("context_applied", False):
                    print("   🔗 대화 맥락 적용됨")
                
                kb_decision = parsed_result.get("kb_decision", {})
                if kb_decision:
                    rule_applied = kb_decision.get("rule_applied", "")
                    reason = kb_decision.get("reason", "")
                    print(f"   🎯 KB 검색 결정: {kb_decision.get('needs_search', False)}")
                    print(f"   📋 적용 규칙: {rule_applied}")
                    print(f"   💡 판단 이유: {reason}")
                
                if parsed_result.get("error"):
                    safety_controller.record_error()
                else:
                    safety_controller.reset_error_count()
                
                # KB 검색이 필요하지 않은 경우 바로 Observation으로
                if not parsed_result.get("needs_kb_search", False):
                    print("   ℹ️ KB 검색 불필요, Observation으로 이동")
                    
                    observation_result = self.observation_agent.observe(context, steps)
                    steps.append(observation_result)
                    
                    obs_parsed = observation_result.get("parsed_result", {})
                    if obs_parsed.get("is_final_answer", False):
                        final_answer = obs_parsed.get("final_answer", "답변을 생성할 수 없습니다.")
                        termination_reason = "KB 검색 없이 답변 완료"
                        break
                
                # 2. Intelligent Action (KB 검색)
                print("⚡ Intelligent Action 단계...")
                action_result = self.action_agent.act(context, steps)
                steps.append(action_result)
                
                action_parsed = action_result.get("parsed_result", {})
                if action_parsed.get("error"):
                    safety_controller.record_error()
                else:
                    safety_controller.reset_error_count()
                
                # 3. Context-Aware Observation
                print("👁️ Context-Aware Observation 단계...")
                # previous_steps를 context에 추가하여 반복 횟수 추적
                context["previous_steps"] = steps
                observation_result = self.observation_agent.observe(context, steps)
                steps.append(observation_result)
                
                obs_parsed = observation_result.get("parsed_result", {})
                
                # 최종 답변인지 확인
                if obs_parsed.get("is_final_answer", False):
                    final_answer = obs_parsed.get("final_answer", "답변을 생성할 수 없습니다.")
                    termination_reason = f"{iteration + 1}회 반복 후 완료"
                    break
                
                # 재시도가 필요한지 확인
                if obs_parsed.get("needs_retry", False):
                    retry_keywords = obs_parsed.get("retry_keywords", [])
                    if retry_keywords:
                        print(f"   🔄 재시도 필요: {retry_keywords}")
                        # 다음 반복에서 사용할 키워드를 context에 추가
                        context["retry_keywords"] = retry_keywords
                        context["retry_reason"] = obs_parsed.get("retry_reason", "검색 결과 불충분")
                        continue  # 다음 반복으로
                
                # 안전장치 확인
                should_continue, reason = safety_controller.should_continue(iteration + 1, action_parsed)
                if not should_continue:
                    termination_reason = f"안전장치 작동: {reason}"
                    if obs_parsed.get("partial_answer"):
                        final_answer = obs_parsed.get("partial_answer")
                    else:
                        final_answer = obs_parsed.get("final_answer", "부분적인 답변을 제공합니다.")
                    break
            
            if final_answer is None:
                final_answer = "죄송합니다. 충분한 정보를 찾을 수 없어 완전한 답변을 드리기 어렵습니다."
                termination_reason = "최대 반복 횟수 도달"
        
        except Exception as e:
            final_answer = f"처리 중 오류가 발생했습니다: {str(e)}"
            termination_reason = f"예외 발생: {str(e)}"
        
        total_time = time.time() - start_time
        
        return {
            "final_answer": final_answer,
            "steps": steps,
            "metadata": {
                "total_iterations": len([s for s in steps if s.get("type") == "Orchestration"]),
                "total_time": total_time,
                "termination_reason": termination_reason,
                "orchestration_model": self.orchestration_agent.get_model_name(),
                "action_model": self.action_agent.get_model_name(),
                "observation_model": self.observation_agent.get_model_name(),
                "optimization_level": "INTELLIGENT_V5",  # v5 표시
                "context_aware": True,
                "kb_enhanced": True,
                "intelligent_kb_search": True
            }
        }
    
    def get_performance_info(self) -> Dict:
        return {
            "orchestration_optimized": True,
            "optimization_level": "INTELLIGENT_V5",
            "context_aware": True,
            "kb_enhanced": True,
            "intelligent_kb_search": True,
            "orchestration_model": self.orchestration_agent.get_model_name(),
            "features": {
                "ultra_fast_prompt": True,
                "improved_domain_detection": True,
                "instant_fallback": True,
                "minimal_tokens": True,
                "conversation_context": True,
                "continuation_handling": True,
                "enhanced_kb_search": True,
                "auto_keyword_generation": True,
                "kb_description_based_search": True,
                "model_knowledge_limit_recognition": True,
                "general_knowledge_filtering": True
            }
        }


# 기존 코드와의 호환성을 위한 별칭
ReActAgent = IntelligentReActAgent
