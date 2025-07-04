"""
Simplified Strands Agents 호환성 어댑터
Mock 환경에서도 작동하는 간소화된 버전
"""

import asyncio
from typing import Dict, List, Any, Optional
from utils.config import AgentConfig
from .strands_react_simple import SimpleStrandsReActChatbot


class SimpleStrandsCompatibilityAdapter:
    """
    간소화된 Strands Agents 호환성 어댑터
    
    주요 기능:
    - Mock 환경 지원
    - 기존 인터페이스 유지
    - 간단한 폴백 처리
    """
    
    def __init__(self, config: AgentConfig, use_strands: bool = True):
        self.config = config
        self.use_strands = use_strands
        
        # Strands 시스템 초기화
        if use_strands:
            try:
                self.strands_chatbot = SimpleStrandsReActChatbot(config)
                self.strands_available = True
                print("✅ Simple Strands Agents 초기화 성공")
            except Exception as e:
                print(f"⚠️ Simple Strands Agents 초기화 실패: {e}")
                self.strands_available = False
        else:
            self.strands_available = False
        
        # Legacy 시스템 (폴백용)
        self.legacy_available = True
    
    def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        쿼리 처리 - Strands 우선, 실패 시 폴백
        
        Args:
            query: 사용자 질문
            conversation_history: 대화 히스토리
            
        Returns:
            처리 결과
        """
        if conversation_history is None:
            conversation_history = []
        
        # Strands 시스템 시도
        if self.strands_available and self.use_strands:
            try:
                print("🚀 Simple Strands Agents 처리 시작")
                
                # 비동기 처리를 동기로 변환
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    strands_result = loop.run_until_complete(
                        self.strands_chatbot.process_query(query, conversation_history)
                    )
                    
                    if not strands_result.get("error"):
                        print("✅ Simple Strands Agents 처리 완료")
                        return self._convert_strands_result(strands_result)
                    else:
                        print(f"❌ Simple Strands Agents 오류: {strands_result.get('content')}")
                        raise Exception(strands_result.get("content", "Unknown error"))
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                print(f"⚠️ Simple Strands Agents 실패, 폴백 처리: {e}")
                return self._fallback_response(query, conversation_history, str(e))
        
        # 폴백 처리
        else:
            print("🔄 폴백 시스템 사용")
            return self._fallback_response(query, conversation_history, "Strands 시스템 비활성화")
    
    def _convert_strands_result(self, strands_result: Dict) -> Dict:
        """Strands 결과를 기존 형식으로 변환"""
        return {
            "type": "ReAct",
            "content": strands_result.get("content", ""),
            "final_answer": strands_result.get("content", ""),
            "search_results": strands_result.get("search_results", []),
            "processing_time": strands_result.get("processing_time", 0),
            "iterations": strands_result.get("iterations", 1),
            "context_analysis": strands_result.get("context_analysis", {}),
            "model_info": {
                "framework": strands_result.get("framework", "Simple Strands Agents"),
                "strands_available": strands_result.get("strands_available", False)
            },
            "error": False,
            "steps": self._generate_steps_summary(strands_result)
        }
    
    def _generate_steps_summary(self, strands_result: Dict) -> List[Dict]:
        """단계별 요약 생성"""
        steps = []
        
        # 맥락 분석 단계
        context_analysis = strands_result.get("context_analysis", {})
        steps.append({
            "type": "Context Analysis",
            "content": "대화 맥락 분석 완료",
            "details": context_analysis
        })
        
        # 검색 단계 (있는 경우)
        search_results = strands_result.get("search_results", [])
        if search_results:
            steps.append({
                "type": "Knowledge Base Search",
                "content": f"KB 검색 완료: {len(search_results)}개 결과",
                "details": {
                    "results_count": len(search_results),
                    "iterations": strands_result.get("iterations", 1)
                }
            })
        
        # 답변 생성 단계
        steps.append({
            "type": "Answer Generation",
            "content": "최종 답변 생성 완료",
            "details": {
                "processing_time": strands_result.get("processing_time", 0),
                "framework": strands_result.get("framework", "Simple Strands Agents")
            }
        })
        
        return steps
    
    def _fallback_response(self, query: str, history: List[Dict], reason: str) -> Dict:
        """폴백 응답 생성"""
        # 간단한 규칙 기반 응답
        if any(word in query.lower() for word in ["안녕", "hello", "hi"]):
            answer = "안녕하세요! 무엇을 도와드릴까요?"
        elif "테스트" in query:
            answer = "테스트 응답입니다. 시스템이 정상적으로 작동하고 있습니다."
        else:
            answer = f"'{query}'에 대한 답변을 준비하고 있습니다. 현재 간소화된 모드로 작동 중입니다."
        
        return {
            "type": "Fallback",
            "content": answer,
            "final_answer": answer,
            "search_results": [],
            "processing_time": 0.1,
            "iterations": 1,
            "model_info": {
                "framework": "Fallback System",
                "reason": reason
            },
            "fallback_used": True,
            "error": False,
            "steps": [
                {
                    "type": "Fallback Response",
                    "content": f"폴백 시스템 사용: {reason}",
                    "details": {"query": query}
                }
            ]
        }
    
    def test_connection(self) -> Dict:
        """연결 테스트"""
        results = {
            "strands_available": self.strands_available,
            "legacy_available": self.legacy_available,
            "kb_enabled": self.config.is_kb_enabled(),
            "use_strands": self.use_strands
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
        
        return results
    
    def get_system_info(self) -> Dict:
        """시스템 정보 반환"""
        return {
            "active_system": "Simple Strands Agents" if (self.strands_available and self.use_strands) else "Fallback",
            "strands_available": self.strands_available,
            "use_strands": self.use_strands,
            "kb_enabled": self.config.is_kb_enabled(),
            "kb_id": self.config.kb_id if self.config.is_kb_enabled() else None
        }
    
    def switch_system(self, use_strands: bool) -> bool:
        """시스템 전환"""
        if use_strands and not self.strands_available:
            return False
        
        self.use_strands = use_strands
        return True
