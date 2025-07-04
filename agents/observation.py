"""
Citation 기능이 강화된 Observation Agent
KB 검색 결과에 대한 명확한 Citation 표시
"""

import json
from typing import Dict, List, Any
from utils.config import AgentConfig
from utils.bedrock_client import BedrockClient


class CitationEnhancedObservationAgent:
    """
    Citation 기능이 강화된 Observation Agent
    
    주요 개선사항:
    - KB 검색 결과에 대한 명확한 Citation 표시
    - 출처 정보 자동 포함
    - 검색 결과 기반 답변 생성 강화
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.bedrock_client = BedrockClient()
    
    def observe(self, context: Dict, previous_steps: List) -> Dict:
        """Citation이 강화된 결과 분석 및 다음 단계 결정"""
        try:
            # 가장 최근 Action 결과 찾기
            action_result = None
            orchestration_result = None
            
            for step in reversed(previous_steps):
                if step.get("type") == "Action" and action_result is None:
                    action_result = step
                elif step.get("type") == "Orchestration" and orchestration_result is None:
                    orchestration_result = step
                
                if action_result and orchestration_result:
                    break
            
            # Orchestration에서 맥락 정보 추출
            context_info = self._extract_context_info(orchestration_result)
            
            if not action_result:
                # Action이 없는 경우 (KB 검색 불필요한 경우)
                return self._handle_no_action_case_with_context(context, previous_steps, context_info)
            
            # Action 결과 분석
            search_results = action_result.get("search_results", [])
            action_error = action_result.get("parsed_result", {}).get("error", False)
            search_keywords = action_result.get("parsed_result", {}).get("search_keywords", [])
            
            # 검색 결과가 있는 경우 - Citation 강화
            if search_results and not action_error:
                return self._analyze_search_results_with_enhanced_citation(search_results, context, search_keywords, context_info)
            
            # 검색 결과가 없지만 오류가 아닌 경우
            elif not search_results and not action_error:
                return self._handle_no_search_case_with_context(context, previous_steps, context_info)
            
            # 검색 실패 또는 오류인 경우
            else:
                return self._handle_search_failure_with_context(action_result, context, search_keywords, context_info)
                
        except Exception as e:
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": f"Observation 수행 중 오류 발생: {str(e)}",
                "parsed_result": {
                    "analysis": "오류 발생",
                    "is_final_answer": True,
                    "final_answer": "죄송합니다. 처리 중 오류가 발생했습니다.",
                    "needs_retry": False,
                    "retry_keywords": []
                },
                "error": True
            }
    
    def _analyze_search_results_with_enhanced_citation(self, search_results: List[Dict], context: Dict, search_keywords: List[str], context_info: Dict) -> Dict:
        """Citation이 강화된 검색 결과 분석"""
        try:
            original_query = context.get("original_query", "")
            conversation_history = context.get("conversation_history", [])
            
            # Citation 정보 준비
            citations = []
            results_with_citations = []
            
            for i, result in enumerate(search_results):
                citation_id = i + 1
                citation_info = {
                    "id": citation_id,
                    "content": result.get('content', ''),
                    "source": result.get('source', '알 수 없는 출처'),
                    "score": result.get('score', 0)
                }
                citations.append(citation_info)
                
                # 검색 결과에 Citation ID 추가
                enhanced_result = result.copy()
                enhanced_result['citation_id'] = citation_id
                results_with_citations.append(enhanced_result)
            
            # 검색 결과 텍스트 구성 (Citation 포함)
            results_text = ""
            for citation in citations:
                content = citation['content'][:400]  # 400자로 제한
                results_text += f"[{citation['id']}] {content}...\n출처: {citation['source']}\n\n"
            
            # 이전 대화 맥락
            previous_context = ""
            if context_info.get("has_context", False) and conversation_history:
                recent_messages = conversation_history[-2:]
                for msg in recent_messages:
                    if msg.get("role") == "user":
                        previous_context += f"이전 질문: {msg.get('content', '')}\n"
                    elif msg.get("role") == "assistant":
                        previous_context += f"이전 답변: {msg.get('content', '')[:150]}...\n"
            
            # 현재 반복 횟수 확인 (previous_steps에서 Action 단계 수 계산)
            previous_steps = context.get("previous_steps", [])
            action_count = sum(1 for step in previous_steps if step.get("type") == "Action")
            current_iteration = action_count + 1
            
            # 검색 결과 품질 평가
            quality_assessment = self._assess_search_quality(search_results, original_query, search_keywords, current_iteration)
            
            # 최종 반복(5회차)이거나 품질이 충분한 경우 답변 생성
            if current_iteration >= 5 or not quality_assessment["needs_retry"]:
                # 검색 결과 텍스트 구성 (Citation 포함)
                results_text = ""
                for citation in citations:
                    content = citation['content'][:400]  # 400자로 제한
                    results_text += f"[{citation['id']}] {content}...\n출처: {citation['source']}\n\n"
                
                # 이전 대화 맥락
                previous_context = ""
                if context_info.get("has_context", False) and conversation_history:
                    recent_messages = conversation_history[-2:]
                    for msg in recent_messages:
                        if msg.get("role") == "user":
                            previous_context += f"이전 질문: {msg.get('content', '')}\n"
                        elif msg.get("role") == "assistant":
                            previous_context += f"이전 답변: {msg.get('content', '')[:150]}...\n"
                
                # Citation 강화 프롬프트 (최종 답변용)
                if current_iteration >= 5:
                    prompt = f"""이전 대화 맥락:
{previous_context}

현재 사용자 질문: {original_query}
분석된 의도: {context_info.get('intent', '')}

Knowledge Base 검색 결과 ({current_iteration}회 검색 후):
{results_text}

**중요 지침:**
이것은 {current_iteration}회차 검색 결과입니다. 검색 결과가 완벽하지 않더라도 가능한 한 도움이 되는 답변을 제공해주세요.

1. 검색 결과에서 관련성이 있는 부분을 최대한 활용하세요
2. 직접적인 정보가 없더라도 유사한 내용이나 일반적인 절차를 설명하세요
3. 검색 결과의 정보를 활용할 때는 반드시 [1], [2] 형태의 Citation을 포함하세요
4. 답변 마지막에 "**참고 자료:**" 섹션을 추가하여 모든 출처를 나열하세요
5. 정확한 정보를 찾지 못했다면 그 사실을 명시하고 대안을 제시하세요

답변:"""
                else:
                    prompt = f"""이전 대화 맥락:
{previous_context}

현재 사용자 질문: {original_query}
분석된 의도: {context_info.get('intent', '')}

Knowledge Base 검색 결과:
{results_text}

위의 검색 결과를 바탕으로 사용자의 질문에 대한 정확하고 상세한 답변을 생성해주세요.

**중요한 요구사항:**
1. 검색 결과의 정보를 활용할 때는 반드시 [1], [2] 형태의 Citation을 포함하세요
2. 답변 마지막에 "**참고 자료:**" 섹션을 추가하여 모든 출처를 나열하세요
3. 검색 결과에 없는 정보는 추측하지 마세요
4. 구체적이고 실용적인 답변을 제공하세요

답변:"""
                
                response = self.bedrock_client.invoke_model(
                    model_id=self.config.observation_model,
                    prompt=prompt,
                    temperature=self.config.temperature,
                    max_tokens=self.config.get_max_tokens_for_model(self.config.observation_model),
                    system_prompt=self._get_citation_system_prompt()
                )
                
                # Citation 정보가 포함되지 않은 경우 자동 추가
                enhanced_response = self._ensure_citations_in_response(response, citations)
                
                return {
                    "type": "Observation",
                    "model": self.config.observation_model,
                    "content": enhanced_response,
                    "parsed_result": {
                        "analysis": f"Citation 강화 검색 결과 {len(search_results)}개 분석 ({current_iteration}회차)",
                        "is_final_answer": True,
                        "final_answer": enhanced_response,
                        "needs_retry": False,
                        "retry_keywords": [],
                        "citations": citations,
                        "search_results_used": len(search_results),
                        "iteration_count": current_iteration
                    },
                    "search_results_count": len(search_results),
                    "context_applied": context_info.get("has_context", False),
                    "citations": citations,
                    "quality_score": quality_assessment["score"],
                    "error": False
                }
            
            # 재시도가 필요한 경우
            else:
                retry_keywords = self._generate_retry_keywords(original_query, search_keywords, quality_assessment["reason"])
                return {
                    "type": "Observation",
                    "model": self.config.observation_model,
                    "content": f"Search results insufficient. Retry needed with keywords: {retry_keywords}",
                    "parsed_result": {
                        "analysis": f"검색 결과 불충분 ({current_iteration}회차): {quality_assessment['reason']}",
                        "is_final_answer": False,
                        "final_answer": "",
                        "needs_retry": True,
                        "retry_keywords": retry_keywords,
                        "retry_reason": quality_assessment["reason"],
                        "iteration_count": current_iteration
                    },
                    "search_results_count": len(search_results),
                    "quality_score": quality_assessment["score"],
                    "error": False
                }
            prompt = f"""이전 대화 맥락:
{previous_context}

현재 사용자 질문: {original_query}
분석된 의도: {context_info.get('intent', '')}

Knowledge Base 검색 결과:
{results_text}

위의 검색 결과를 바탕으로 사용자의 질문에 대한 정확하고 상세한 답변을 생성해주세요.

**중요한 요구사항:**
1. 검색 결과의 정보를 활용할 때는 반드시 [1], [2] 형태의 Citation을 포함하세요
2. 답변 마지막에 "**참고 자료:**" 섹션을 추가하여 모든 출처를 나열하세요
3. 검색 결과에 없는 정보는 추측하지 마세요
4. 구체적이고 실용적인 답변을 제공하세요

답변 형식:
[검색 결과 기반 상세 답변 with Citations]

**참고 자료:**
[1] 출처 정보
[2] 출처 정보
...

답변:"""
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.get_max_tokens_for_model(self.config.observation_model),
                system_prompt=self._get_citation_system_prompt()
            )
            
            # Citation 정보가 포함되지 않은 경우 자동 추가
            enhanced_response = self._ensure_citations_in_response(response, citations)
            
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": enhanced_response,
                "parsed_result": {
                    "analysis": f"Citation 강화 검색 결과 {len(search_results)}개 분석",
                    "is_final_answer": True,
                    "final_answer": enhanced_response,
                    "needs_retry": False,
                    "retry_keywords": [],
                    "citations": citations,
                    "search_results_used": len(search_results)
                },
                "search_results_count": len(search_results),
                "context_applied": context_info.get("has_context", False),
                "citations": citations,
                "error": False
            }
            
        except Exception as e:
            return self._create_error_response(f"Citation 강화 검색 결과 분석 중 오류: {str(e)}")
    
    def _ensure_citations_in_response(self, response: str, citations: List[Dict]) -> str:
        """응답에 Citation이 포함되어 있는지 확인하고 없으면 추가"""
        # Citation 패턴 확인
        import re
        citation_pattern = r'\[\d+\]'
        has_citations = bool(re.search(citation_pattern, response))
        
        # 참고 자료 섹션 확인
        has_references = "참고 자료" in response or "References" in response or "출처" in response
        
        if not has_citations or not has_references:
            # Citation 자동 추가
            enhanced_response = response
            
            if not has_references:
                enhanced_response += "\n\n**참고 자료:**\n"
                for citation in citations:
                    enhanced_response += f"[{citation['id']}] {citation['source']}\n"
            
            return enhanced_response
        
        return response
    
    def _get_citation_system_prompt(self) -> str:
        """Citation 강화 시스템 프롬프트"""
        base_prompt = self.config.system_prompt or "당신은 도움이 되는 AI 어시스턴트입니다."
        
        return f"""{base_prompt}

당신은 Knowledge Base 검색 결과를 바탕으로 정확한 답변을 생성하는 전문가입니다.

**Citation 규칙:**
1. 검색 결과의 정보를 사용할 때는 반드시 [1], [2] 형태로 출처를 표시하세요
2. 답변 마지막에 "**참고 자료:**" 섹션을 포함하세요
3. 검색 결과에 없는 정보는 추측하지 마세요
4. 정확하고 구체적인 답변을 제공하세요"""
    
    def _extract_context_info(self, orchestration_result: Dict) -> Dict:
        """Orchestration 결과에서 맥락 정보 추출"""
        if not orchestration_result:
            return {"has_context": False}
        
        parsed_result = orchestration_result.get("parsed_result", {})
        
        return {
            "has_context": parsed_result.get("context_applied", False),
            "intent": parsed_result.get("intent", ""),
            "keywords": parsed_result.get("search_keywords", []),
            "confidence": parsed_result.get("confidence", 0)
        }
    
    def _handle_no_action_case_with_context(self, context: Dict, previous_steps: List, context_info: Dict) -> Dict:
        """맥락을 고려한 Action 없는 경우 처리"""
        try:
            original_query = context.get("original_query", "")
            conversation_history = context.get("conversation_history", [])
            
            # 간단한 인사말 처리
            if self._is_simple_greeting(original_query):
                answer = self._generate_greeting_response(original_query)
                return self._create_final_response(answer, "간단한 인사말로 직접 답변 생성")
            
            # 맥락 기반 답변 생성
            if context_info.get("has_context", False):
                return self._generate_context_aware_answer(original_query, conversation_history, context_info)
            else:
                return self._generate_general_answer(original_query)
            
        except Exception as e:
            return self._create_error_response(f"직접 답변 생성 중 오류: {str(e)}")
    
    def _generate_context_aware_answer(self, query: str, history: List[Dict], context_info: Dict) -> Dict:
        """맥락을 고려한 답변 생성 - 대화 연속성 강화"""
        try:
            # 이전 대화에서 맥락 추출 (더 많은 대화 포함)
            previous_context = ""
            if history:
                # 최근 6개 메시지까지 포함 (더 풍부한 맥락)
                recent_messages = history[-6:]
                for msg in recent_messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "user":
                        previous_context += f"사용자: {content}\n"
                    elif role == "assistant":
                        # 이전 답변을 더 길게 포함 (500자까지)
                        previous_context += f"어시스턴트: {content[:500]}...\n"
            
            # 연속성 질문 감지
            is_continuation = self._is_conversation_continuation_question(query)
            
            # 맥락 인식 프롬프트 (더 상세하게)
            if is_continuation:
                prompt = f"""이전 대화 맥락:
{previous_context}

현재 사용자 질문: {query}

위의 대화 맥락을 바탕으로 현재 질문에 대한 적절한 답변을 생성해주세요.

**중요 지침:**
1. 이전 대화의 내용을 정확히 기억하고 참조하세요
2. "다음은?", "그럼?", "또는?" 같은 연속성 질문의 경우, 이전 답변의 내용을 이어서 설명하세요
3. 이전 답변에서 언급했던 내용을 구체적으로 확장하거나 보완하세요
4. 자연스러운 대화 흐름을 유지하세요

답변:"""
            else:
                prompt = f"""이전 대화 맥락:
{previous_context}

현재 사용자 질문: {query}

분석된 의도: {context_info.get('intent', '')}

위의 대화 맥락을 고려하여 현재 질문에 대한 적절한 답변을 생성해주세요.
이전 대화와 관련이 있다면 그 연관성을 언급하면서 답변해주세요.

답변:"""
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=min(2000, self.config.get_max_tokens_for_model(self.config.observation_model)),  # 더 긴 답변 허용
                system_prompt=self._get_conversation_system_prompt()
            )
            
            return self._create_final_response(
                response.strip(), 
                f"대화 맥락을 고려한 답변 생성 (연속성: {is_continuation}, 의도: {context_info.get('intent', 'N/A')})"
            )
            
        except Exception as e:
            return self._create_error_response(f"맥락 인식 답변 생성 중 오류: {str(e)}")
    
    def _is_conversation_continuation_question(self, query: str) -> bool:
        """대화 연속성 질문인지 확인"""
        continuation_patterns = [
            "다음은", "그럼", "그러면", "또는", "아니면", "그리고", "그런데",
            "그래서", "그렇다면", "계속", "이어서", "추가로", "더", "또", "그 외에"
        ]
        
        query_lower = query.lower().strip()
        return any(pattern in query_lower for pattern in continuation_patterns)
    
    def _get_conversation_system_prompt(self) -> str:
        """대화 맥락 인식 시스템 프롬프트"""
        base_prompt = self.config.system_prompt or "당신은 도움이 되는 AI 어시스턴트입니다."
        
        return f"""{base_prompt}

당신은 대화의 맥락을 정확히 기억하고 연속성 있는 답변을 제공하는 전문가입니다.

**대화 연속성 규칙:**
1. 이전 대화의 내용을 정확히 기억하고 참조하세요
2. 연속성 질문("다음은?", "그럼?" 등)에는 이전 답변을 이어서 설명하세요
3. 이전 답변에서 언급한 내용을 구체적으로 확장하거나 보완하세요
4. 자연스러운 대화 흐름을 유지하세요
5. 이전 대화와의 연관성을 명확히 표현하세요"""
    
    def _generate_general_answer(self, query: str) -> Dict:
        """일반적인 답변 생성"""
        try:
            prompt = f"""사용자 질문: {query}

이 질문에 대해 도움이 되는 답변을 생성해주세요.

답변:"""
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=min(1000, self.config.get_max_tokens_for_model(self.config.observation_model)),
                system_prompt=self.config.system_prompt
            )
            
            return self._create_final_response(response.strip(), "일반적인 질문으로 직접 답변 생성")
            
        except Exception as e:
            return self._create_error_response(f"일반 답변 생성 중 오류: {str(e)}")
    
    def _handle_no_search_case_with_context(self, context: Dict, previous_steps: List, context_info: Dict) -> Dict:
        """맥락을 고려한 검색 없는 경우 처리"""
        return self._handle_no_action_case_with_context(context, previous_steps, context_info)
    
    def _handle_search_failure_with_context(self, action_result: Dict, context: Dict, search_keywords: List[str], context_info: Dict) -> Dict:
        """맥락을 고려한 검색 실패 처리"""
        try:
            original_query = context.get("original_query", "")
            
            # 검색 실패 시에도 일반적인 답변 제공
            prompt = f"""사용자 질문: {original_query}
검색 키워드: {search_keywords}

Knowledge Base에서 관련 정보를 찾을 수 없었습니다.
하지만 일반적인 지식을 바탕으로 도움이 될 수 있는 답변을 제공해주세요.

답변 시 다음 사항을 포함하세요:
1. 구체적인 정보를 찾을 수 없다는 안내
2. 일반적인 가이드라인이나 절차 안내
3. 추가 정보를 얻을 수 있는 방법 제안

답변:"""
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=min(1200, self.config.get_max_tokens_for_model(self.config.observation_model)),
                system_prompt=self.config.system_prompt
            )
            
            return self._create_final_response(
                response.strip(),
                "검색 실패 시 일반적인 가이드라인 제공"
            )
            
        except Exception as e:
            return self._create_error_response(f"검색 실패 처리 중 오류: {str(e)}")
    
    def _is_simple_greeting(self, query: str) -> bool:
        """간단한 인사말인지 확인"""
        greetings = [
            "안녕", "hello", "hi", "hey", "안녕하세요", "안녕하십니까",
            "좋은 아침", "좋은 오후", "좋은 저녁", "반갑습니다"
        ]
        
        query_lower = query.lower().strip()
        return any(greeting in query_lower for greeting in greetings)
    
    def _generate_greeting_response(self, query: str) -> str:
        """인사말에 대한 응답 생성"""
        responses = {
            "안녕": "안녕하세요! 무엇을 도와드릴까요?",
            "hello": "Hello! How can I help you?",
            "hi": "Hi there! What can I do for you?",
            "안녕하세요": "안녕하세요! 궁금한 것이 있으시면 언제든 말씀해 주세요.",
            "안녕하십니까": "안녕하십니까! 도움이 필요한 일이 있으시면 말씀해 주세요."
        }
        
        query_lower = query.lower().strip()
        
        for greeting, response in responses.items():
            if greeting in query_lower:
                return response
        
        return "안녕하세요! 무엇을 도와드릴까요?"
    
    def _assess_search_quality(self, search_results: List[Dict], query: str, keywords: List[str], iteration: int = 1) -> Dict:
        """검색 결과 품질 평가 - 반복 횟수에 따른 기준 조정"""
        if not search_results or len(search_results) == 0:
            return {
                "needs_retry": iteration < 5,  # 5회차에서는 재시도 안함
                "reason": "검색 결과 없음",
                "score": 0.0
            }
        
        # 반복 횟수에 따른 기준 완화
        if iteration <= 2:
            # 초기 반복: 엄격한 기준
            min_avg_score = 0.5
            min_max_score = 0.6
            min_content_length = 200
        elif iteration <= 4:
            # 중간 반복: 완화된 기준
            min_avg_score = 0.4
            min_max_score = 0.5
            min_content_length = 150
        else:
            # 최종 반복: 매우 완화된 기준 (거의 통과)
            min_avg_score = 0.2
            min_max_score = 0.3
            min_content_length = 50
        
        # 평균 점수 계산
        avg_score = sum(result.get('score', 0) for result in search_results) / len(search_results)
        max_score = max(result.get('score', 0) for result in search_results)
        total_content_length = sum(len(result.get('content', '')) for result in search_results)
        
        # 검색 결과가 1개뿐인 경우
        if len(search_results) == 1:
            score = search_results[0].get('score', 0)
            if score < min_max_score and iteration < 5:
                return {
                    "needs_retry": True,
                    "reason": f"검색 결과 1개, 관련성 낮음 (점수: {score:.3f}, {iteration}회차)",
                    "score": score
                }
        
        # 평균 점수가 낮은 경우
        if avg_score < min_avg_score and iteration < 5:
            return {
                "needs_retry": True,
                "reason": f"평균 관련성 점수 낮음 ({avg_score:.3f}, {iteration}회차)",
                "score": avg_score
            }
        
        # 최고 점수가 너무 낮은 경우
        if max_score < min_max_score and iteration < 5:
            return {
                "needs_retry": True,
                "reason": f"최고 관련성 점수 낮음 ({max_score:.3f}, {iteration}회차)",
                "score": max_score
            }
        
        # 검색 결과 내용이 너무 짧은 경우
        if total_content_length < min_content_length and iteration < 5:
            return {
                "needs_retry": True,
                "reason": f"검색 결과 내용 부족 ({total_content_length}자, {iteration}회차)",
                "score": avg_score
            }
        
        # 품질이 충분한 경우 또는 최종 반복인 경우
        return {
            "needs_retry": False,
            "reason": f"검색 결과 품질 {'양호' if iteration < 5 else '최종 반복'} (평균: {avg_score:.3f}, 최고: {max_score:.3f}, {iteration}회차)",
            "score": avg_score
        }
    
    def _generate_retry_keywords(self, query: str, previous_keywords: List[str], reason: str) -> List[str]:
        """재시도를 위한 대체 키워드 생성"""
        try:
            # 간단한 키워드 변형 로직
            import re
            
            # 원본 쿼리에서 핵심 단어 추출
            korean_words = re.findall(r'[가-힣]+', query)
            
            # 이전 키워드와 다른 새로운 키워드 생성
            new_keywords = []
            
            # 동의어/유사어 매핑
            synonym_map = {
                "규정": ["정책", "지침", "기준", "절차"],
                "지원": ["혜택", "보조", "도움", "제공"],
                "전결": ["승인", "결재", "허가", "인가"],
                "치료": ["의료", "진료", "처치", "케어"],
                "시술": ["수술", "처치", "의료행위", "진료"],
                "복리후생": ["직원혜택", "근로자혜택", "복지", "후생"],
                "회사": ["기업", "조직", "직장", "사업장"]
            }
            
            # 기존 키워드를 동의어로 변경
            for keyword in previous_keywords:
                for word, synonyms in synonym_map.items():
                    if word in keyword:
                        for synonym in synonyms:
                            new_keyword = keyword.replace(word, synonym)
                            if new_keyword not in new_keywords and new_keyword not in previous_keywords:
                                new_keywords.append(new_keyword)
                                break
                        break
            
            # 원본 쿼리의 핵심 단어 조합
            if len(korean_words) >= 2:
                for i in range(len(korean_words)-1):
                    combined = f"{korean_words[i]} {korean_words[i+1]}"
                    if combined not in new_keywords and combined not in previous_keywords:
                        new_keywords.append(combined)
            
            # 단일 핵심 단어들
            for word in korean_words:
                if len(word) >= 2 and word not in new_keywords and word not in str(previous_keywords):
                    new_keywords.append(word)
            
            # 최대 3개 반환
            return new_keywords[:3] if new_keywords else [query[:20]]
            
        except Exception as e:
            # 폴백: 원본 쿼리의 일부 사용
            return [query[:20]]
    
    def _create_final_response(self, answer: str, analysis: str) -> Dict:
        """최종 응답 생성"""
        return {
            "type": "Observation",
            "model": self.config.observation_model,
            "content": answer,
            "parsed_result": {
                "analysis": analysis,
                "is_final_answer": True,
                "final_answer": answer,
                "needs_retry": False,
                "retry_keywords": []
            },
            "error": False
        }
    
    def _create_error_response(self, error_msg: str) -> Dict:
        """에러 응답 생성"""
        return {
            "type": "Observation",
            "model": self.config.observation_model,
            "content": error_msg,
            "parsed_result": {
                "analysis": "에러 발생",
                "is_final_answer": True,
                "final_answer": "죄송합니다. 처리 중 오류가 발생했습니다.",
                "needs_retry": False,
                "retry_keywords": []
            },
            "error": True
        }
    
    def get_model_name(self) -> str:
        """현재 사용 중인 모델명 반환"""
        model_id = self.config.observation_model
        if "claude-sonnet-4" in model_id:
            return "Claude 4 (Citation-Enhanced)"
        elif "claude-3-7-sonnet" in model_id:
            return "Claude 3.7 Sonnet (Citation-Enhanced)"
        elif "claude-3-5-sonnet" in model_id:
            return "Claude 3.5 Sonnet (Citation-Enhanced)"
        elif "claude-3-5-haiku" in model_id:
            return "Claude 3.5 Haiku (Citation-Enhanced)"
        elif "nova-lite" in model_id:
            return "Nova Lite (Citation-Enhanced)"
        elif "nova-micro" in model_id:
            return "Nova Micro (Citation-Enhanced)"
        else:
            return f"{model_id.split(':')[0]} (Citation-Enhanced)"


# 기존 코드와의 호환성을 위한 별칭
ContextAwareObservationAgent = CitationEnhancedObservationAgent
ObservationAgent = CitationEnhancedObservationAgent  # react_agent.py 호환성을 위해 추가
