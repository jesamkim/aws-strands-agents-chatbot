"""
Strands Agents와 기존 ReAct 시스템 간의 호환성 어댑터
점진적 마이그레이션을 위한 브리지 역할
"""

import asyncio
from typing import Dict, List, Any, Optional
from utils.config import AgentConfig
from .strands_react_agent import StrandsReActChatbot
from .react_agent import SafetyController  # 기존 시스템


class StrandsCompatibilityAdapter:
    """
    Strands Agents와 기존 ReAct 시스템 간의 호환성 어댑터
    
    주요 기능:
    - 기존 인터페이스 유지
    - Strands Agents 기반 처리
    - 결과 형식 통일
    - 에러 처리 및 폴백
    """
    
    def __init__(self, config: AgentConfig, use_strands: bool = True):
        self.config = config
        self.use_strands = use_strands
        
        # Strands Agents 시스템
        if use_strands:
            try:
                self.strands_chatbot = StrandsReActChatbot(config)
                self.strands_available = True
            except Exception as e:
                print(f"⚠️ Strands Agents 초기화 실패: {e}")
                self.strands_available = False
        else:
            self.strands_available = False
        
        # 기존 시스템 (폴백용)
        self.legacy_controller = SafetyController()
    
    def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        쿼리 처리 - Strands 우선, 실패 시 기존 시스템 사용
        
        Args:
            query: 사용자 질문
            conversation_history: 대화 히스토리
            
        Returns:
            처리 결과 (기존 형식과 호환)
        """
        if conversation_history is None:
            conversation_history = []
        
        # Strands Agents 시도
        if self.strands_available and self.use_strands:
            try:
                print("🚀 Strands Agents 처리 시작")
                
                # 비동기 처리를 동기로 변환
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    strands_result = loop.run_until_complete(
                        self.strands_chatbot.process_query(query, conversation_history)
                    )
                    
                    if not strands_result.get("error"):
                        print("✅ Strands Agents 처리 완료")
                        return self._convert_strands_result(strands_result)
                    else:
                        print(f"❌ Strands Agents 오류: {strands_result.get('content')}")
                        raise Exception(strands_result.get("content", "Unknown error"))
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                print(f"⚠️ Strands Agents 실패, 기존 시스템으로 폴백: {e}")
                return self._fallback_to_legacy(query, conversation_history)
        
        # 기존 시스템 사용
        else:
            print("🔄 기존 ReAct 시스템 사용")
            return self._fallback_to_legacy(query, conversation_history)
    
    def _convert_strands_result(self, strands_result: Dict) -> Dict:
        """
        Strands 결과를 기존 형식으로 변환
        
        Args:
            strands_result: Strands Agents 결과
            
        Returns:
            기존 형식과 호환되는 결과
        """
        # 기존 형식에 맞춰 변환
        converted_result = {
            "type": "ReAct",
            "content": strands_result.get("content", ""),
            "final_answer": strands_result.get("content", ""),
            "search_results": strands_result.get("search_results", []),
            "citations": strands_result.get("citations", []),
            "processing_time": strands_result.get("processing_time", 0),
            "iterations": strands_result.get("iterations", 1),
            "context_analysis": strands_result.get("context_analysis", {}),
            "model_info": {
                "framework": "Strands Agents",
                "orchestration": self.config.orchestration_model,
                "action": self.config.action_model,
                "observation": self.config.observation_model
            },
            "error": False,
            "steps": self._generate_steps_summary(strands_result)
        }
        
        return converted_result
    
    def _generate_steps_summary(self, strands_result: Dict) -> List[Dict]:
        """Strands 결과에서 단계별 요약 생성"""
        steps = []
        
        # 1. 맥락 분석 단계
        context_analysis = strands_result.get("context_analysis", {})
        steps.append({
            "type": "Context Analysis",
            "content": f"대화 맥락 분석 완료",
            "details": {
                "is_continuation": context_analysis.get("is_continuation", False),
                "is_greeting": context_analysis.get("is_greeting", False),
                "has_context": context_analysis.get("has_context", False),
                "needs_kb_search": context_analysis.get("needs_kb_search", False)
            }
        })
        
        # 2. 검색 단계 (있는 경우)
        search_results = strands_result.get("search_results", [])
        if search_results:
            steps.append({
                "type": "Knowledge Base Search",
                "content": f"KB 검색 완료: {len(search_results)}개 결과",
                "details": {
                    "results_count": len(search_results),
                    "iterations": strands_result.get("iterations", 1),
                    "top_scores": [r.get("score", 0) for r in search_results[:3]]
                }
            })
        
        # 3. 답변 생성 단계
        steps.append({
            "type": "Answer Generation",
            "content": "최종 답변 생성 완료",
            "details": {
                "has_citations": len(strands_result.get("citations", [])) > 0,
                "processing_time": strands_result.get("processing_time", 0)
            }
        })
        
        return steps
    
    def _fallback_to_legacy(self, query: str, conversation_history: List[Dict]) -> Dict:
        """
        기존 시스템으로 폴백 처리
        
        Args:
            query: 사용자 질문
            conversation_history: 대화 히스토리
            
        Returns:
            기존 시스템 처리 결과
        """
        try:
            # 기존 시스템 컨텍스트 구성
            context = {
                "original_query": query,
                "conversation_history": conversation_history,
                "kb_id": self.config.kb_id,
                "kb_description": self.config.kb_description
            }
            
            # 기존 ReAct 루프 실행
            result = self.legacy_controller.process_query(context, self.config)
            
            # 결과에 폴백 정보 추가
            if isinstance(result, dict):
                result["fallback_used"] = True
                result["framework"] = "Legacy ReAct"
            
            return result
            
        except Exception as e:
            # 최종 에러 처리
            return {
                "type": "Error",
                "content": f"처리 중 오류가 발생했습니다: {str(e)}",
                "final_answer": "죄송합니다. 현재 서비스에 문제가 있습니다. 잠시 후 다시 시도해주세요.",
                "error": True,
                "fallback_used": True,
                "framework": "Error Handler"
            }
    
    def test_connection(self) -> Dict:
        """연결 테스트"""
        results = {
            "strands_available": self.strands_available,
            "legacy_available": True,  # 항상 사용 가능
            "kb_enabled": self.config.is_kb_enabled(),
            "models": {
                "orchestration": self.config.orchestration_model,
                "action": self.config.action_model,
                "observation": self.config.observation_model
            }
        }
        
        # Strands 시스템 테스트
        if self.strands_available:
            try:
                model_info = self.strands_chatbot.get_model_info()
                results["strands_test"] = {
                    "success": True,
                    "info": model_info
                }
            except Exception as e:
                results["strands_test"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # KB 연결 테스트
        if self.config.is_kb_enabled():
            try:
                # 기존 시스템의 KB 테스트 활용
                from .action import ActionAgent
                action_agent = ActionAgent(self.config)
                kb_test = action_agent.test_kb_connection()
                results["kb_test"] = kb_test
            except Exception as e:
                results["kb_test"] = {
                    "success": False,
                    "message": f"KB 테스트 실패: {str(e)}"
                }
        
        return results
    
    def get_system_info(self) -> Dict:
        """시스템 정보 반환"""
        return {
            "active_system": "Strands Agents" if (self.strands_available and self.use_strands) else "Legacy ReAct",
            "strands_available": self.strands_available,
            "use_strands": self.use_strands,
            "kb_enabled": self.config.is_kb_enabled(),
            "kb_id": self.config.kb_id if self.config.is_kb_enabled() else None,
            "models": {
                "orchestration": self.config.orchestration_model,
                "action": self.config.action_model,
                "observation": self.config.observation_model
            }
        }
    
    def switch_system(self, use_strands: bool) -> bool:
        """시스템 전환"""
        if use_strands and not self.strands_available:
            return False  # Strands가 사용 불가능한 경우
        
        self.use_strands = use_strands
        return True


class StrandsReActController:
    """
    기존 SafetyController와 호환되는 Strands 기반 컨트롤러
    기존 코드 수정 최소화를 위한 래퍼
    """
    
    def __init__(self, config: AgentConfig = None):
        if config is None:
            from utils.config import AgentConfig
            config = AgentConfig()
        
        self.adapter = StrandsCompatibilityAdapter(config, use_strands=True)
    
    def process_query(self, context: Dict, config: AgentConfig) -> Dict:
        """기존 인터페이스와 호환되는 쿼리 처리"""
        query = context.get("original_query", "")
        history = context.get("conversation_history", [])
        
        return self.adapter.process_query(query, history)
    
    def test_connection(self) -> Dict:
        """연결 테스트"""
        return self.adapter.test_connection()
    
    def get_system_info(self) -> Dict:
        """시스템 정보"""
        return self.adapter.get_system_info()
