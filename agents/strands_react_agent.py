"""
AWS Strands Agents 기반 ReAct 챗봇
기존 수동 ReAct 루프를 Strands Agents 프레임워크로 대체
"""

import json
import time
from typing import Dict, List, Any, Optional

# Strands import with fallback to mock
try:
    from strands import Agent
    STRANDS_AVAILABLE = True
except ImportError:
    print("⚠️ Strands Agents 라이브러리를 찾을 수 없습니다. Mock 버전을 사용합니다.")
    from .mock_strands import MockAgent as Agent
    STRANDS_AVAILABLE = False

from utils.config import AgentConfig
from .strands_tools import StrandsToolsManager


class StrandsReActChatbot:
    """
    AWS Strands Agents 기반 ReAct 챗봇
    
    주요 특징:
    - Strands Agents 프레임워크 활용
    - 자동화된 ReAct 루프
    - 도구 기반 KB 검색 및 분석
    - 대화 맥락 인식
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.tools_manager = StrandsToolsManager(config)
        
        # 메인 오케스트레이터 에이전트 생성
        self.orchestrator = self._create_orchestrator_agent()
        
        # KB 검색 전문 에이전트 생성
        self.kb_search_agent = self._create_kb_search_agent()
        
        # 답변 생성 전문 에이전트 생성
        self.answer_agent = self._create_answer_agent()
    
    def _create_orchestrator_agent(self) -> Agent:
        """메인 오케스트레이터 에이전트 생성"""
        system_prompt = f"""{self.config.system_prompt or '당신은 도움이 되는 AI 어시스턴트입니다.'}

당신은 사용자 질문을 분석하고 적절한 처리 방법을 결정하는 오케스트레이터입니다.

**주요 역할:**
1. 대화 맥락 분석 (연속성 질문, 인사말 등)
2. KB 검색 필요성 판단
3. 적절한 전문 에이전트에게 작업 위임
4. 최종 답변 조율

**처리 우선순위:**
1. 대화 연속성 질문 → 직접 답변
2. 간단한 인사말 → 직접 답변  
3. KB_ID 없음 → 일반 지식으로 답변
4. KB_ID 있음 → KB 검색 후 답변

**도구 사용 지침:**
- conversation_context_analyzer: 먼저 대화 맥락을 분석하세요
- kb_search_tool: KB 검색이 필요한 경우에만 사용
- citation_generator: 검색 결과가 있을 때 Citation 추가

항상 한국어로 응답하세요."""
        
        return Agent(
            system_prompt=system_prompt,
            tools=self.tools_manager.get_all_tools()
        )
    
    def _create_kb_search_agent(self) -> Agent:
        """KB 검색 전문 에이전트 생성"""
        system_prompt = """당신은 Knowledge Base 검색 전문가입니다.

**주요 역할:**
1. 최적의 검색 키워드 생성
2. KB 검색 실행
3. 검색 결과 품질 평가
4. 필요시 재검색 수행

**검색 전략:**
- 초기 검색: 핵심 키워드 3개로 검색
- 품질 평가: 관련성 점수와 내용 길이 확인
- 재검색: 품질이 낮으면 대체 키워드로 재시도 (최대 5회)

**품질 기준:**
- 1-2회차: 엄격한 기준 (평균 점수 0.5 이상)
- 3-4회차: 완화된 기준 (평균 점수 0.4 이상)  
- 5회차: 매우 완화된 기준 (평균 점수 0.2 이상)

항상 한국어로 응답하세요."""
        
        return Agent(
            system_prompt=system_prompt,
            tools=[
                self.tools_manager.keyword_generator,
                self.tools_manager.kb_search_tool,
                self.tools_manager.search_quality_assessor
            ]
        )
    
    def _create_answer_agent(self) -> Agent:
        """답변 생성 전문 에이전트 생성"""
        system_prompt = f"""{self.config.system_prompt or '당신은 도움이 되는 AI 어시스턴트입니다.'}

당신은 검색 결과를 바탕으로 정확하고 유용한 답변을 생성하는 전문가입니다.

**답변 생성 원칙:**
1. 검색 결과가 있으면 반드시 활용하고 Citation 포함
2. 검색 결과가 없으면 일반 지식으로 도움되는 답변 제공
3. 대화 맥락을 고려한 자연스러운 답변
4. 구체적이고 실용적인 정보 제공

**Citation 규칙:**
- 검색 결과 사용 시 [1], [2] 형태로 출처 표시
- 답변 마지막에 "**참고 자료:**" 섹션 포함
- 검색 결과에 없는 정보는 추측하지 않음

**대화 연속성:**
- 이전 대화 내용을 정확히 기억하고 참조
- "다음은?", "그럼?" 같은 연속성 질문에 적절히 대응
- 자연스러운 대화 흐름 유지

항상 한국어로 응답하세요."""
        
        return Agent(
            system_prompt=system_prompt,
            tools=[self.tools_manager.citation_generator]
        )
    
    async def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        사용자 쿼리 처리 (Strands Agents 기반)
        
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
            
            # 1단계: 대화 맥락 분석
            context_analysis = await self._analyze_conversation_context(query, conversation_history)
            
            # 2단계: 처리 방법 결정 및 실행
            if context_analysis.get("is_greeting"):
                result = await self._handle_greeting(query)
            elif context_analysis.get("is_continuation"):
                result = await self._handle_continuation(query, conversation_history)
            elif not self.config.is_kb_enabled():
                result = await self._handle_direct_answer(query, conversation_history)
            else:
                result = await self._handle_kb_search_flow(query, conversation_history, context_analysis)
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            return {
                "type": "StrandsReAct",
                "content": result.get("answer", "답변을 생성할 수 없습니다."),
                "processing_time": processing_time,
                "context_analysis": context_analysis,
                "search_results": result.get("search_results", []),
                "citations": result.get("citations", []),
                "iterations": result.get("iterations", 1),
                "error": False
            }
            
        except Exception as e:
            return {
                "type": "StrandsReAct",
                "content": f"처리 중 오류가 발생했습니다: {str(e)}",
                "processing_time": time.time() - start_time,
                "error": True
            }
    
    async def _analyze_conversation_context(self, query: str, history: List[Dict]) -> Dict:
        """대화 맥락 분석"""
        try:
            # Strands Agent를 통한 맥락 분석
            context_prompt = f"""다음 대화 맥락을 분석해주세요:

현재 질문: {query}
대화 히스토리: {json.dumps(history[-3:], ensure_ascii=False) if history else '없음'}

conversation_context_analyzer 도구를 사용하여 분석하고 결과를 JSON 형태로 반환하세요."""
            
            response = self.orchestrator(context_prompt)
            
            # 응답에서 JSON 추출
            import re
            json_match = re.search(r'\{.*\}', str(response), re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # 폴백 분석
            return self._fallback_context_analysis(query, history)
            
        except Exception as e:
            return self._fallback_context_analysis(query, history)
    
    def _fallback_context_analysis(self, query: str, history: List[Dict]) -> Dict:
        """폴백 맥락 분석"""
        continuation_patterns = ["다음은", "그럼", "그러면", "또는", "계속"]
        greetings = ["안녕", "hello", "hi"]
        
        return {
            "is_continuation": any(p in query.lower() for p in continuation_patterns),
            "is_greeting": any(g in query.lower() for g in greetings) and len(query) < 20,
            "has_context": len(history) > 0,
            "needs_kb_search": self.config.is_kb_enabled()
        }
    
    async def _handle_greeting(self, query: str) -> Dict:
        """인사말 처리"""
        greeting_prompt = f"""사용자가 인사말을 했습니다: "{query}"

친근하고 도움이 되는 인사말로 응답해주세요. 어떤 도움을 드릴 수 있는지 안내하세요."""
        
        response = self.answer_agent(greeting_prompt)
        
        return {
            "answer": str(response),
            "search_results": [],
            "citations": [],
            "iterations": 1
        }
    
    async def _handle_continuation(self, query: str, history: List[Dict]) -> Dict:
        """대화 연속성 질문 처리"""
        # 이전 대화 맥락 구성
        context_text = ""
        if history:
            for msg in history[-4:]:  # 최근 4개 메시지
                role = msg.get("role", "")
                content = msg.get("content", "")
                context_text += f"{role}: {content}\n"
        
        continuation_prompt = f"""이전 대화 맥락:
{context_text}

현재 연속성 질문: {query}

이전 대화의 내용을 바탕으로 현재 질문에 대한 적절한 답변을 생성해주세요.
이전 답변에서 언급한 내용을 구체적으로 확장하거나 보완하세요."""
        
        response = self.answer_agent(continuation_prompt)
        
        return {
            "answer": str(response),
            "search_results": [],
            "citations": [],
            "iterations": 1
        }
    
    async def _handle_direct_answer(self, query: str, history: List[Dict]) -> Dict:
        """직접 답변 처리 (KB 없음)"""
        # 대화 맥락 포함
        context_text = ""
        if history:
            for msg in history[-3:]:
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]
                context_text += f"{role}: {content}\n"
        
        direct_prompt = f"""이전 대화 맥락:
{context_text}

현재 질문: {query}

Knowledge Base가 없으므로 일반적인 지식을 바탕으로 도움이 되는 답변을 제공해주세요.
이전 대화와 관련이 있다면 그 연관성을 언급하면서 답변해주세요."""
        
        response = self.answer_agent(direct_prompt)
        
        return {
            "answer": str(response),
            "search_results": [],
            "citations": [],
            "iterations": 1
        }
    
    async def _handle_kb_search_flow(self, query: str, history: List[Dict], context_analysis: Dict) -> Dict:
        """KB 검색 플로우 처리"""
        max_iterations = 5
        current_iteration = 1
        search_results = []
        previous_keywords = []
        
        while current_iteration <= max_iterations:
            print(f"🔄 KB 검색 반복 {current_iteration}회차")
            
            # 키워드 생성
            if current_iteration == 1:
                keywords_result = await self._generate_initial_keywords(query)
            else:
                keywords_result = await self._generate_retry_keywords(query, previous_keywords)
            
            keywords = keywords_result.get("keywords", [])
            if not keywords:
                break
            
            print(f"   🔍 검색 키워드: {keywords}")
            previous_keywords.extend(keywords)
            
            # KB 검색 실행
            search_prompt = f"""다음 키워드로 Knowledge Base 검색을 수행하세요:
키워드: {keywords}
최대 결과: 5개

kb_search_tool을 사용하여 검색하고 결과를 분석하세요."""
            
            search_response = self.kb_search_agent(search_prompt)
            
            # 검색 결과 추출
            try:
                import re
                json_match = re.search(r'\{.*\}', str(search_response), re.DOTALL)
                if json_match:
                    search_data = json.loads(json_match.group())
                    if search_data.get("success"):
                        search_results = search_data.get("results", [])
            except:
                pass
            
            # 품질 평가
            quality_result = await self._assess_search_quality(search_results, current_iteration)
            
            if quality_result.get("is_sufficient") or current_iteration >= max_iterations:
                print(f"   ✅ 검색 완료: {quality_result.get('reason')}")
                break
            else:
                print(f"   🔄 재시도 필요: {quality_result.get('reason')}")
                current_iteration += 1
        
        # 최종 답변 생성
        answer = await self._generate_final_answer(query, history, search_results, current_iteration)
        
        return {
            "answer": answer,
            "search_results": search_results,
            "citations": self._extract_citations(search_results),
            "iterations": current_iteration
        }
    
    async def _generate_initial_keywords(self, query: str) -> Dict:
        """초기 키워드 생성"""
        try:
            keywords_prompt = f"""다음 질문에 대한 최적의 검색 키워드를 생성하세요:
질문: {query}
KB 설명: {self.config.kb_description}

keyword_generator 도구를 사용하여 키워드를 생성하세요."""
            
            response = self.kb_search_agent(keywords_prompt)
            
            # JSON 추출
            import re
            json_match = re.search(r'\{.*\}', str(response), re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return {"keywords": [query[:20]]}
            
        except Exception as e:
            return {"keywords": [query[:20]]}
    
    async def _generate_retry_keywords(self, query: str, previous_keywords: List[str]) -> Dict:
        """재시도 키워드 생성"""
        try:
            retry_prompt = f"""이전 검색 키워드로 충분한 결과를 얻지 못했습니다.
질문: {query}
이전 키워드: {previous_keywords}

keyword_generator 도구를 사용하여 대체 키워드를 생성하세요."""
            
            response = self.kb_search_agent(retry_prompt)
            
            # JSON 추출
            import re
            json_match = re.search(r'\{.*\}', str(response), re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return {"keywords": []}
            
        except Exception as e:
            return {"keywords": []}
    
    async def _assess_search_quality(self, search_results: List[Dict], iteration: int) -> Dict:
        """검색 품질 평가"""
        try:
            quality_prompt = f"""다음 검색 결과의 품질을 평가하세요:
검색 결과: {json.dumps(search_results, ensure_ascii=False)}
현재 반복: {iteration}회차

search_quality_assessor 도구를 사용하여 품질을 평가하세요."""
            
            response = self.kb_search_agent(quality_prompt)
            
            # JSON 추출
            import re
            json_match = re.search(r'\{.*\}', str(response), re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return {"is_sufficient": iteration >= 5, "reason": "평가 실패"}
            
        except Exception as e:
            return {"is_sufficient": iteration >= 5, "reason": f"평가 오류: {str(e)}"}
    
    async def _generate_final_answer(self, query: str, history: List[Dict], search_results: List[Dict], iterations: int) -> str:
        """최종 답변 생성"""
        try:
            # 대화 맥락 구성
            context_text = ""
            if history:
                for msg in history[-3:]:
                    role = msg.get("role", "")
                    content = msg.get("content", "")[:200]
                    context_text += f"{role}: {content}\n"
            
            # 검색 결과 텍스트 구성
            results_text = ""
            if search_results:
                for i, result in enumerate(search_results):
                    content = result.get("content", "")[:400]
                    source = result.get("source", "")
                    results_text += f"[{i+1}] {content}...\n출처: {source}\n\n"
            
            answer_prompt = f"""이전 대화 맥락:
{context_text}

현재 질문: {query}

Knowledge Base 검색 결과 ({iterations}회 검색):
{results_text}

위의 검색 결과를 바탕으로 사용자 질문에 대한 정확하고 상세한 답변을 생성해주세요.

**중요 요구사항:**
1. 검색 결과 사용 시 반드시 [1], [2] 형태로 Citation 포함
2. 답변 마지막에 "**참고 자료:**" 섹션 추가
3. 검색 결과에 없는 정보는 추측하지 않음
4. 구체적이고 실용적인 답변 제공

citation_generator 도구를 사용하여 Citation을 포함한 답변을 생성하세요."""
            
            response = self.answer_agent(answer_prompt)
            return str(response)
            
        except Exception as e:
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _extract_citations(self, search_results: List[Dict]) -> List[Dict]:
        """Citation 정보 추출"""
        citations = []
        for i, result in enumerate(search_results):
            citations.append({
                "id": i + 1,
                "source": result.get("source", f"출처 {i+1}"),
                "score": result.get("score", 0)
            })
        return citations
    
    def get_model_info(self) -> Dict:
        """모델 정보 반환"""
        return {
            "framework": "AWS Strands Agents",
            "orchestration_model": self.config.orchestration_model,
            "action_model": self.config.action_model,
            "observation_model": self.config.observation_model,
            "kb_enabled": self.config.is_kb_enabled(),
            "kb_id": self.config.kb_id if self.config.is_kb_enabled() else None
        }
