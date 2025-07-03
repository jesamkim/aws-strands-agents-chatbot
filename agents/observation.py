"""
Observation Agent 구현
결과 분석 및 다음 단계 결정을 담당
"""

import json
from typing import Dict, List, Any
from utils.config import AgentConfig
from utils.bedrock_client import BedrockClient


class ObservationAgent:
    """
    결과 분석 및 다음 단계 결정을 담당하는 Agent
    
    주요 역할:
    - Action 결과 분석
    - 목표 달성 여부 평가
    - 추가 행동 필요성 판단
    - 최종 답변 생성 또는 다음 단계 계획
    """
    
    def __init__(self, config: AgentConfig):
        """
        Observation Agent 초기화
        
        Args:
            config: Agent 설정
        """
        self.config = config
        self.bedrock_client = BedrockClient()
    
    def observe(self, action_result: Dict, context: Dict) -> Dict:
        """
        결과 분석 및 다음 단계 결정
        
        Args:
            action_result: Action 단계 결과
            context: 실행 컨텍스트
            
        Returns:
            Observation 결과
        """
        # 현재 컨텍스트를 저장하여 다른 메서드에서 사용할 수 있도록 함
        self._current_context = context
        
        try:
            # Action 결과 분석
            search_results = action_result.get("search_results", [])
            action_error = action_result.get("error", False)
            search_keywords = action_result.get("search_keywords", [])
            
            # 검색 결과가 있는 경우
            if search_results and not action_error:
                return self._analyze_search_results(search_results, context, search_keywords)
            
            # 검색 결과가 없지만 오류가 아닌 경우 (KB 검색 불필요)
            elif not search_results and not action_error:
                return self._handle_no_search_case(action_result, context)
            
            # 검색 실패 또는 오류인 경우
            else:
                return self._handle_search_failure(action_result, context, search_keywords)
                
        except Exception as e:
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": f"Observation 수행 중 오류 발생: {str(e)}",
                "parsed_result": {
                    "analysis": "오류 발생",
                    "can_answer": False,
                    "needs_retry": False,
                    "retry_keywords": [],
                    "final_answer": None,
                    "should_stop": True
                },
                "error": True
            }
        finally:
            # 컨텍스트 정리
            if hasattr(self, '_current_context'):
                delattr(self, '_current_context')
    
    def _analyze_search_results(self, search_results: List[Dict], context: Dict, search_keywords: List[str]) -> Dict:
        """검색 결과가 있는 경우의 분석"""
        try:
            # 검색 결과를 바탕으로 답변 생성
            prompt = self._build_analysis_prompt(search_results, context, search_keywords)
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.get_max_tokens_for_model(self.config.observation_model),
                system_prompt=self.config.system_prompt
            )
            
            # 응답 파싱
            parsed_result = self._parse_observation_response(response)
            
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": response,
                "parsed_result": parsed_result,
                "search_results_count": len(search_results),
                "error": False
            }
            
        except Exception as e:
            # 파싱 실패 시 기본 답변 생성
            return self._generate_fallback_answer(search_results, context, str(e))
    
    def _handle_no_search_case(self, action_result: Dict, context: Dict) -> Dict:
        """KB 검색이 필요하지 않은 경우의 처리"""
        try:
            original_query = context.get("original_query", "")
            action_content = action_result.get("content", "")
            
            # 직접 답변 생성
            prompt = self._build_direct_response_prompt(original_query, action_content)
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.get_max_tokens_for_model(self.config.observation_model),
                system_prompt=self.config.system_prompt
            )
            
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": response,
                "parsed_result": {
                    "analysis": "Knowledge Base 검색이 필요하지 않은 질문으로 직접 답변 생성",
                    "can_answer": True,
                    "needs_retry": False,
                    "retry_keywords": [],
                    "final_answer": response.strip(),
                    "should_stop": True
                },
                "error": False
            }
            
        except Exception as e:
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": f"직접 답변 생성 중 오류: {str(e)}",
                "parsed_result": {
                    "analysis": "직접 답변 생성 실패",
                    "can_answer": False,
                    "needs_retry": False,
                    "retry_keywords": [],
                    "final_answer": "죄송합니다. 답변을 생성할 수 없습니다.",
                    "should_stop": True
                },
                "error": True
            }
    
    def _handle_search_failure(self, action_result: Dict, context: Dict, search_keywords: List[str]) -> Dict:
        """검색 실패 시 재시도 여부 결정"""
        try:
            original_query = context.get("original_query", "")
            action_content = action_result.get("content", "")
            
            # 재시도 여부 판단
            prompt = self._build_retry_decision_prompt(original_query, action_content, search_keywords)
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.observation_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.get_max_tokens_for_model(self.config.observation_model),
                system_prompt=self.config.system_prompt
            )
            
            parsed_result = self._parse_retry_decision(response)
            
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": response,
                "parsed_result": parsed_result,
                "error": False
            }
            
        except Exception as e:
            # 재시도 없이 종료
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": f"재시도 판단 중 오류: {str(e)}",
                "parsed_result": {
                    "analysis": "검색 실패 및 재시도 판단 실패",
                    "can_answer": False,
                    "needs_retry": False,
                    "retry_keywords": [],
                    "final_answer": "죄송합니다. 관련 정보를 찾을 수 없습니다.",
                    "should_stop": True
                },
                "error": True
            }
    
    def _build_analysis_prompt(self, search_results: List[Dict], context: Dict, search_keywords: List[str]) -> str:
        """검색 결과 분석용 프롬프트 구성"""
        original_query = context.get("original_query", "")
        conversation_history = context.get("conversation_history", [])
        
        # 검색 결과 컨텍스트 구성 (citation 포함)
        search_context = ""
        for i, result in enumerate(search_results, 1):
            content = result.get("content", "")[:400]  # 400자로 확대
            score = result.get("score", 0)
            keyword = result.get("query", "")
            citation_id = result.get("citation_id", i)
            
            search_context += f"\n검색 결과 [{citation_id}] (점수: {score:.3f}, 키워드: {keyword}):\n{content}\n"
        
        # 대화 히스토리 컨텍스트 구성
        history_context = ""
        if conversation_history:
            history_context = "\n\n=== 이전 대화 맥락 ===\n"
            recent_messages = conversation_history[-4:]  # 최근 4개 메시지
            
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                if role == "user":
                    history_context += f"사용자: {content}\n"
                elif role == "assistant":
                    # Assistant 응답은 요약해서 표시
                    if len(content) > 100:
                        history_context += f"AI: {content[:100]}...\n"
                    else:
                        history_context += f"AI: {content}\n"
        
        # 시스템 프롬프트에서 특별한 형식 요구사항 추출
        system_prompt = self.config.system_prompt
        has_table_requirement = '|' in system_prompt and ('표' in system_prompt or 'table' in system_prompt.lower())
        has_emoji_requirement = ':' in system_prompt and ('clipboard' in system_prompt or 'book' in system_prompt)
        
        prompt = f"""당신은 검색 결과를 분석하고 사용자 질문에 대한 최종 답변을 생성하는 Observation Agent입니다.

{history_context}

현재 사용자 질문: {original_query}

검색 키워드: {search_keywords}

검색 결과:
{search_context}

**시스템 프롬프트 요구사항**: 
{system_prompt}

**중요 지침**:
1. 위의 시스템 프롬프트에서 요구하는 형식을 반드시 준수하세요
2. 검색 결과가 있고 관련성이 있다면 답변 가능으로 판단하세요
3. 시스템 프롬프트에서 요구하는 구조와 형식을 정확히 따르세요
4. 이전 대화 맥락을 고려하여 자연스러운 답변을 생성하세요
5. **답변에 검색 결과를 인용할 때는 반드시 [1], [2] 형태의 citation을 사용하세요**
6. **각 검색 결과는 고유한 citation 번호를 가지고 있으니 정확히 참조하세요**

다음 작업을 수행해주세요:

1. 이전 대화 맥락과 현재 질문을 종합하여 사용자가 실제로 무엇을 묻는지 파악하세요
2. 검색 결과가 사용자 질문에 답하기에 충분한지 분석하세요
3. 충분하다면 시스템 프롬프트의 형식을 정확히 따라 답변을 생성하세요
4. 부족하다면 추가 검색이 필요한지, 다른 키워드가 필요한지 판단하세요

응답은 반드시 다음 JSON 형식으로 해주세요:

{{
    "analysis": "검색 결과에 대한 분석 (대화 맥락 포함)",
    "can_answer": true 또는 false,
    "needs_retry": true 또는 false,
    "retry_keywords": ["새로운키워드1", "새로운키워드2"] (재시도가 필요한 경우만),
    "final_answer": "사용자에게 제공할 최종 답변 (can_answer가 true인 경우, 시스템 프롬프트 형식 준수)",
    "should_stop": true 또는 false,
    "confidence": 0.0~1.0 사이의 신뢰도 점수,
    "context_continuity": "이전 대화와의 연결성 설명",
    "format_compliance": "시스템 프롬프트 형식 준수 여부"
}}

**답변 생성 가이드라인**:
- 검색 결과가 있고 관련성이 0.3 이상이면 답변 가능으로 판단하세요
- 시스템 프롬프트에서 요구하는 모든 형식 요소를 포함하세요
- 표 형식이 요구되면 마크다운 테이블을 사용하세요
- 이모지나 특수 기호가 요구되면 정확히 포함하세요
- 검색 결과의 정보를 정확히 반영하세요
- **검색 결과를 인용할 때는 반드시 [1], [2] 등의 citation을 문장 끝에 추가하세요**
- **예시: "전결규정에 따르면 사장 승인이 필요합니다 [1]. 추가로 검토부서 협의도 필요합니다 [2]."**
- 불확실한 정보는 명시하세요"""

        return prompt
    
    def _build_direct_response_prompt(self, original_query: str, action_content: str) -> str:
        """직접 답변 생성용 프롬프트"""
        # 컨텍스트에서 대화 히스토리 가져오기
        conversation_history = getattr(self, '_current_context', {}).get('conversation_history', [])
        
        # 대화 히스토리 컨텍스트 구성
        history_context = ""
        if conversation_history:
            history_context = "\n\n=== 이전 대화 맥락 ===\n"
            recent_messages = conversation_history[-4:]  # 최근 4개 메시지
            
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                if role == "user":
                    history_context += f"사용자: {content}\n"
                elif role == "assistant":
                    # Assistant 응답은 요약해서 표시
                    if len(content) > 100:
                        history_context += f"AI: {content[:100]}...\n"
                    else:
                        history_context += f"AI: {content}\n"
            
            history_context += "\n=== 현재 질문 ===\n"
        
        prompt = f"""{history_context}사용자 질문: {original_query}

상황: {action_content}

**중요**: 위의 대화 맥락을 반드시 고려하여 답변하세요.
- 사용자가 "다음은?", "그럼?", "또는?" 같은 질문을 했다면, 이전 대화에서 언급된 시퀀스나 목록의 다음 항목을 답변하세요.
- 이전 대화의 주제와 자연스럽게 연결하여 답변하세요.
- 대화의 연속성을 유지하세요.

위 질문에 대해 직접 답변해주세요. Knowledge Base 검색이 필요하지 않은 질문입니다.

답변 가이드라인:
- 이전 대화의 맥락을 고려하여 자연스럽게 이어가세요
- 친절하고 도움이 되는 답변을 제공하세요
- 질문의 성격에 맞는 적절한 답변을 하세요
- 필요시 추가 도움을 제공할 수 있음을 안내하세요"""

        return prompt
    
    def _build_retry_decision_prompt(self, original_query: str, action_content: str, search_keywords: List[str]) -> str:
        """재시도 결정용 프롬프트"""
        prompt = f"""사용자 질문: {original_query}

검색 상황: {action_content}

사용된 검색 키워드: {search_keywords}

검색 결과가 없거나 오류가 발생했습니다. 다른 키워드로 재시도할지 결정해주세요.

응답은 다음 JSON 형식으로 해주세요:

{{
    "analysis": "현재 상황 분석",
    "can_answer": false,
    "needs_retry": true 또는 false,
    "retry_keywords": ["대체키워드1", "대체키워드2"] (재시도하는 경우),
    "final_answer": "재시도하지 않는 경우의 답변",
    "should_stop": true 또는 false
}}

재시도 판단 기준:
- 사용자 질문이 포스코 관련 구체적 정보를 요구하는가?
- 다른 키워드로 검색하면 결과를 찾을 가능성이 있는가?
- 이미 여러 번 시도했는가?"""

        return prompt
    
    def _parse_observation_response(self, response: str) -> Dict:
        """Observation 응답 파싱"""
        try:
            # JSON 추출 및 파싱
            response_clean = response.strip()
            
            # JSON 블록 찾기
            json_str = None
            if "```json" in response_clean:
                start = response_clean.find("```json") + 7
                end = response_clean.find("```", start)
                json_str = response_clean[start:end].strip()
            elif "{" in response_clean and "}" in response_clean:
                start = response_clean.find("{")
                end = response_clean.rfind("}") + 1
                json_str = response_clean[start:end]
            else:
                json_str = response_clean
            
            # JSON 제어 문자 정리
            json_str = json_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            import re
            json_str = re.sub(r'\s+', ' ', json_str)
            
            parsed = json.loads(json_str)
            
            # 필수 필드 검증 및 기본값 설정
            result = {
                "analysis": parsed.get("analysis", "분석 정보 없음"),
                "can_answer": bool(parsed.get("can_answer", False)),
                "needs_retry": bool(parsed.get("needs_retry", False)),
                "retry_keywords": parsed.get("retry_keywords", []),
                "final_answer": parsed.get("final_answer"),
                "should_stop": bool(parsed.get("should_stop", True)),
                "confidence": float(parsed.get("confidence", 0.5))
            }
            
            # 재시도 키워드 정리
            if result["retry_keywords"]:
                result["retry_keywords"] = [
                    kw.strip() for kw in result["retry_keywords"] 
                    if kw and kw.strip()
                ][:5]
            
            return result
            
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            # 파싱 실패 시 응답에서 직접 답변 추출 시도
            return self._extract_direct_answer(response)
    
    def _parse_retry_decision(self, response: str) -> Dict:
        """재시도 결정 응답 파싱"""
        try:
            return self._parse_observation_response(response)
        except Exception:
            # 기본적으로 재시도하지 않음
            return {
                "analysis": "재시도 결정 파싱 실패",
                "can_answer": False,
                "needs_retry": False,
                "retry_keywords": [],
                "final_answer": "죄송합니다. 관련 정보를 찾을 수 없습니다.",
                "should_stop": True,
                "confidence": 0.1
            }
    
    def _extract_direct_answer(self, response: str) -> Dict:
        """JSON 파싱 실패 시 직접 답변 추출"""
        # 응답에서 의미있는 답변 부분 추출
        answer = response.strip()
        
        # 간단한 휴리스틱으로 답변 품질 판단
        has_meaningful_content = len(answer) > 20 and any(
            keyword in answer.lower() for keyword in 
            ['포스코', '절차', '방법', '규정', '승인', '투자', '안전', '보건']
        )
        
        return {
            "analysis": "JSON 파싱 실패로 직접 답변 추출",
            "can_answer": has_meaningful_content,
            "needs_retry": not has_meaningful_content,
            "retry_keywords": [],
            "final_answer": answer if has_meaningful_content else None,
            "should_stop": True,
            "confidence": 0.3 if has_meaningful_content else 0.1
        }
    
    def _generate_fallback_answer(self, search_results: List[Dict], context: Dict, error_msg: str) -> Dict:
        """파싱 실패 시 폴백 답변 생성"""
        # 검색 결과가 있다면 간단한 요약 생성
        if search_results:
            summary_parts = []
            for result in search_results[:3]:
                content = result.get("content", "")[:150]
                summary_parts.append(content)
            
            fallback_answer = f"검색된 정보를 바탕으로 다음과 같은 내용을 찾았습니다:\n\n"
            fallback_answer += "\n\n".join([f"• {part}..." for part in summary_parts])
            fallback_answer += "\n\n더 자세한 정보가 필요하시면 구체적으로 문의해 주세요."
            
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": f"응답 파싱 실패 (오류: {error_msg}), 폴백 답변 생성",
                "parsed_result": {
                    "analysis": "응답 파싱 실패로 폴백 답변 생성",
                    "can_answer": True,
                    "needs_retry": False,
                    "retry_keywords": [],
                    "final_answer": fallback_answer,
                    "should_stop": True,
                    "confidence": 0.4
                },
                "error": False
            }
        else:
            return {
                "type": "Observation",
                "model": self.config.observation_model,
                "content": f"응답 파싱 실패 및 검색 결과 없음 (오류: {error_msg})",
                "parsed_result": {
                    "analysis": "응답 파싱 실패 및 검색 결과 없음",
                    "can_answer": False,
                    "needs_retry": True,
                    "retry_keywords": ["일반적인", "기본", "표준"],
                    "final_answer": None,
                    "should_stop": False,
                    "confidence": 0.1
                },
                "error": True
            }
    
    def get_model_name(self) -> str:
        """현재 사용 중인 모델명 반환"""
        model_id = self.config.observation_model
        if "claude-sonnet-4" in model_id:
            return "Claude 4"
        elif "claude-3-7-sonnet" in model_id:
            return "Claude 3.7 Sonnet"
        elif "claude-3-5-sonnet" in model_id:
            return "Claude 3.5 Sonnet"
        elif "claude-3-5-haiku" in model_id:
            return "Claude 3.5 Haiku"
        elif "nova-lite" in model_id:
            return "Nova Lite"
        elif "nova-micro" in model_id:
            return "Nova Micro"
        else:
            return model_id.split(':')[0]
