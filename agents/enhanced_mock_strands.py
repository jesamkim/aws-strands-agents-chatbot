"""
실제 KB 검색이 가능한 향상된 Mock Strands Agents
실제 Strands 라이브러리가 없어도 KB 검색 기능 제공
"""

import json
import time
from typing import Dict, List, Any, Optional, Callable
from utils.kb_search import KnowledgeBaseSearcher
from utils.bedrock_client import BedrockClient


class EnhancedMockAgent:
    """실제 KB 검색이 가능한 Mock Agent"""
    
    def __init__(self, config=None, system_prompt=None, tools=None):
        # config가 직접 전달되거나 첫 번째 인자로 전달될 수 있음
        if hasattr(config, 'is_kb_enabled'):
            self.config = config
        else:
            # config가 없으면 기본값 사용
            self.config = config
            
        self.tools = tools or []
        self.kb_searcher = KnowledgeBaseSearcher() if (self.config and self.config.is_kb_enabled()) else None
        self.bedrock_client = BedrockClient()
        self._last_search_results = []  # 검색 결과 저장용
        
        print(f"🤖 Enhanced Mock Agent 초기화 (KB: {self.config.is_kb_enabled() if self.config else False})")
    
    def __call__(self, prompt: str) -> str:
        """Agent 호출 - 실제 KB 검색 수행"""
        try:
            # KB 검색이 필요한지 판단
            if self._needs_kb_search(prompt):
                return self._process_with_kb_search(prompt)
            else:
                return self._process_simple_response(prompt)
                
        except Exception as e:
            return f"처리 중 오류가 발생했습니다: {str(e)}"
    
    def _needs_kb_search(self, prompt: str, conversation_history: List[Dict] = None) -> bool:
        """KB 검색이 필요한지 LLM 기반으로 판단"""
        if not self.config.is_kb_enabled():
            return False
        
        conversation_history = conversation_history or []
        
        try:
            # 대화 연속성 확인
            if self._is_conversation_continuation(prompt, conversation_history):
                print("   🔗 대화 연속성 감지 - KB 검색 불필요")
                return False
            
            # 간단한 인사말 확인
            if self._is_simple_greeting(prompt):
                print("   👋 간단한 인사말 - KB 검색 불필요")
                return False
            
            # LLM을 통한 KB 검색 필요성 판단
            decision_prompt = f"""다음 사용자 질문이 Knowledge Base 검색이 필요한지 판단해주세요:

사용자 질문: {prompt}

판단 기준:
1. 회사 정책, 규정, 제도에 관한 질문 → KB 검색 필요
2. 복리후생, 지원제도에 관한 질문 → KB 검색 필요  
3. 구체적인 절차나 기준에 관한 질문 → KB 검색 필요
4. 일반적인 대화, 인사말 → KB 검색 불필요
5. 개념 설명, 일반 지식 → KB 검색 불필요

다음 형식으로 답변해주세요:
NEEDS_KB_SEARCH: [YES/NO]
REASON: [판단 이유]"""

            # Cross Region Inference용 모델 ID 사용
            model_id = self.config.observation_model
            if "claude-3-5-haiku" in model_id:
                model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            elif "claude-3-5-sonnet" in model_id:
                model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            elif "nova-lite" in model_id:
                model_id = "us.amazon.nova-lite-v1:0"
            elif "nova-micro" in model_id:
                model_id = "us.amazon.nova-micro-v1:0"

            response = self.bedrock_client.invoke_model(
                model_id=model_id,
                prompt=decision_prompt,
                temperature=0.1,  # 일관된 판단
                max_tokens=150,
                system_prompt="당신은 사용자 질문을 분석하여 Knowledge Base 검색이 필요한지 판단하는 전문가입니다."
            )
            
            # 응답 파싱
            lines = response.strip().split('\n')
            needs_search = False
            reason = "판단 실패"
            
            for line in lines:
                if line.startswith('NEEDS_KB_SEARCH:'):
                    needs_search = 'YES' in line.upper()
                elif line.startswith('REASON:'):
                    reason = line.split(':', 1)[1].strip()
            
            print(f"   🤖 KB 검색 필요성 판단: {needs_search} ({reason})")
            return needs_search
            
        except Exception as e:
            print(f"   ⚠️ KB 검색 필요성 판단 오류: {str(e)}")
            # 폴백: 기본적인 휴리스틱 사용
            return self._fallback_kb_search_decision(prompt, conversation_history)
    
    def _is_conversation_continuation(self, prompt: str, conversation_history: List[Dict]) -> bool:
        """대화 연속성 확인"""
        if not conversation_history:
            return False
        
        # 연속성 표현 확인
        continuation_patterns = [
            "다음은", "그럼", "그러면", "또는", "아니면", "그리고", "그런데",
            "그래서", "그렇다면", "계속", "이어서", "추가로", "더", "또", "그 외에",
            "그것", "그거", "이것", "이거", "위에서", "앞서"
        ]
        
        prompt_lower = prompt.lower().strip()
        return any(pattern in prompt_lower for pattern in continuation_patterns)
    
    def _is_simple_greeting(self, prompt: str) -> bool:
        """간단한 인사말 확인"""
        greetings = [
            "안녕", "hello", "hi", "hey", "안녕하세요", "안녕하십니까",
            "좋은 아침", "좋은 오후", "좋은 저녁", "반갑습니다", "처음 뵙겠습니다"
        ]
        
        prompt_lower = prompt.lower().strip()
        return any(greeting in prompt_lower for greeting in greetings)
    
    def _fallback_kb_search_decision(self, prompt: str, conversation_history: List[Dict]) -> bool:
        """폴백 KB 검색 필요성 판단"""
        # 대화 연속성이 있으면 KB 검색 불필요
        if self._is_conversation_continuation(prompt, conversation_history):
            return False
        
        # 간단한 인사말이면 KB 검색 불필요
        if self._is_simple_greeting(prompt):
            return False
        
        # 질문 형태이고 구체적인 내용이 있으면 KB 검색 필요
        if any(char in prompt for char in ["?", "？", "어떻게", "무엇", "언제", "어디서", "왜"]):
            return True
        
        # 기본적으로 KB 검색 수행
        return True
    
    def _process_with_kb_search(self, prompt: str) -> str:
        """KB 검색을 포함한 처리"""
        try:
            print(f"🔍 KB 검색 수행 중...")
            
            # 검색 키워드 추출
            keywords = self._extract_keywords(prompt)
            print(f"   검색 키워드: {keywords}")
            
            # KB 검색 실행
            search_results = self.kb_searcher.search_multiple_queries(
                kb_id=self.config.kb_id,
                queries=keywords,
                max_results_per_query=3
            )
            
            # 검색 결과 저장 (Streamlit 호환성을 위해)
            self._last_search_results = search_results
            
            print(f"   검색 결과: {len(search_results)}개")
            
            if search_results:
                # 검색 결과를 바탕으로 답변 생성
                return self._generate_answer_with_kb(prompt, search_results)
            else:
                return self._generate_fallback_answer(prompt)
                
        except Exception as e:
            print(f"❌ KB 검색 오류: {e}")
            self._last_search_results = []  # 오류 시 빈 리스트
            return self._generate_fallback_answer(prompt)
    
    def _extract_keywords(self, prompt: str) -> List[str]:
        """LLM을 통한 동적 키워드 추출"""
        try:
            keyword_prompt = f"""다음 사용자 질문에서 Knowledge Base 검색에 효과적인 키워드 3개를 추출해주세요:

사용자 질문: {prompt}

키워드 추출 지침:
1. 질문의 핵심 개념을 포함하는 키워드
2. 구체적이고 검색 가능한 용어
3. 너무 일반적이지 않고 너무 구체적이지도 않은 적절한 수준
4. 복합어는 그대로 유지 (예: "난임치료시술비")
5. 동의어나 유사어보다는 원문의 표현 우선

다음 형식으로 답변해주세요:
KEYWORD1: [키워드1]
KEYWORD2: [키워드2]  
KEYWORD3: [키워드3]"""

            # Cross Region Inference용 모델 ID 사용
            model_id = self.config.observation_model
            if "claude-3-5-haiku" in model_id:
                model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            elif "claude-3-5-sonnet" in model_id:
                model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            elif "nova-lite" in model_id:
                model_id = "us.amazon.nova-lite-v1:0"
            elif "nova-micro" in model_id:
                model_id = "us.amazon.nova-micro-v1:0"

            response = self.bedrock_client.invoke_model(
                model_id=model_id,
                prompt=keyword_prompt,
                temperature=0.3,  # 적당한 창의성
                max_tokens=200,
                system_prompt="당신은 검색 키워드 추출 전문가입니다. 사용자 질문에서 가장 효과적인 검색 키워드를 추출할 수 있습니다."
            )
            
            # 키워드 파싱
            keywords = []
            lines = response.strip().split('\n')
            
            for line in lines:
                if line.startswith('KEYWORD'):
                    try:
                        keyword = line.split(':', 1)[1].strip()
                        if keyword and keyword not in keywords:
                            keywords.append(keyword)
                    except:
                        continue
            
            # LLM 추출이 실패한 경우 폴백
            if not keywords:
                print("   ⚠️ LLM 키워드 추출 실패, 폴백 사용")
                keywords = self._fallback_keyword_extraction(prompt)
            
            print(f"   🤖 LLM 추출 키워드: {keywords}")
            return keywords[:3]
            
        except Exception as e:
            print(f"   ❌ LLM 키워드 추출 오류: {str(e)}")
            return self._fallback_keyword_extraction(prompt)
    
    def _fallback_keyword_extraction(self, prompt: str) -> List[str]:
        """LLM 실패 시 폴백 키워드 추출"""
        import re
        
        # 한글 단어 추출 (2글자 이상)
        korean_words = [word for word in re.findall(r'[가-힣]+', prompt) if len(word) >= 2]
        
        keywords = []
        
        # 2-3단어 조합
        if len(korean_words) >= 2:
            keywords.append(f"{korean_words[0]} {korean_words[1]}")
        
        if len(korean_words) >= 3:
            keywords.append(f"{korean_words[0]} {korean_words[1]} {korean_words[2]}")
        
        # 개별 단어 (길이 순)
        sorted_words = sorted(korean_words, key=len, reverse=True)
        for word in sorted_words[:2]:
            if word not in str(keywords):
                keywords.append(word)
        
        return keywords[:3] if keywords else ["정보"]
    
    def _generate_answer_with_kb(self, prompt: str, search_results: List[Dict]) -> str:
        """KB 검색 결과를 바탕으로 답변 생성 - 개선된 버전"""
        try:
            # 검색 결과 컨텍스트 준비
            context_parts = []
            sources = []
            
            for i, result in enumerate(search_results[:5], 1):  # 최대 5개 결과 사용
                content = result.get("content", "")[:400]  # 더 많은 내용 포함
                source = result.get("source", f"문서 {i}")
                score = result.get("score", 0)
                
                context_parts.append(f"[{i}] (관련성: {score:.3f}) {content}")
                sources.append(f"[{i}] {source}")
            
            context = "\n\n".join(context_parts)
            
            # 개선된 답변 생성 프롬프트
            answer_prompt = f"""다음 검색 결과를 바탕으로 사용자 질문에 대한 정확하고 상세한 답변을 생성해주세요:

사용자 질문: {prompt}

검색 결과:
{context}

답변 요구사항:
1. 사용자 질문에 직접적으로 답변하는 형태로 구성
2. 검색 결과의 정보를 활용할 때는 반드시 [1], [2] 형태의 Citation 포함
3. 구체적인 절차, 기준, 조건, 금액 등이 있다면 명확히 설명
4. 검색 결과에 없는 정보는 추측하지 말고 명시적으로 언급
5. 자연스럽고 이해하기 쉬운 한국어로 작성
6. 단순히 검색 결과를 나열하지 말고 질문에 맞게 재구성하여 답변

예시 형태:
- "~에 관한 규정은 다음과 같습니다: [구체적 내용][1]"
- "신청 절차는 [단계별 설명][2]입니다"
- "지원 대상은 [조건 설명][3]에 해당하는 경우입니다"

답변:"""

            # Cross Region Inference용 모델 ID 사용
            model_id = self.config.observation_model
            if "claude-3-5-haiku" in model_id:
                model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            elif "claude-3-5-sonnet" in model_id:
                model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            elif "nova-lite" in model_id:
                model_id = "us.amazon.nova-lite-v1:0"
            elif "nova-micro" in model_id:
                model_id = "us.amazon.nova-micro-v1:0"

            # agent 객체의 bedrock_client 사용
            response = self.agent.bedrock_client.invoke_model(
                model_id=model_id,
                prompt=answer_prompt,
                temperature=0.1,  # 일관된 답변을 위해 낮은 temperature
                max_tokens=1500,  # 더 긴 답변 허용
                system_prompt="당신은 Knowledge Base 검색 결과를 바탕으로 사용자 질문에 정확하고 도움이 되는 답변을 생성하는 전문가입니다. 검색 결과를 단순 나열하지 말고 질문에 맞게 재구성하여 자연스러운 답변을 만드세요."
            )
            
            answer = response.strip()
            
            # Citation이 포함되지 않은 경우 자동 추가
            if not self._has_citations(answer):
                answer = self._add_citations_to_answer(answer, search_results)
            
            # 출처 정보가 없는 경우 추가
            if "**참고 자료:**" not in answer and sources:
                answer += f"\n\n**참고 자료:**\n" + "\n".join(sources)
            
            return answer
            
        except Exception as e:
            print(f"❌ 답변 생성 오류: {e}")
            return self._generate_fallback_answer(prompt)
    
    def _generate_fallback_answer(self, prompt: str) -> str:
        """KB 검색 실패 시 fallback 답변"""
        return f"""죄송합니다. 현재 Knowledge Base에서 관련 정보를 찾을 수 없습니다.

**질문:** {prompt}

**상황:** Knowledge Base 검색이 실패했거나 관련 정보가 없습니다.

**제안:**
1. 질문을 더 구체적으로 바꿔서 다시 시도해 주세요
2. 다른 키워드를 사용해 보세요
3. 일반적인 정보가 필요하시면 KB 없이 답변드릴 수 있습니다

더 도움이 필요하시면 구체적인 질문을 해주세요."""
    
    def _process_simple_response_with_context(self, prompt: str, conversation_history: List[Dict]) -> str:
        """대화 맥락을 고려한 간단한 응답 처리"""
        try:
            # 검색 결과 초기화 (Streamlit 호환성을 위해)
            self._last_search_results = []
            
            # 대화 맥락 구성
            context_text = ""
            if conversation_history:
                recent_messages = conversation_history[-4:]  # 최근 4개 메시지
                for msg in recent_messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "user":
                        context_text += f"사용자: {content}\n"
                    elif role == "assistant":
                        context_text += f"어시스턴트: {content[:200]}...\n"  # 200자로 제한
            
            # 대화 맥락을 고려한 프롬프트
            if context_text:
                full_prompt = f"""이전 대화 맥락:
{context_text}

현재 사용자 질문: {prompt}

위의 대화 맥락을 고려하여 현재 질문에 적절한 답변을 해주세요.

답변 지침:
1. 이전 대화의 내용을 참조하여 자연스러운 연결
2. 연속성 질문("다음은?", "그럼?" 등)의 경우 이전 답변을 이어서 설명
3. 새로운 질문이라면 독립적으로 답변
4. 친근하고 도움이 되는 톤으로 답변

답변:"""
            else:
                full_prompt = f"""사용자 질문: {prompt}

위 질문에 대해 친절하고 도움이 되는 답변을 해주세요.

답변:"""
            
            # Cross Region Inference용 모델 ID 사용
            model_id = self.config.observation_model
            if "claude-3-5-haiku" in model_id:
                model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            elif "claude-3-5-sonnet" in model_id:
                model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            elif "nova-lite" in model_id:
                model_id = "us.amazon.nova-lite-v1:0"
            elif "nova-micro" in model_id:
                model_id = "us.amazon.nova-micro-v1:0"
                
            response = self.bedrock_client.invoke_model(
                model_id=model_id,
                prompt=full_prompt,
                temperature=0.3,
                max_tokens=800,
                system_prompt="당신은 대화의 맥락을 잘 이해하고 연속성 있는 답변을 제공하는 친근한 AI 어시스턴트입니다."
            )
            
            return response.strip()
            
        except Exception as e:
            self._last_search_results = []  # 오류 시에도 빈 리스트 설정
            return f"안녕하세요! 무엇을 도와드릴까요? (대화 맥락 처리 중 오류: {str(e)})"
    
    def _process_simple_response(self, prompt: str) -> str:
        """간단한 응답 처리 (기존 호환성)"""
        return self._process_simple_response_with_context(prompt, [])


def enhanced_mock_tool(func: Callable) -> Callable:
    """향상된 Mock tool 데코레이터"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return f"도구 실행 오류: {str(e)}"
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


class EnhancedMockStrandsAgent:
    """향상된 Mock Strands Agent (실제 KB 검색 지원)"""
    
    def __init__(self, config):
        self.config = config
        self.agent = EnhancedMockAgent(config)
        print(f"🚀 Strands Agent 초기화 완료")
    
    def __call__(self, prompt: str) -> str:
        return self.agent(prompt)
    
    def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        ReAct 패턴을 구현한 쿼리 처리 메서드 (Streamlit 호환성)
        
        Args:
            query: 사용자 질문
            conversation_history: 대화 히스토리
            
        Returns:
            처리 결과 딕셔너리
        """
        start_time = time.time()
        conversation_history = conversation_history or []
        
        try:
            # KB 검색이 필요한지 판단 (대화 히스토리 포함)
            if not self.agent._needs_kb_search(query, conversation_history):
                # KB 검색이 불필요한 경우 직접 답변
                result = self.agent._process_simple_response_with_context(query, conversation_history)
                processing_time = time.time() - start_time
                
                return {
                    "final_answer": result,
                    "content": result,
                    "search_results": [],
                    "processing_time": processing_time,
                    "framework": "Strands (Direct)",
                    "iterations": 1,
                    "steps": [
                        {
                            "type": "Direct Response",
                            "content": f"KB 검색 불필요, 직접 답변 생성",
                            "model": "Enhanced Mock Agent"
                        }
                    ],
                    "model_info": {
                        "framework": "Strands",
                        "kb_enabled": self.config.is_kb_enabled() if self.config else False
                    },
                    "citations": [],
                    "context_analysis": {
                        "needs_kb_search": False,
                        "has_context": len(conversation_history) > 0
                    }
                }
            
            # ReAct 루프 실행 (최대 5회 반복)
            return self._execute_react_loop(query, conversation_history, start_time)
            
        except Exception as e:
            processing_time = time.time() - start_time
            return {
                "final_answer": f"처리 중 오류가 발생했습니다: {str(e)}",
                "content": f"처리 중 오류가 발생했습니다: {str(e)}",
                "search_results": [],
                "processing_time": processing_time,
                "framework": "Strands",
                "iterations": 1,
                "steps": [
                    {
                        "type": "Error",
                        "content": str(e),
                        "model": "Enhanced Mock Agent"
                    }
                ],
                "model_info": {
                    "framework": "Strands",
                    "error": True
                },
                "citations": [],
                "context_analysis": {}
            }
    
    def _execute_react_loop(self, query: str, conversation_history: List[Dict], start_time: float) -> Dict:
        """ReAct 루프 실행"""
        steps = []
        all_search_results = []
        previous_keywords = []
        max_iterations = 5
        
        for iteration in range(1, max_iterations + 1):
            print(f"\n🔄 Strands - ReAct 반복 {iteration}/{max_iterations}")
            
            # 1. Orchestration (키워드 생성)
            orchestration_step = self._orchestration_step(query, previous_keywords, iteration)
            steps.append(orchestration_step)
            
            current_keywords = orchestration_step.get("parsed_result", {}).get("search_keywords", [])
            if not current_keywords:
                break
            
            # 2. Action (KB 검색)
            action_step = self._action_step(current_keywords)
            steps.append(action_step)
            
            search_results = action_step.get("search_results", [])
            all_search_results.extend(search_results)
            
            # 3. Observation (품질 평가)
            observation_step = self._observation_step(query, search_results, iteration)
            steps.append(observation_step)
            
            # 최종 답변인지 확인
            if observation_step.get("parsed_result", {}).get("is_final_answer", False):
                final_answer = observation_step.get("parsed_result", {}).get("final_answer", "")
                break
            
            # 재시도 키워드 확인
            retry_keywords = observation_step.get("parsed_result", {}).get("retry_keywords", [])
            if retry_keywords:
                previous_keywords.extend(current_keywords)
                continue
            else:
                # 재시도 키워드가 없으면 종료
                final_answer = observation_step.get("content", "답변을 생성할 수 없습니다.")
                break
        
        # 최종 답변이 설정되지 않은 경우
        if 'final_answer' not in locals():
            final_answer = "최대 반복 횟수에 도달했습니다. 부분적인 정보를 제공합니다."
            if all_search_results:
                final_answer = self._generate_final_answer_from_results(query, all_search_results)
        
        processing_time = time.time() - start_time
        
        return {
            "final_answer": final_answer,
            "content": final_answer,
            "search_results": all_search_results,
            "processing_time": processing_time,
            "framework": "Strands (ReAct)",
            "iterations": iteration,
            "steps": steps,
            "model_info": {
                "framework": "Strands",
                "kb_enabled": self.config.is_kb_enabled() if self.config else False,
                "react_enabled": True
            },
            "citations": self._extract_citations(all_search_results),
            "context_analysis": {
                "needs_kb_search": True,
                "has_context": len(conversation_history) > 0,
                "total_iterations": iteration
            }
        }
    
    def _orchestration_step(self, query: str, previous_keywords: List[str], iteration: int) -> Dict:
        """Orchestration 단계 - 키워드 생성"""
        try:
            if iteration == 1:
                # 첫 번째 반복: 기본 키워드 추출
                keywords = self.agent._extract_keywords(query)
            else:
                # 재시도: LLM을 통한 새로운 키워드 생성
                keywords = self._generate_retry_keywords_llm(query, previous_keywords)
            
            print(f"   🎯 생성된 키워드: {keywords}")
            
            return {
                "type": "Orchestration",
                "content": f"검색 키워드 생성: {keywords}",
                "model": "Enhanced Mock Orchestration",
                "parsed_result": {
                    "search_keywords": keywords,
                    "iteration": iteration,
                    "intent": f"KB 검색을 통한 정보 수집 ({iteration}회차)"
                }
            }
            
        except Exception as e:
            return {
                "type": "Orchestration",
                "content": f"키워드 생성 오류: {str(e)}",
                "model": "Enhanced Mock Orchestration",
                "parsed_result": {
                    "search_keywords": [],
                    "error": True
                }
            }
    
    def _action_step(self, keywords: List[str]) -> Dict:
        """Action 단계 - KB 검색"""
        try:
            print(f"   ⚡ KB 검색 실행: {keywords}")
            
            search_results = self.agent.kb_searcher.search_multiple_queries(
                kb_id=self.config.kb_id,
                queries=keywords,
                max_results_per_query=3
            )
            
            print(f"   📚 검색 결과: {len(search_results)}개")
            
            return {
                "type": "Action",
                "content": f"KB 검색 완료: {len(search_results)}개 결과",
                "model": "Enhanced Mock Action",
                "search_results": search_results,
                "parsed_result": {
                    "search_keywords": keywords,
                    "results_count": len(search_results),
                    "search_type": "Knowledge Base"
                }
            }
            
        except Exception as e:
            print(f"   ❌ KB 검색 오류: {str(e)}")
            return {
                "type": "Action",
                "content": f"KB 검색 오류: {str(e)}",
                "model": "Enhanced Mock Action",
                "search_results": [],
                "parsed_result": {
                    "search_keywords": keywords,
                    "results_count": 0,
                    "error": True
                }
            }
    
    def _observation_step(self, query: str, search_results: List[Dict], iteration: int) -> Dict:
        """Observation 단계 - 품질 평가 및 답변 생성"""
        try:
            # 품질 평가
            quality_assessment = self._assess_search_quality_llm(query, search_results, iteration)
            
            print(f"   👁️ 품질 평가: {quality_assessment['reason']} (점수: {quality_assessment['score']:.3f})")
            
            if iteration >= 5 or not quality_assessment["needs_retry"]:
                # 최종 답변 생성
                final_answer = self._generate_final_answer_from_results(query, search_results)
                
                return {
                    "type": "Observation",
                    "content": final_answer,
                    "model": "Enhanced Mock Observation",
                    "parsed_result": {
                        "is_final_answer": True,
                        "final_answer": final_answer,
                        "needs_retry": False,
                        "quality_score": quality_assessment["score"],
                        "iteration": iteration
                    }
                }
            else:
                # 재시도 필요
                retry_keywords = self._generate_retry_keywords_simple(query, search_results)
                
                return {
                    "type": "Observation",
                    "content": f"검색 결과 불충분, 재시도 필요: {retry_keywords}",
                    "model": "Enhanced Mock Observation",
                    "parsed_result": {
                        "is_final_answer": False,
                        "final_answer": "",
                        "needs_retry": True,
                        "retry_keywords": retry_keywords,
                        "quality_score": quality_assessment["score"],
                        "iteration": iteration
                    }
                }
                
        except Exception as e:
            print(f"   ❌ Observation 오류: {str(e)}")
            return {
                "type": "Observation",
                "content": f"품질 평가 오류: {str(e)}",
                "model": "Enhanced Mock Observation",
                "parsed_result": {
                    "is_final_answer": True,
                    "final_answer": "처리 중 오류가 발생했습니다.",
                    "needs_retry": False,
                    "error": True
                }
            }


    def _assess_search_quality_llm(self, query: str, search_results: List[Dict], iteration: int) -> Dict:
        """LLM을 통한 검색 결과 품질 평가"""
        if not search_results:
            return {
                "needs_retry": iteration < 5,
                "reason": "검색 결과 없음",
                "score": 0.0
            }
        
        try:
            # 검색 결과 요약
            results_summary = ""
            for i, result in enumerate(search_results[:3], 1):
                content = result.get('content', '')[:150]
                score = result.get('score', 0)
                results_summary += f"결과 {i} (점수: {score:.3f}): {content}...\n"
            
            # 간단한 품질 평가 (LLM 없이)
            avg_score = sum(result.get('score', 0) for result in search_results) / len(search_results)
            
            # 반복 횟수에 따른 임계값
            if iteration <= 2:
                threshold = 0.5
            elif iteration <= 4:
                threshold = 0.4
            else:
                threshold = 0.2
            
            needs_retry = avg_score < threshold and iteration < 5
            
            return {
                "needs_retry": needs_retry,
                "reason": f"평균 점수 {avg_score:.3f} (임계값: {threshold}, {iteration}회차)",
                "score": avg_score
            }
            
        except Exception as e:
            return {
                "needs_retry": iteration < 5,
                "reason": f"평가 오류: {str(e)}",
                "score": 0.0
            }
    
    def _generate_retry_keywords_llm(self, query: str, previous_keywords: List[str]) -> List[str]:
        """LLM을 통한 재시도 키워드 생성"""
        try:
            retry_prompt = f"""이전 검색이 실패했습니다. 더 나은 검색 결과를 얻기 위한 새로운 키워드를 생성해주세요:

원본 질문: {query}
이전 검색 키워드: {previous_keywords}

새로운 키워드 생성 전략:
1. 동의어나 유사어 사용
2. 더 구체적이거나 더 일반적인 표현 시도
3. 다른 관점에서의 접근
4. 관련 분야의 전문 용어 활용
5. 이전 키워드와는 다른 새로운 접근

다음 형식으로 3개의 새로운 키워드를 제안해주세요:
KEYWORD1: [키워드1]
KEYWORD2: [키워드2]
KEYWORD3: [키워드3]"""

            # Cross Region Inference용 모델 ID 사용
            model_id = self.config.observation_model
            if "claude-3-5-haiku" in model_id:
                model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            elif "claude-3-5-sonnet" in model_id:
                model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            elif "nova-lite" in model_id:
                model_id = "us.amazon.nova-lite-v1:0"
            elif "nova-micro" in model_id:
                model_id = "us.amazon.nova-micro-v1:0"

            response = self.agent.bedrock_client.invoke_model(
                model_id=model_id,
                prompt=retry_prompt,
                temperature=0.7,  # 더 창의적인 키워드 생성
                max_tokens=300,
                system_prompt="당신은 검색 키워드 최적화 전문가입니다. 실패한 검색을 개선하기 위한 효과적인 대안 키워드를 생성할 수 있습니다."
            )
            
            # 키워드 파싱
            new_keywords = []
            lines = response.strip().split('\n')
            
            for line in lines:
                if line.startswith('KEYWORD'):
                    try:
                        keyword = line.split(':', 1)[1].strip()
                        if keyword and keyword not in new_keywords and keyword not in str(previous_keywords):
                            new_keywords.append(keyword)
                    except:
                        continue
            
            # LLM 생성이 실패한 경우 폴백
            if not new_keywords:
                print("   ⚠️ LLM 재시도 키워드 생성 실패, 폴백 사용")
                new_keywords = self._generate_retry_keywords_simple(query, [])
            
            print(f"   🤖 LLM 재시도 키워드: {new_keywords}")
            return new_keywords[:3]
            
        except Exception as e:
            print(f"   ❌ LLM 재시도 키워드 생성 오류: {str(e)}")
            return self._generate_retry_keywords_simple(query, [])
    
    def _generate_retry_keywords_simple(self, query: str, search_results: List[Dict]) -> List[str]:
        """간단한 재시도 키워드 생성"""
        import re
        korean_words = re.findall(r'[가-힣]+', query)
        
        # 기본 키워드 조합
        keywords = []
        if len(korean_words) >= 2:
            keywords.append(f"{korean_words[0]} {korean_words[1]}")
        
        for word in korean_words:
            if len(word) >= 2:
                keywords.append(word)
        
        return keywords[:3] if keywords else ["정보", "정책"]
    
    def _generate_final_answer_from_results(self, query: str, search_results: List[Dict]) -> str:
        """검색 결과를 바탕으로 최종 답변 생성 - LLM 기반 재가공"""
        if not search_results:
            return f"""죄송합니다. '{query}'에 대한 구체적인 정보를 Knowledge Base에서 찾을 수 없습니다.

더 구체적인 키워드로 다시 검색하시거나, 관련 부서에 직접 문의하시기 바랍니다."""
        
        try:
            # 검색 결과 컨텍스트 준비
            context_parts = []
            sources = []
            
            for i, result in enumerate(search_results[:5], 1):
                content = result.get("content", "")[:400]  # 더 많은 내용 포함
                source = result.get("source", f"문서 {i}")
                score = result.get("score", 0)
                
                context_parts.append(f"[{i}] (관련성: {score:.3f}) {content}")
                sources.append(f"[{i}] {source}")
            
            context = "\n\n".join(context_parts)
            
            # LLM을 통한 답변 재가공
            answer_prompt = f"""다음 검색 결과를 바탕으로 사용자 질문에 대한 정확하고 상세한 답변을 생성해주세요:

사용자 질문: {query}

검색 결과:
{context}

답변 요구사항:
1. 사용자 질문에 직접적으로 답변하는 형태로 재구성
2. 검색 결과의 정보를 활용할 때는 반드시 [1], [2] 형태의 Citation 포함
3. 구체적인 절차, 기준, 조건 등이 있다면 명확히 설명
4. 검색 결과에 없는 정보는 추측하지 말고 "추가 확인이 필요합니다"라고 명시
5. 자연스럽고 이해하기 쉬운 한국어로 작성
6. 단순히 검색 결과를 나열하지 말고 질문에 맞게 재구성

답변:"""

            # Cross Region Inference용 모델 ID 사용
            model_id = self.config.observation_model
            if "claude-3-5-haiku" in model_id:
                model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            elif "claude-3-5-sonnet" in model_id:
                model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            elif "nova-lite" in model_id:
                model_id = "us.amazon.nova-lite-v1:0"
            elif "nova-micro" in model_id:
                model_id = "us.amazon.nova-micro-v1:0"

            # agent 객체의 bedrock_client 사용
            response = self.agent.bedrock_client.invoke_model(
                model_id=model_id,
                prompt=answer_prompt,
                temperature=0.1,  # 일관된 답변을 위해 낮은 temperature
                max_tokens=1500,  # 더 긴 답변 허용
                system_prompt="당신은 Knowledge Base 검색 결과를 바탕으로 사용자 질문에 정확하고 도움이 되는 답변을 생성하는 전문가입니다. 검색 결과를 단순 나열하지 말고 질문에 맞게 재구성하여 답변하세요."
            )
            
            answer = response.strip()
            
            # Citation이 포함되지 않은 경우 자동 추가
            if not self._has_citations(answer):
                answer = self._add_citations_to_answer(answer, search_results)
            
            # 출처 정보가 없는 경우 추가
            if "**참고 자료:**" not in answer and sources:
                answer += f"\n\n**참고 자료:**\n" + "\n".join(sources)
            
            return answer
            
        except Exception as e:
            print(f"❌ LLM 답변 생성 오류: {str(e)}")
            # 폴백: 기본 답변 생성
            return self._generate_fallback_answer_from_results(query, search_results)
    
    def _has_citations(self, text: str) -> bool:
        """텍스트에 Citation이 포함되어 있는지 확인"""
        import re
        citation_pattern = r'\[\d+\]'
        return bool(re.search(citation_pattern, text))
    
    def _add_citations_to_answer(self, answer: str, search_results: List[Dict]) -> str:
        """답변에 Citation 자동 추가"""
        try:
            # 검색 결과의 주요 키워드를 찾아서 Citation 추가
            enhanced_answer = answer
            
            for i, result in enumerate(search_results[:3], 1):
                content = result.get("content", "")
                # 검색 결과의 주요 단어들을 찾아서 Citation 추가
                import re
                key_phrases = re.findall(r'[가-힣]{2,}', content)[:5]  # 주요 한글 단어 5개
                
                for phrase in key_phrases:
                    if phrase in enhanced_answer and f"[{i}]" not in enhanced_answer:
                        enhanced_answer = enhanced_answer.replace(phrase, f"{phrase}[{i}]", 1)
                        break
            
            return enhanced_answer
            
        except Exception as e:
            return answer
    
    def _generate_fallback_answer_from_results(self, query: str, search_results: List[Dict]) -> str:
        """LLM 실패 시 폴백 답변 생성"""
        try:
            # 검색 결과에서 가장 관련성 높은 내용 추출
            best_results = sorted(search_results, key=lambda x: x.get('score', 0), reverse=True)[:3]
            
            answer = f"'{query}'에 대한 정보를 찾았습니다:\n\n"
            
            for i, result in enumerate(best_results, 1):
                content = result.get("content", "")[:200]
                source = result.get("source", f"문서 {i}")
                answer += f"**{i}. ** {content}... [출처: {source}]\n\n"
            
            answer += "더 자세한 정보가 필요하시면 관련 부서에 문의하시기 바랍니다."
            
            return answer
            
        except Exception as e:
            return f"검색 결과 처리 중 오류가 발생했습니다: {str(e)}"
    
    def _extract_citations(self, search_results: List[Dict]) -> List[Dict]:
        """검색 결과에서 인용 정보 추출"""
        citations = []
        for i, result in enumerate(search_results[:5], 1):
            citations.append({
                "id": i,
                "content": result.get("content", "")[:200],
                "source": result.get("source", f"문서 {i}"),
                "score": result.get("score", 0)
            })

# 기존 코드와의 호환성을 위한 별칭
MockAgent = EnhancedMockAgent
mock_tool = enhanced_mock_tool
