"""
KB Priority-based Ultra-fast Orchestration Agent
Maximum speed optimization with KB-first approach
"""

import json
from typing import Dict, List, Any
from utils.config import AgentConfig
from utils.bedrock_client import BedrockClient


class OptimizedOrchestrationAgent:
    """
    KB Priority-based Ultra-fast Orchestration Agent
    
    Key optimizations:
    - KB_ID exists → KB search priority
    - KB_ID missing → Direct model answer
    - Ultra-minimal English prompts
    - Korean output maintained
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.bedrock_client = BedrockClient()
    
    def orchestrate(self, context: Dict) -> Dict:
        """Ultra-fast KB-priority orchestration with conversation continuity"""
        try:
            original_query = context.get("original_query", "")
            kb_id = context.get("kb_id", "")
            kb_description = context.get("kb_description", "")
            conversation_history = context.get("conversation_history", [])
            
            # 1. 대화 연속성 질문 우선 처리 (KB_ID 존재 여부와 무관)
            if self._is_conversation_continuation(original_query, conversation_history):
                return self._create_direct_answer_result(original_query, "Conversation continuation")
            
            # 2. 단순한 인사말 처리
            if self._is_simple_greeting(original_query):
                return self._create_direct_answer_result(original_query, "Simple greeting")
            
            # 3. KB_ID 존재 여부에 따른 우선순위 결정
            if not kb_id:
                # KB_ID 없음 → 직접 답변 (대화 맥락 고려)
                return self._create_direct_answer_result(original_query, "No KB_ID - direct answer with context")
            
            # 4. KB_ID 있음 → KB 검색 우선
            # 재시도 키워드가 있는지 확인
            retry_keywords = context.get("retry_keywords", [])
            if retry_keywords:
                print(f"   🔄 재시도 키워드 사용: {retry_keywords}")
                return {
                    "type": "Orchestration",
                    "model": self.config.orchestration_model,
                    "content": f"KB retry search with keywords: {retry_keywords}",
                    "parsed_result": {
                        "needs_kb_search": True,
                        "search_keywords": retry_keywords,
                        "intent": "KB retry search",
                        "confidence": 0.9,
                        "rule_applied": "kb_retry",
                        "reasoning": f"Retry with different keywords: {context.get('retry_reason', 'Previous search insufficient')}",
                        "context_applied": len(conversation_history) > 0
                    },
                    "error": False
                }
            
            # KB 검색 키워드 생성 (초고속)
            keywords = self._generate_keywords_fast(original_query, kb_description, conversation_history)
            
            return {
                "type": "Orchestration",
                "model": self.config.orchestration_model,
                "content": f"KB search with keywords: {keywords}",
                "parsed_result": {
                    "needs_kb_search": True,
                    "search_keywords": keywords,
                    "intent": "KB search priority",
                    "confidence": 0.95,
                    "rule_applied": "kb_priority",
                    "reasoning": "KB_ID exists - KB search priority",
                    "context_applied": len(conversation_history) > 0
                },
                "error": False
            }
            
        except Exception as e:
            return self._create_error_result(str(e))
    
    def _generate_keywords_fast(self, query: str, kb_description: str, history: List[Dict]) -> List[str]:
        """Ultra-fast keyword generation with minimal prompt"""
        try:
            # 이전 대화 맥락 확인
            context_info = ""
            if history and len(history) > 0:
                last_user_msg = ""
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")[:100]
                        break
                if last_user_msg:
                    context_info = f"Previous: {last_user_msg}"
            
            # KB 설명 정보
            kb_info = f"KB: {kb_description[:100]}" if kb_description else "KB: General knowledge base"
            
            # 초간단 영어 프롬프트 (토큰 최소화)
            prompt = f"""Query: {query}
{kb_info}
{context_info}

Generate 3 Korean search keywords for KB search.
Output format: ["keyword1", "keyword2", "keyword3"]"""
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.orchestration_model,
                prompt=prompt,
                temperature=0.0,  # 일관성 최대화
                max_tokens=100,   # 최소 토큰
                system_prompt="You are a keyword extraction expert. Generate precise Korean search keywords in JSON array format."
            )
            
            # JSON 파싱 시도
            try:
                import re
                # JSON 배열 패턴 찾기
                json_match = re.search(r'\[.*?\]', response)
                if json_match:
                    keywords_json = json_match.group()
                    keywords = json.loads(keywords_json)
                    if isinstance(keywords, list) and len(keywords) > 0:
                        return keywords[:3]  # 최대 3개
            except:
                pass
            
            # JSON 파싱 실패 시 폴백
            return self._extract_keywords_fallback(query)
            
        except Exception as e:
            return self._extract_keywords_fallback(query)
    
    def _extract_keywords_fallback(self, query: str) -> List[str]:
        """키워드 추출 폴백 로직"""
        # 간단한 키워드 추출
        import re
        
        # 한글 단어 추출
        korean_words = re.findall(r'[가-힣]+', query)
        
        # 영어 단어 추출
        english_words = re.findall(r'[a-zA-Z]+', query)
        
        # 숫자 포함 단어 추출
        number_words = re.findall(r'[가-힣]*\d+[가-힣]*', query)
        
        all_keywords = korean_words + english_words + number_words
        
        # 중복 제거 및 길이 필터링
        unique_keywords = []
        for keyword in all_keywords:
            if len(keyword) >= 2 and keyword not in unique_keywords:
                unique_keywords.append(keyword)
        
        # 최대 3개 반환
        return unique_keywords[:3] if unique_keywords else [query[:20]]
    
    def _is_conversation_continuation(self, query: str, history: List[Dict]) -> bool:
        """대화 연속성 질문인지 확인"""
        if not history or len(history) == 0:
            return False
        
        # 연속성 표현들
        continuation_patterns = [
            "다음은", "그럼", "그러면", "또는", "아니면", "그리고", "그런데",
            "그래서", "그렇다면", "그럼에도", "하지만", "그런데도", "그래도",
            "계속", "이어서", "추가로", "더", "또", "그 외에", "다른",
            "next", "then", "also", "more", "continue", "what about", "how about"
        ]
        
        query_lower = query.lower().strip()
        
        # 짧은 연속성 질문 (10자 이하)
        if len(query.strip()) <= 10:
            for pattern in continuation_patterns:
                if pattern in query_lower:
                    return True
        
        # 질문이 짧고 이전 대화가 있는 경우
        if len(query.strip()) <= 20 and len(history) > 0:
            # 의문사로 시작하는 짧은 질문
            question_starters = ["뭐", "무엇", "어떤", "어떻게", "왜", "언제", "어디", "누가", "얼마"]
            for starter in question_starters:
                if query.strip().startswith(starter):
                    return True
        
        return False
    
    def _is_simple_greeting(self, query: str) -> bool:
        """간단한 인사말 확인"""
        greetings = ["안녕", "hello", "hi", "안녕하세요", "안녕하십니까"]
        query_lower = query.lower().strip()
        return any(greeting in query_lower for greeting in greetings) and len(query.strip()) < 20
    
    def _create_direct_answer_result(self, query: str, reason: str) -> Dict:
        """직접 답변 결과 생성 (대화 맥락 포함)"""
        return {
            "type": "Orchestration",
            "model": self.config.orchestration_model,
            "content": f"Direct answer required. Reason: {reason}",
            "parsed_result": {
                "needs_kb_search": False,
                "search_keywords": [],
                "intent": "Direct answer with context",
                "confidence": 0.9,
                "rule_applied": "direct_answer",
                "reasoning": reason,
                "context_applied": True,  # 대화 맥락 적용 표시
                "requires_conversation_context": True  # 대화 맥락 필요 표시
            },
            "error": False
        }
    
    def _create_error_result(self, error_msg: str) -> Dict:
        """에러 결과 생성"""
        return {
            "type": "Orchestration",
            "model": self.config.orchestration_model,
            "content": f"Orchestration error: {error_msg}",
            "parsed_result": {
                "needs_kb_search": False,
                "search_keywords": [],
                "intent": "Error occurred",
                "confidence": 0.0,
                "rule_applied": "error",
                "reasoning": f"Error: {error_msg}",
                "context_applied": False
            },
            "error": True
        }
    
    def get_model_name(self) -> str:
        """현재 사용 중인 모델명 반환"""
        model_id = self.config.orchestration_model
        if "claude-sonnet-4" in model_id:
            return "Claude 4 (KB-Priority)"
        elif "claude-3-7-sonnet" in model_id:
            return "Claude 3.7 Sonnet (KB-Priority)"
        elif "claude-3-5-sonnet" in model_id:
            return "Claude 3.5 Sonnet (KB-Priority)"
        elif "claude-3-5-haiku" in model_id:
            return "Claude 3.5 Haiku (KB-Priority)"
        elif "nova-lite" in model_id:
            return "Nova Lite (KB-Priority)"
        elif "nova-micro" in model_id:
            return "Nova Micro (KB-Priority)"
        else:
            return f"{model_id.split(':')[0]} (KB-Priority)"


# 기존 코드와의 호환성을 위한 별칭
OrchestrationAgent = OptimizedOrchestrationAgent
