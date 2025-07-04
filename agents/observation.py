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
            
            # 현재 반복 횟수 확인 (previous_steps에서 Action 단계 수 계산)
            previous_steps = context.get("previous_steps", [])
            action_count = sum(1 for step in previous_steps if step.get("type") == "Action")
            current_iteration = action_count
            
            print(f"   📊 현재 반복: {current_iteration}회차, 검색 결과: {len(search_results)}개")
            
            # 검색 결과 품질 평가
            quality_assessment = self._assess_search_quality(search_results, original_query, search_keywords, current_iteration)
            
            print(f"   🎯 품질 평가: {quality_assessment['reason']} (점수: {quality_assessment['score']:.3f})")
            
            # 재시도가 필요한 경우 (5회차가 아니고 품질이 불충분한 경우)
            if current_iteration < 5 and quality_assessment["needs_retry"]:
                retry_keywords = self._generate_retry_keywords(original_query, search_keywords, quality_assessment["reason"])
                print(f"   🔄 재시도 키워드: {retry_keywords}")
                
                return {
                    "type": "Observation",
                    "model": self.config.observation_model,
                    "content": f"검색 결과 불충분. 재시도 필요: {retry_keywords}",
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
            
            # 최종 답변 생성 (5회차이거나 품질이 충분한 경우)
            print(f"   ✅ 최종 답변 생성 (반복: {current_iteration}, 품질 충족: {not quality_assessment['needs_retry']})")
            
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
        """LLM 기반 검색 결과 품질 평가"""
        if not search_results or len(search_results) == 0:
            return {
                "needs_retry": iteration < 5,
                "reason": "검색 결과 없음",
                "score": 0.0
            }
        
        try:
            # 검색 결과 요약 생성
            results_summary = ""
            for i, result in enumerate(search_results, 1):
                content = result.get('content', '')[:200]  # 200자로 제한
                score = result.get('score', 0)
                results_summary += f"결과 {i} (관련성: {score:.3f}): {content}...\n"
            
            # LLM을 통한 품질 평가
            evaluation_prompt = f"""사용자 질문: {query}
검색 키워드: {keywords}
현재 반복 횟수: {iteration}/5

검색 결과:
{results_summary}

위의 검색 결과가 사용자 질문에 대한 답변을 제공하기에 충분한지 평가해주세요.

평가 기준:
1. 질문과의 관련성 (검색 결과가 질문의 핵심 내용을 다루고 있는가?)
2. 정보의 구체성 (구체적인 절차, 규정, 기준 등이 포함되어 있는가?)
3. 답변 완성도 (이 정보만으로 사용자에게 도움이 되는 답변을 만들 수 있는가?)

반복 횟수별 기준:
- 1-2회차: 엄격한 기준 (높은 관련성과 구체적 정보 필요)
- 3-4회차: 완화된 기준 (부분적 정보라도 유용하면 통과)
- 5회차: 매우 완화된 기준 (최소한의 관련 정보만 있어도 통과)

다음 형식으로 답변해주세요:
QUALITY_SCORE: [0.0-1.0 사이의 점수]
SUFFICIENT: [YES/NO]
REASON: [평가 이유를 한 문장으로]"""

            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=evaluation_prompt,
                temperature=0.1,  # 일관된 평가를 위해 낮은 temperature
                max_tokens=200,
                system_prompt="당신은 검색 결과의 품질을 객관적으로 평가하는 전문가입니다."
            )
            
            # 응답 파싱
            lines = response.strip().split('\n')
            quality_score = 0.0
            is_sufficient = False
            reason = "평가 실패"
            
            for line in lines:
                if line.startswith('QUALITY_SCORE:'):
                    try:
                        quality_score = float(line.split(':')[1].strip())
                    except:
                        quality_score = 0.0
                elif line.startswith('SUFFICIENT:'):
                    is_sufficient = 'YES' in line.upper()
                elif line.startswith('REASON:'):
                    reason = line.split(':', 1)[1].strip()
            
            # 최종 반복(5회차)에서는 항상 충분하다고 판단
            if iteration >= 5:
                is_sufficient = True
                reason += " (최종 반복)"
            
            needs_retry = not is_sufficient and iteration < 5
            
            print(f"   🤖 LLM 품질 평가: 점수={quality_score:.3f}, 충분={is_sufficient}, 재시도={needs_retry}")
            
            return {
                "needs_retry": needs_retry,
                "reason": reason,
                "score": quality_score
            }
            
        except Exception as e:
            print(f"   ⚠️ LLM 품질 평가 오류: {str(e)}")
            # 폴백: 간단한 점수 기반 평가
            avg_score = sum(result.get('score', 0) for result in search_results) / len(search_results)
            
            # 반복 횟수에 따른 기본 임계값
            threshold = 0.5 if iteration <= 2 else (0.4 if iteration <= 4 else 0.2)
            
            return {
                "needs_retry": avg_score < threshold and iteration < 5,
                "reason": f"폴백 평가: 평균 점수 {avg_score:.3f} (임계값: {threshold})",
                "score": avg_score
            }
    
    def _generate_retry_keywords(self, query: str, previous_keywords: List[str], reason: str) -> List[str]:
        """LLM 기반 재시도 키워드 생성"""
        try:
            keyword_generation_prompt = f"""사용자 질문: {query}
이전 검색 키워드: {previous_keywords}
검색 실패 이유: {reason}

위의 정보를 바탕으로 더 나은 검색 결과를 얻을 수 있는 새로운 키워드들을 생성해주세요.

키워드 생성 전략:
1. 동의어/유사어 사용 (예: "규정" → "정책", "지침", "기준")
2. 더 구체적인 용어 사용 (예: "지원" → "지원금", "지원제도")
3. 더 일반적인 용어 사용 (너무 구체적이었다면)
4. 관련 분야의 전문 용어 활용
5. 다른 표현 방식 시도

이전 키워드와는 다른 새로운 키워드 3-4개를 생성해주세요.

형식:
KEYWORD1: [키워드1]
KEYWORD2: [키워드2]
KEYWORD3: [키워드3]
KEYWORD4: [키워드4] (선택사항)"""

            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=keyword_generation_prompt,
                temperature=0.7,  # 창의적인 키워드 생성을 위해 높은 temperature
                max_tokens=300,
                system_prompt="당신은 검색 키워드 최적화 전문가입니다. 다양한 관점에서 효과적인 검색 키워드를 생성할 수 있습니다."
            )
            
            # 키워드 추출
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
            
            # 키워드가 생성되지 않은 경우 폴백
            if not new_keywords:
                print("   ⚠️ LLM 키워드 생성 실패, 폴백 사용")
                return self._fallback_keyword_generation(query, previous_keywords)
            
            print(f"   🤖 LLM 생성 키워드: {new_keywords}")
            return new_keywords[:4]  # 최대 4개
            
        except Exception as e:
            print(f"   ⚠️ LLM 키워드 생성 오류: {str(e)}")
            return self._fallback_keyword_generation(query, previous_keywords)
    
    def _fallback_keyword_generation(self, query: str, previous_keywords: List[str]) -> List[str]:
        """폴백 키워드 생성 (LLM 실패 시)"""
        import re
        
        # 원본 쿼리에서 핵심 단어 추출
        korean_words = re.findall(r'[가-힣]+', query)
        new_keywords = []
        
        # 단어 조합 생성
        if len(korean_words) >= 2:
            for i in range(len(korean_words)-1):
                combined = f"{korean_words[i]} {korean_words[i+1]}"
                if combined not in str(previous_keywords):
                    new_keywords.append(combined)
        
        # 개별 단어 추가
        for word in korean_words:
            if len(word) >= 2 and word not in str(previous_keywords):
                new_keywords.append(word)
        
        # 원본 쿼리 일부 사용
        if not new_keywords:
            new_keywords = [query[:15], query[-15:]]
        
        return new_keywords[:3]
    
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
