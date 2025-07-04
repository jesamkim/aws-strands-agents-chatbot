"""
Simplified AWS Strands Agents 기반 ReAct 챗봇
Mock 환경에서도 작동하는 간소화된 버전
"""

import json
import time
from typing import Dict, List, Any, Optional

# Strands import with fallback to mock
try:
    from strands import Agent
    STRANDS_AVAILABLE = True
except ImportError:
    from .mock_strands import MockAgent as Agent
    STRANDS_AVAILABLE = False

from utils.config import AgentConfig
from .strands_tools_simple import SimpleStrandsToolsManager


class SimpleStrandsReActChatbot:
    """
    간소화된 AWS Strands Agents 기반 ReAct 챗봇
    
    주요 특징:
    - Mock 환경 지원
    - 기본적인 ReAct 패턴 구현
    - 대화 맥락 인식
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.tools_manager = SimpleStrandsToolsManager(config)
        self.strands_available = STRANDS_AVAILABLE
        
        print(f"🚀 SimpleStrandsReActChatbot 초기화 (Strands: {STRANDS_AVAILABLE})")
        
        # 메인 에이전트 생성
        self.main_agent = self._create_main_agent()
    
    def _create_main_agent(self) -> Agent:
        """메인 에이전트 생성"""
        system_prompt = f"""{self.config.system_prompt or '당신은 도움이 되는 AI 어시스턴트입니다.'}

당신은 사용자 질문을 분석하고 적절한 답변을 제공하는 ReAct 에이전트입니다.

**처리 방식:**
1. 대화 맥락 분석
2. 필요시 Knowledge Base 검색
3. 검색 결과 기반 답변 생성

**도구 사용:**
- kb_search_tool: KB 검색이 필요한 경우
- context_analyzer: 대화 맥락 분석
- quality_assessor: 검색 결과 품질 평가

항상 한국어로 응답하세요."""
        
        return Agent(
            system_prompt=system_prompt,
            tools=self.tools_manager.get_all_tools()
        )
    
    async def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        사용자 쿼리 처리
        
        Args:
            query: 사용자 질문
            conversation_history: 대화 히스토리
            
        Returns:
            처리 결과
        """
        start_time = time.time()
        
        try:
            if conversation_history is None:
                conversation_history = []
            
            print(f"🔍 쿼리 처리 시작: {query}")
            
            # 1단계: 대화 맥락 분석
            context_analysis = await self._analyze_context(query, conversation_history)
            print(f"   맥락 분석: {context_analysis}")
            
            # 2단계: 처리 방법 결정
            if context_analysis.get("is_greeting"):
                result = await self._handle_greeting(query)
            elif context_analysis.get("is_continuation"):
                result = await self._handle_continuation(query, conversation_history)
            elif not self.config.is_kb_enabled():
                result = await self._handle_direct_answer(query)
            else:
                result = await self._handle_kb_search(query, conversation_history)
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            return {
                "type": "SimpleStrandsReAct",
                "content": result.get("answer", "답변을 생성할 수 없습니다."),
                "processing_time": processing_time,
                "context_analysis": context_analysis,
                "search_results": result.get("search_results", []),
                "iterations": result.get("iterations", 1),
                "framework": "Simple Strands Agents",
                "strands_available": self.strands_available,
                "error": False
            }
            
        except Exception as e:
            return {
                "type": "SimpleStrandsReAct",
                "content": f"처리 중 오류가 발생했습니다: {str(e)}",
                "processing_time": time.time() - start_time,
                "error": True,
                "error_details": str(e)
            }
    
    async def _analyze_context(self, query: str, history: List[Dict]) -> Dict:
        """대화 맥락 분석"""
        try:
            # 간단한 맥락 분석 (Mock 환경에서도 작동)
            is_greeting = any(word in query.lower() for word in ["안녕", "hello", "hi"])
            is_continuation = any(word in query.lower() for word in ["다음", "그럼", "계속", "또는"])
            
            return {
                "is_greeting": is_greeting,
                "is_continuation": is_continuation,
                "has_context": len(history) > 0,
                "needs_kb_search": not (is_greeting or is_continuation) and self.config.is_kb_enabled()
            }
            
        except Exception as e:
            return {
                "is_greeting": False,
                "is_continuation": False,
                "has_context": False,
                "needs_kb_search": True,
                "error": str(e)
            }
    
    async def _handle_greeting(self, query: str) -> Dict:
        """인사말 처리"""
        try:
            # 에이전트를 통한 인사말 응답
            response = self.main_agent(f"사용자가 인사했습니다: '{query}'. 친근하게 인사하고 도움을 제안하세요.")
            
            return {
                "answer": str(response),
                "search_results": [],
                "iterations": 1
            }
            
        except Exception as e:
            return {
                "answer": "안녕하세요! 무엇을 도와드릴까요?",
                "search_results": [],
                "iterations": 1,
                "error": str(e)
            }
    
    async def _handle_continuation(self, query: str, history: List[Dict]) -> Dict:
        """대화 연속성 처리"""
        try:
            # 이전 대화 맥락 구성
            context_text = ""
            if history:
                for msg in history[-3:]:
                    role = msg.get("role", "")
                    content = msg.get("content", "")[:200]
                    context_text += f"{role}: {content}\n"
            
            prompt = f"""이전 대화:
{context_text}

현재 질문: {query}

이전 대화를 바탕으로 연속성 있는 답변을 제공하세요."""
            
            response = self.main_agent(prompt)
            
            return {
                "answer": str(response),
                "search_results": [],
                "iterations": 1
            }
            
        except Exception as e:
            return {
                "answer": "이전 대화를 바탕으로 답변드리겠습니다.",
                "search_results": [],
                "iterations": 1,
                "error": str(e)
            }
    
    async def _handle_direct_answer(self, query: str) -> Dict:
        """직접 답변 처리"""
        try:
            response = self.main_agent(f"다음 질문에 대해 일반적인 지식으로 답변하세요: {query}")
            
            return {
                "answer": str(response),
                "search_results": [],
                "iterations": 1
            }
            
        except Exception as e:
            return {
                "answer": "일반적인 지식을 바탕으로 답변드리겠습니다.",
                "search_results": [],
                "iterations": 1,
                "error": str(e)
            }
    
    async def _handle_kb_search(self, query: str, history: List[Dict]) -> Dict:
        """KB 검색 처리"""
        try:
            # KB 검색 시뮬레이션
            search_prompt = f"""다음 질문에 대해 Knowledge Base를 검색하고 답변하세요:
질문: {query}
KB ID: {self.config.kb_id}

kb_search_tool을 사용하여 검색하고 결과를 바탕으로 답변하세요."""
            
            response = self.main_agent(search_prompt)
            
            # Mock 검색 결과
            mock_results = [
                {
                    "id": 1,
                    "content": f"{query}에 대한 Mock 검색 결과입니다.",
                    "source": "Mock KB",
                    "score": 0.8
                }
            ]
            
            return {
                "answer": str(response),
                "search_results": mock_results,
                "iterations": 1
            }
            
        except Exception as e:
            return {
                "answer": "Knowledge Base 검색을 통해 답변드리겠습니다.",
                "search_results": [],
                "iterations": 1,
                "error": str(e)
            }
    
    def get_model_info(self) -> Dict:
        """모델 정보 반환"""
        return {
            "framework": "Simple Strands Agents",
            "strands_available": self.strands_available,
            "orchestration_model": self.config.orchestration_model,
            "kb_enabled": self.config.is_kb_enabled(),
            "kb_id": self.config.kb_id if self.config.is_kb_enabled() else None
        }
