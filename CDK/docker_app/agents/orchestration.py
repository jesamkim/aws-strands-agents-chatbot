"""
Orchestration Agent 구현
사용자 쿼리 분석 및 실행 계획 수립을 담당
"""

import json
from typing import Dict, List, Any
from utils.config import AgentConfig
from utils.bedrock_client import BedrockClient


class OrchestrationAgent:
    """
    사용자 쿼리 분석 및 실행 계획 수립을 담당하는 Agent
    
    주요 역할:
    - 사용자 쿼리 의도 파악
    - Knowledge Base 검색 필요성 판단
    - 검색 키워드 생성
    - 실행 계획 수립
    """
    
    def __init__(self, config: AgentConfig):
        """
        Orchestration Agent 초기화
        
        Args:
            config: Agent 설정
        """
        self.config = config
        self.bedrock_client = BedrockClient()
    
    def orchestrate(self, context: Dict, previous_steps: List) -> Dict:
        """
        사용자 쿼리 분석 및 계획 수립
        
        Args:
            context: 실행 컨텍스트 (original_query, conversation_history 등)
            previous_steps: 이전 단계 결과 (재시도 시 사용)
            
        Returns:
            Orchestration 결과
        """
        try:
            # 프롬프트 구성
            prompt = self._build_orchestration_prompt(context, previous_steps)
            
            # 모델 호출
            response = self.bedrock_client.invoke_model(
                model_id=self.config.orchestration_model,
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.get_max_tokens_for_model(self.config.orchestration_model),
                system_prompt=self.config.system_prompt
            )
            
            # 응답 파싱
            parsed_result = self._parse_orchestration_response(response)
            
            return {
                "type": "Orchestration",
                "model": self.config.orchestration_model,
                "content": response,
                "parsed_result": parsed_result
            }
            
        except Exception as e:
            return {
                "type": "Orchestration",
                "model": self.config.orchestration_model,
                "content": f"Orchestration 오류: {str(e)}",
                "parsed_result": {
                    "intent": "오류 발생",
                    "needs_kb_search": False,
                    "search_keywords": [],
                    "execution_plan": "오류로 인해 계획 수립 실패",
                    "error": True
                }
            }
    
    def _build_orchestration_prompt(self, context: Dict, previous_steps: List) -> str:
        """Orchestration용 프롬프트 구성"""
        
        user_query = context.get("original_query", "")
        conversation_history = context.get("conversation_history", [])
        kb_enabled = self.config.is_kb_enabled()
        
        # 이전 시도 정보 (재시도인 경우)
        previous_attempts = ""
        if previous_steps:
            failed_keywords = []
            for step in previous_steps:
                if step.get("type") == "Action" and step.get("search_results") is not None:
                    if len(step.get("search_results", [])) == 0:
                        # 이전에 실패한 키워드들 수집
                        if "search_keywords" in step:
                            failed_keywords.extend(step.get("search_keywords", []))
            
            if failed_keywords:
                previous_attempts = f"\n\n이전 시도에서 다음 키워드들로 검색했지만 결과가 없었습니다: {failed_keywords}\n다른 키워드를 시도해주세요."
        
        # 대화 히스토리 요약 (개선된 버전)
        history_context = ""
        if conversation_history:
            history_context = "\n\n=== 이전 대화 맥락 ===\n"
            
            # 최근 대화를 역순으로 정리 (최신이 위로)
            recent_messages = conversation_history[-6:]  # 최근 6개 메시지 (3번의 대화)
            
            for i, msg in enumerate(recent_messages):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                # 역할에 따른 표시
                if role == "user":
                    history_context += f"사용자: {content}\n"
                elif role == "assistant":
                    # Assistant 응답은 너무 길 수 있으므로 요약
                    if len(content) > 150:
                        history_context += f"AI: {content[:150]}...\n"
                    else:
                        history_context += f"AI: {content}\n"
            
            history_context += "=== 현재 질문 ===\n"
        
        prompt = f"""당신은 사용자의 질문을 분석하고 실행 계획을 수립하는 Orchestration Agent입니다.

{history_context}
사용자 질문: {user_query}
{previous_attempts}

Knowledge Base 사용 가능: {'예' if kb_enabled else '아니오'}

**중요**: 위의 대화 맥락을 반드시 고려하여 사용자의 현재 질문을 이해하세요.
- 사용자가 "다음은?", "그럼?", "또는?" 같은 불완전한 질문을 했다면, 이전 대화의 맥락에서 무엇을 묻는지 파악하세요.
- 이전 대화에서 언급된 주제나 시퀀스가 있다면 그것을 고려하세요.
- 대화의 연속성을 유지하여 자연스러운 응답이 가능하도록 하세요.

다음 작업을 수행해주세요:

1. 이전 대화 맥락을 고려하여 사용자의 질문 의도를 파악하세요
2. Knowledge Base 검색이 필요한지 판단하세요
3. 검색이 필요하다면 효과적인 검색 키워드를 생성하세요
4. 실행 계획을 수립하세요

응답은 반드시 다음 JSON 형식으로 해주세요:

{{
    "intent": "사용자 질문의 의도 (이전 대화 맥락 포함하여 구체적으로)",
    "needs_kb_search": true 또는 false,
    "search_keywords": ["키워드1", "키워드2", "키워드3"],
    "execution_plan": "구체적인 실행 계획 설명",
    "confidence": 0.0~1.0 사이의 신뢰도 점수,
    "context_understanding": "이전 대화 맥락에 대한 이해 요약"
}}

검색 키워드 생성 가이드라인:
- 이전 대화에서 언급된 주제를 키워드에 포함하세요
- 핵심 개념과 관련 용어를 포함
- 너무 일반적이지 않고 구체적인 키워드 사용
- 동의어나 유사 표현도 고려
- 최대 5개까지 생성
- 한국어와 영어 키워드 모두 고려

Knowledge Base가 사용 불가능한 경우 needs_kb_search는 false로 설정하세요."""

        return prompt
    
    def _parse_orchestration_response(self, response: str) -> Dict:
        """Orchestration 응답 파싱"""
        try:
            # JSON 추출 시도
            response_clean = response.strip()
            
            # JSON 블록 찾기 (여러 패턴 시도)
            json_str = None
            
            # 패턴 1: ```json 블록
            if "```json" in response_clean:
                start = response_clean.find("```json") + 7
                end = response_clean.find("```", start)
                json_str = response_clean[start:end].strip()
            
            # 패턴 2: 단순 중괄호 블록
            elif "{" in response_clean and "}" in response_clean:
                start = response_clean.find("{")
                end = response_clean.rfind("}") + 1
                json_str = response_clean[start:end]
            
            # 패턴 3: 전체가 JSON인 경우
            else:
                json_str = response_clean
            
            if not json_str:
                raise ValueError("JSON 형식을 찾을 수 없습니다")
            
            # JSON 제어 문자 정리
            json_str = json_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            # 연속된 공백을 하나로 정리
            import re
            json_str = re.sub(r'\s+', ' ', json_str)
            
            # JSON 파싱 시도
            parsed = json.loads(json_str)
            
            # 필수 필드 검증 및 기본값 설정
            result = {
                "intent": parsed.get("intent", "알 수 없는 의도"),
                "needs_kb_search": bool(parsed.get("needs_kb_search", False)),
                "search_keywords": parsed.get("search_keywords", []),
                "execution_plan": parsed.get("execution_plan", "계획 없음"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "error": False
            }
            
            # KB가 비활성화된 경우 강제로 검색 비활성화
            if not self.config.is_kb_enabled():
                result["needs_kb_search"] = False
                result["search_keywords"] = []
            
            # 검색 키워드 정리 (빈 문자열 제거, 최대 5개)
            if result["search_keywords"]:
                result["search_keywords"] = [
                    kw.strip() for kw in result["search_keywords"] 
                    if kw and kw.strip()
                ][:5]
            
            return result
            
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            # JSON 파싱 실패 시 폴백 로직
            print(f"JSON 파싱 실패: {str(e)}")
            print(f"원본 응답: {response[:200]}...")
            return self._fallback_parsing(response)
    
    def _fallback_parsing(self, response: str) -> Dict:
        """JSON 파싱 실패 시 폴백 로직"""
        
        # 기본 응답 구조
        result = {
            "intent": "파싱 실패",
            "needs_kb_search": self.config.is_kb_enabled(),
            "search_keywords": [],
            "execution_plan": "응답 파싱에 실패했지만 기본 검색을 시도합니다",
            "confidence": 0.3,
            "error": True
        }
        
        # 응답에서 키워드 추출 시도
        if self.config.is_kb_enabled():
            # 간단한 키워드 추출 로직
            response_lower = response.lower()
            
            # 일반적인 키워드 패턴 찾기
            common_patterns = [
                "절차", "방법", "과정", "규정", "정책", "지침",
                "투자", "계약", "승인", "품의", "결재",
                "회사", "조직", "부서"
            ]
            
            found_keywords = []
            for pattern in common_patterns:
                if pattern in response or pattern in response_lower:
                    found_keywords.append(pattern)
            
            result["search_keywords"] = found_keywords[:3]  # 최대 3개
        
        return result
    
    def get_model_name(self) -> str:
        """현재 사용 중인 모델명 반환"""
        model_id = self.config.orchestration_model
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
