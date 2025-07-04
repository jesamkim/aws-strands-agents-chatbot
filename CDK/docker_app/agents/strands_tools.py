"""
AWS Strands Agents Tools for ReAct Chatbot
Knowledge Base 검색 및 분석을 위한 도구들
"""

from typing import Dict, List, Any, Optional
import json

# Strands import with fallback to mock
try:
    from strands import tool
    STRANDS_AVAILABLE = True
except ImportError:
    print("⚠️ Strands Agents 라이브러리를 찾을 수 없습니다. Mock 버전을 사용합니다.")
    from .mock_strands import mock_tool as tool
    STRANDS_AVAILABLE = False

from utils.config import AgentConfig
from utils.kb_search import KnowledgeBaseSearcher
from utils.bedrock_client import BedrockClient


class StrandsToolsManager:
    """Strands Agents 도구 관리자"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.kb_searcher = KnowledgeBaseSearcher() if config.is_kb_enabled() else None
        self.bedrock_client = BedrockClient()
        
        # 도구들을 동적으로 생성
        self._create_tools()
    
    def _create_tools(self):
        """도구들을 동적으로 생성"""
        # KB 검색 도구
        @tool
        def kb_search_tool(keywords: List[str], max_results: int = 5) -> str:
            """
            Knowledge Base에서 키워드로 검색을 수행합니다.
            
            Args:
                keywords: 검색할 키워드 리스트
                max_results: 최대 결과 수
                
            Returns:
                검색 결과를 JSON 문자열로 반환
            """
            return self._kb_search_impl(keywords, max_results)
        
        # 대화 맥락 분석 도구
        @tool
        def conversation_context_analyzer(query: str, history: List[Dict]) -> str:
            """
            대화 맥락을 분석하여 질문의 성격을 파악합니다.
            
            Args:
                query: 현재 사용자 질문
                history: 대화 히스토리
                
            Returns:
                분석 결과를 JSON 문자열로 반환
            """
            return self._context_analysis_impl(query, history)
        
        # 검색 품질 평가 도구
        @tool
        def search_quality_assessor(search_results: List[Dict], iteration: int = 1) -> str:
            """
            검색 결과의 품질을 평가하고 재시도 필요성을 판단합니다.
            
            Args:
                search_results: 검색 결과 리스트
                iteration: 현재 반복 횟수
                
            Returns:
                품질 평가 결과를 JSON 문자열로 반환
            """
            return self._quality_assessment_impl(search_results, iteration)
        
        # Citation 생성 도구
        @tool
        def citation_generator(search_results: List[Dict], answer: str) -> str:
            """
            검색 결과를 바탕으로 Citation이 포함된 답변을 생성합니다.
            
            Args:
                search_results: 검색 결과 리스트
                answer: 기본 답변
                
            Returns:
                Citation이 포함된 답변
            """
            return self._citation_generation_impl(search_results, answer)
        
        # 키워드 생성 도구
        @tool
        def keyword_generator(query: str, kb_description: str = "", previous_keywords: List[str] = None) -> str:
            """
            검색을 위한 최적화된 키워드를 생성합니다.
            
            Args:
                query: 사용자 질문
                kb_description: KB 설명
                previous_keywords: 이전에 사용한 키워드 (재시도용)
                
            Returns:
                생성된 키워드를 JSON 문자열로 반환
            """
            return self._keyword_generation_impl(query, kb_description, previous_keywords)
        
        # 도구들을 인스턴스 변수로 저장
        self.kb_search_tool = kb_search_tool
        self.conversation_context_analyzer = conversation_context_analyzer
        self.search_quality_assessor = search_quality_assessor
        self.citation_generator = citation_generator
        self.keyword_generator = keyword_generator
    
    def get_all_tools(self) -> List[callable]:
        """모든 도구 반환"""
        return [
            self.kb_search_tool,
            self.conversation_context_analyzer,
            self.search_quality_assessor,
            self.citation_generator,
            self.keyword_generator
        ]
    
    def _kb_search_impl(self, keywords: List[str], max_results: int = 5) -> str:
        """
        KB 검색 구현
        """
        try:
            if not self.config.is_kb_enabled() or not self.kb_searcher:
                return json.dumps({
                    "success": False,
                    "error": "Knowledge Base가 설정되지 않았습니다.",
                    "results": []
                })
            
            # 다중 키워드 검색
            search_results = self.kb_searcher.search_multiple_queries(
                kb_id=self.config.kb_id,
                queries=keywords,
                max_results_per_query=max(1, max_results // len(keywords))
            )
            
            # 결과 정리
            formatted_results = []
            for i, result in enumerate(search_results[:max_results]):
                formatted_results.append({
                    "id": i + 1,
                    "content": result.get("content", ""),
                    "source": result.get("source", ""),
                    "score": result.get("score", 0),
                    "query": result.get("query", "")
                })
            
            return json.dumps({
                "success": True,
                "results_count": len(formatted_results),
                "results": formatted_results,
                "search_keywords": keywords
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"KB 검색 중 오류: {str(e)}",
                "results": []
            })
    
    def _context_analysis_impl(self, query: str, history: List[Dict]) -> str:
        """
        대화 맥락을 분석하여 질문의 성격을 파악합니다.
        
        Args:
            query: 현재 사용자 질문
            history: 대화 히스토리
            
        Returns:
            분석 결과를 JSON 문자열로 반환
        """
        try:
            # 연속성 질문 패턴 확인
            continuation_patterns = [
                "다음은", "그럼", "그러면", "또는", "아니면", "그리고", "그런데",
                "그래서", "그렇다면", "계속", "이어서", "추가로", "더", "또"
            ]
            
            is_continuation = any(pattern in query.lower() for pattern in continuation_patterns)
            
            # 인사말 확인
            greetings = ["안녕", "hello", "hi", "안녕하세요"]
            is_greeting = any(greeting in query.lower() for greeting in greetings) and len(query.strip()) < 20
            
            # 이전 대화 맥락 추출
            recent_context = ""
            if history and len(history) > 0:
                for msg in history[-3:]:  # 최근 3개 메시지
                    role = msg.get("role", "")
                    content = msg.get("content", "")[:100]
                    recent_context += f"{role}: {content}\n"
            
            analysis_result = {
                "is_continuation": is_continuation,
                "is_greeting": is_greeting,
                "has_context": len(history) > 0,
                "recent_context": recent_context,
                "query_length": len(query),
                "needs_kb_search": not (is_continuation or is_greeting) and self.config.is_kb_enabled(),
                "confidence": 0.9 if is_continuation or is_greeting else 0.7
            }
            
            return json.dumps(analysis_result)
            
        except Exception as e:
            return json.dumps({
                "error": f"대화 맥락 분석 중 오류: {str(e)}",
                "is_continuation": False,
                "is_greeting": False,
                "has_context": False,
                "needs_kb_search": True
            })
    
    @tool
    def search_quality_assessor(self, search_results: List[Dict], iteration: int = 1) -> str:
        """
        검색 결과의 품질을 평가하고 재시도 필요성을 판단합니다.
        
        Args:
            search_results: 검색 결과 리스트
            iteration: 현재 반복 횟수
            
        Returns:
            품질 평가 결과를 JSON 문자열로 반환
        """
        try:
            if not search_results or len(search_results) == 0:
                return json.dumps({
                    "quality_score": 0.0,
                    "needs_retry": iteration < 5,
                    "reason": "검색 결과 없음",
                    "is_sufficient": False
                })
            
            # 반복 횟수에 따른 기준 조정
            if iteration <= 2:
                min_avg_score = 0.5
                min_max_score = 0.6
            elif iteration <= 4:
                min_avg_score = 0.4
                min_max_score = 0.5
            else:
                min_avg_score = 0.2
                min_max_score = 0.3
            
            # 점수 계산
            scores = [result.get("score", 0) for result in search_results]
            avg_score = sum(scores) / len(scores)
            max_score = max(scores)
            
            # 내용 길이 확인
            total_content_length = sum(len(result.get("content", "")) for result in search_results)
            
            # 품질 평가
            is_sufficient = (
                avg_score >= min_avg_score and 
                max_score >= min_max_score and 
                total_content_length >= 100
            ) or iteration >= 5
            
            assessment = {
                "quality_score": avg_score,
                "max_score": max_score,
                "results_count": len(search_results),
                "total_content_length": total_content_length,
                "needs_retry": not is_sufficient and iteration < 5,
                "is_sufficient": is_sufficient,
                "iteration": iteration,
                "reason": f"평균 점수: {avg_score:.3f}, 최고 점수: {max_score:.3f}, 반복: {iteration}회"
            }
            
            return json.dumps(assessment)
            
        except Exception as e:
            return json.dumps({
                "quality_score": 0.0,
                "needs_retry": False,
                "reason": f"품질 평가 중 오류: {str(e)}",
                "is_sufficient": True  # 오류 시 진행
            })
    
    @tool
    def citation_generator(self, search_results: List[Dict], answer: str) -> str:
        """
        검색 결과를 바탕으로 Citation이 포함된 답변을 생성합니다.
        
        Args:
            search_results: 검색 결과 리스트
            answer: 기본 답변
            
        Returns:
            Citation이 포함된 답변
        """
        try:
            if not search_results:
                return answer
            
            # Citation 정보 생성
            citations = []
            for i, result in enumerate(search_results):
                citation_id = i + 1
                source = result.get("source", f"출처 {citation_id}")
                citations.append(f"[{citation_id}] {source}")
            
            # 답변에 Citation 추가 (없는 경우)
            enhanced_answer = answer
            if "참고 자료" not in answer and "References" not in answer:
                enhanced_answer += "\n\n**참고 자료:**\n"
                enhanced_answer += "\n".join(citations)
            
            return enhanced_answer
            
        except Exception as e:
            return f"{answer}\n\n(Citation 생성 중 오류 발생: {str(e)})"
    
    @tool
    def keyword_generator(self, query: str, kb_description: str = "", previous_keywords: List[str] = None) -> str:
        """
        검색을 위한 최적화된 키워드를 생성합니다.
        
        Args:
            query: 사용자 질문
            kb_description: KB 설명
            previous_keywords: 이전에 사용한 키워드 (재시도용)
            
        Returns:
            생성된 키워드를 JSON 문자열로 반환
        """
        try:
            # 재시도인 경우 대체 키워드 생성
            if previous_keywords:
                return json.dumps(self._generate_alternative_keywords(query, previous_keywords))
            
            # 초기 키워드 생성
            prompt = f"""사용자 질문: {query}
KB 설명: {kb_description}

위 질문에 대해 Knowledge Base에서 검색할 최적의 한국어 키워드 3개를 생성해주세요.
JSON 배열 형태로만 응답하세요: ["키워드1", "키워드2", "키워드3"]"""
            
            response = self.bedrock_client.invoke_model(
                model_id=self.config.orchestration_model,
                prompt=prompt,
                temperature=0.0,
                max_tokens=100,
                system_prompt="당신은 검색 키워드 생성 전문가입니다. JSON 배열 형태로만 응답하세요."
            )
            
            # JSON 파싱
            import re
            json_match = re.search(r'\[.*?\]', response)
            if json_match:
                keywords_json = json_match.group()
                keywords = json.loads(keywords_json)
                if isinstance(keywords, list) and len(keywords) > 0:
                    return json.dumps({"keywords": keywords[:3]})
            
            # 폴백
            return json.dumps({"keywords": self._extract_keywords_fallback(query)})
            
        except Exception as e:
            return json.dumps({
                "keywords": self._extract_keywords_fallback(query),
                "error": f"키워드 생성 중 오류: {str(e)}"
            })
    
    def _generate_alternative_keywords(self, query: str, previous_keywords: List[str]) -> Dict:
        """대체 키워드 생성"""
        synonym_map = {
            "규정": ["정책", "지침", "기준"],
            "지원": ["혜택", "보조", "도움"],
            "승인": ["허가", "인가", "결재"],
            "회사": ["기업", "조직", "직장"],
            "절차": ["과정", "프로세스", "단계"]
        }
        
        alternatives = []
        for keyword in previous_keywords:
            for original, synonyms in synonym_map.items():
                if original in keyword:
                    for synonym in synonyms:
                        new_keyword = keyword.replace(original, synonym)
                        if new_keyword not in alternatives:
                            alternatives.append(new_keyword)
                            break
                    break
        
        if not alternatives:
            alternatives = self._extract_keywords_fallback(query)
        
        return {"keywords": alternatives[:3]}
    
    def _extract_keywords_fallback(self, query: str) -> List[str]:
        """폴백 키워드 추출"""
        import re
        korean_words = re.findall(r'[가-힣]+', query)
        english_words = re.findall(r'[a-zA-Z]+', query)
        
        all_keywords = korean_words + english_words
        unique_keywords = []
        
        for keyword in all_keywords:
            if len(keyword) >= 2 and keyword not in unique_keywords:
                unique_keywords.append(keyword)
        
        return unique_keywords[:3] if unique_keywords else [query[:20]]
