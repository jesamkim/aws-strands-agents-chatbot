"""
Simplified Strands Agents Tools for ReAct Chatbot
간소화된 버전으로 Mock 환경에서도 작동
"""

from typing import Dict, List, Any, Optional
import json

# Strands import with fallback to mock
try:
    from strands import tool
    STRANDS_AVAILABLE = True
except ImportError:
    from .mock_strands import mock_tool as tool
    STRANDS_AVAILABLE = False

from utils.config import AgentConfig


class SimpleStrandsToolsManager:
    """간소화된 Strands Agents 도구 관리자"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        print(f"🔧 SimpleStrandsToolsManager 초기화 (Strands 사용 가능: {STRANDS_AVAILABLE})")
    
    def get_all_tools(self) -> List[callable]:
        """모든 도구 반환"""
        return [
            self.create_kb_search_tool(),
            self.create_context_analyzer(),
            self.create_quality_assessor()
        ]
    
    def create_kb_search_tool(self):
        """KB 검색 도구 생성"""
        config = self.config
        
        @tool
        def kb_search_tool(keywords: List[str], max_results: int = 5) -> str:
            """Knowledge Base 검색 도구"""
            try:
                if not config.is_kb_enabled():
                    return json.dumps({
                        "success": False,
                        "error": "KB가 설정되지 않음",
                        "results": []
                    })
                
                # Mock 검색 결과 (실제 환경에서는 실제 검색 수행)
                mock_results = [
                    {
                        "id": 1,
                        "content": f"Mock 검색 결과: {keywords}에 대한 정보입니다.",
                        "source": "Mock KB Source",
                        "score": 0.85
                    }
                ]
                
                return json.dumps({
                    "success": True,
                    "results_count": len(mock_results),
                    "results": mock_results,
                    "search_keywords": keywords
                })
                
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "results": []
                })
        
        return kb_search_tool
    
    def create_context_analyzer(self):
        """대화 맥락 분석 도구 생성"""
        @tool
        def context_analyzer(query: str, history: List[Dict]) -> str:
            """대화 맥락 분석 도구"""
            try:
                # 간단한 맥락 분석
                is_greeting = any(word in query.lower() for word in ["안녕", "hello", "hi"])
                is_continuation = any(word in query.lower() for word in ["다음", "그럼", "계속"])
                
                return json.dumps({
                    "is_greeting": is_greeting,
                    "is_continuation": is_continuation,
                    "has_context": len(history) > 0,
                    "needs_kb_search": not (is_greeting or is_continuation)
                })
                
            except Exception as e:
                return json.dumps({
                    "error": str(e),
                    "is_greeting": False,
                    "is_continuation": False,
                    "has_context": False,
                    "needs_kb_search": True
                })
        
        return context_analyzer
    
    def create_quality_assessor(self):
        """검색 품질 평가 도구 생성"""
        @tool
        def quality_assessor(search_results: List[Dict], iteration: int = 1) -> str:
            """검색 품질 평가 도구"""
            try:
                if not search_results:
                    return json.dumps({
                        "quality_score": 0.0,
                        "needs_retry": iteration < 3,
                        "is_sufficient": False,
                        "reason": "검색 결과 없음"
                    })
                
                # 간단한 품질 평가
                avg_score = sum(r.get("score", 0) for r in search_results) / len(search_results)
                is_sufficient = avg_score > 0.5 or iteration >= 3
                
                return json.dumps({
                    "quality_score": avg_score,
                    "needs_retry": not is_sufficient,
                    "is_sufficient": is_sufficient,
                    "reason": f"평균 점수: {avg_score:.2f}, 반복: {iteration}"
                })
                
            except Exception as e:
                return json.dumps({
                    "quality_score": 0.0,
                    "needs_retry": False,
                    "is_sufficient": True,
                    "reason": f"평가 오류: {str(e)}"
                })
        
        return quality_assessor
