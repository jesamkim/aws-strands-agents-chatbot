"""
Action Agent 구현
실제 액션 수행을 담당 (주로 Knowledge Base 검색)
"""

from typing import Dict, List, Any
from utils.config import AgentConfig
from utils.kb_search import KnowledgeBaseSearcher


class ActionAgent:
    """
    실제 액션 수행을 담당하는 Agent
    
    주요 역할:
    - Knowledge Base 검색 실행
    - 도구 선택 및 실행
    - 검색 결과 수집 및 정리
    """
    
    def __init__(self, config: AgentConfig):
        """
        Action Agent 초기화
        
        Args:
            config: Agent 설정
        """
        self.config = config
        self.kb_searcher = KnowledgeBaseSearcher() if config.is_kb_enabled() else None
    
    def act(self, orchestration_result: Dict, context: Dict) -> Dict:
        """
        계획에 따라 액션 수행
        
        Args:
            orchestration_result: Orchestration 단계 결과
            context: 실행 컨텍스트
            
        Returns:
            Action 결과
        """
        try:
            parsed_orchestration = orchestration_result.get("parsed_result", {})
            needs_kb_search = parsed_orchestration.get("needs_kb_search", False)
            search_keywords = parsed_orchestration.get("search_keywords", [])
            
            # KB 검색이 필요하고 가능한 경우
            if needs_kb_search and self.config.is_kb_enabled() and search_keywords:
                return self._perform_kb_search(search_keywords, context)
            
            # KB 검색이 필요하지 않은 경우
            elif not needs_kb_search:
                return self._perform_direct_response(orchestration_result, context)
            
            # KB가 비활성화되었거나 키워드가 없는 경우
            else:
                return self._handle_no_search_case(orchestration_result, context)
                
        except Exception as e:
            return {
                "type": "Action",
                "model": self.config.action_model,
                "content": f"Action 수행 중 오류 발생: {str(e)}",
                "search_results": [],
                "error": True
            }
    
    def _perform_kb_search(self, search_keywords: List[str], context: Dict) -> Dict:
        """Knowledge Base 검색 수행"""
        try:
            # 다중 키워드 검색 실행
            search_results = self.kb_searcher.search_multiple_queries(
                kb_id=self.config.kb_id,
                queries=search_keywords,
                max_results_per_query=2  # 키워드당 최대 2개 결과
            )
            
            # 검색 결과를 컨텍스트에 저장
            context["kb_results"] = search_results
            
            # 검색 결과 요약 생성
            if search_results:
                content = f"Knowledge Base 검색 완료: {len(search_results)}개 관련 문서 발견"
                
                # 검색 키워드별 결과 수 요약
                keyword_summary = {}
                for result in search_results:
                    keyword = result.get("query", "unknown")
                    keyword_summary[keyword] = keyword_summary.get(keyword, 0) + 1
                
                content += f"\n검색 키워드별 결과: {dict(keyword_summary)}"
                
                # 상위 결과의 점수 정보
                top_scores = [r.get("score", 0) for r in search_results[:3]]
                content += f"\n상위 3개 결과 점수: {[f'{s:.3f}' for s in top_scores]}"
                
                # Citation 정보 추가
                citations = [f"[{result.get('citation_id', i+1)}]" for i, result in enumerate(search_results)]
                content += f"\nCitations: {', '.join(citations)}"
                
            else:
                content = f"Knowledge Base 검색 완료: 관련 문서를 찾지 못했습니다"
                content += f"\n검색한 키워드: {search_keywords}"
            
            return {
                "type": "Action",
                "model": self.config.action_model,
                "content": content,
                "search_results": search_results,
                "search_keywords": search_keywords,
                "error": False
            }
            
        except Exception as e:
            return {
                "type": "Action",
                "model": self.config.action_model,
                "content": f"KB 검색 중 오류 발생: {str(e)}",
                "search_results": [],
                "search_keywords": search_keywords,
                "error": True
            }
    
    def _perform_direct_response(self, orchestration_result: Dict, context: Dict) -> Dict:
        """KB 검색이 필요하지 않은 경우의 처리"""
        parsed = orchestration_result.get("parsed_result", {})
        intent = parsed.get("intent", "알 수 없는 의도")
        
        # 의도에 따른 직접 응답 준비
        if "인사" in intent or "대화" in intent:
            content = "일반적인 인사말로 판단되어 Knowledge Base 검색을 수행하지 않습니다."
        elif "계산" in intent or "수학" in intent:
            content = "수학 계산 문제로 판단되어 Knowledge Base 검색을 수행하지 않습니다."
        else:
            content = f"'{intent}' 의도로 판단되어 Knowledge Base 검색이 필요하지 않습니다."
        
        return {
            "type": "Action",
            "model": self.config.action_model,
            "content": content,
            "search_results": [],
            "search_keywords": [],
            "error": False
        }
    
    def _handle_no_search_case(self, orchestration_result: Dict, context: Dict) -> Dict:
        """검색을 수행할 수 없는 경우의 처리"""
        parsed = orchestration_result.get("parsed_result", {})
        search_keywords = parsed.get("search_keywords", [])
        
        if not self.config.is_kb_enabled():
            content = "Knowledge Base가 설정되지 않아 검색을 수행할 수 없습니다."
        elif not search_keywords:
            content = "검색 키워드가 생성되지 않아 Knowledge Base 검색을 수행할 수 없습니다."
        else:
            content = "알 수 없는 이유로 Knowledge Base 검색을 수행할 수 없습니다."
        
        return {
            "type": "Action",
            "model": self.config.action_model,
            "content": content,
            "search_results": [],
            "search_keywords": search_keywords,
            "error": True
        }
    
    def retry_with_different_keywords(self, 
                                   original_keywords: List[str], 
                                   context: Dict,
                                   retry_suggestions: List[str] = None) -> Dict:
        """
        다른 키워드로 재검색 수행
        
        Args:
            original_keywords: 원래 검색 키워드
            context: 실행 컨텍스트
            retry_suggestions: Observation Agent가 제안한 새로운 키워드
            
        Returns:
            재검색 결과
        """
        try:
            # 재시도 키워드 결정
            if retry_suggestions:
                new_keywords = retry_suggestions
            else:
                # 원래 키워드를 변형하여 새로운 키워드 생성
                new_keywords = self._generate_alternative_keywords(original_keywords)
            
            if not new_keywords:
                return {
                    "type": "Action",
                    "model": self.config.action_model,
                    "content": "재검색할 대체 키워드를 생성할 수 없습니다.",
                    "search_results": [],
                    "search_keywords": [],
                    "error": True
                }
            
            # 새로운 키워드로 검색 수행
            search_results = self.kb_searcher.search_multiple_queries(
                kb_id=self.config.kb_id,
                queries=new_keywords,
                max_results_per_query=3  # 재시도 시 더 많은 결과 시도
            )
            
            # 컨텍스트 업데이트
            context["kb_results"] = search_results
            context["retry_keywords"] = new_keywords
            
            content = f"대체 키워드로 재검색 완료: {len(search_results)}개 문서 발견"
            content += f"\n원래 키워드: {original_keywords}"
            content += f"\n새로운 키워드: {new_keywords}"
            
            return {
                "type": "Action",
                "model": self.config.action_model,
                "content": content,
                "search_results": search_results,
                "search_keywords": new_keywords,
                "original_keywords": original_keywords,
                "is_retry": True,
                "error": False
            }
            
        except Exception as e:
            return {
                "type": "Action",
                "model": self.config.action_model,
                "content": f"재검색 중 오류 발생: {str(e)}",
                "search_results": [],
                "search_keywords": new_keywords if 'new_keywords' in locals() else [],
                "error": True
            }
    
    def _generate_alternative_keywords(self, original_keywords: List[str]) -> List[str]:
        """원래 키워드를 바탕으로 대체 키워드 생성"""
        alternative_keywords = []
        
        # 키워드 변형 규칙
        keyword_variations = {
            "투자": ["투자안", "투자계획", "자본투자", "투자결정"],
            "승인": ["허가", "결재", "인가", "승인절차"],
            "절차": ["프로세스", "과정", "단계", "방법"],
            "포스코": ["POSCO", "회사", "기업"],
            "관리": ["운영", "관리체계", "시스템"],
            "심의": ["검토", "심사", "평가"]
        }
        
        for keyword in original_keywords:
            # 원래 키워드의 일부를 찾아서 변형
            for base_word, variations in keyword_variations.items():
                if base_word in keyword:
                    for variation in variations:
                        new_keyword = keyword.replace(base_word, variation)
                        if new_keyword != keyword and new_keyword not in alternative_keywords:
                            alternative_keywords.append(new_keyword)
        
        # 일반적인 대체 키워드 추가
        general_alternatives = [
            "품의서", "결재라인", "승인권한", "의사결정", 
            "업무절차", "규정", "지침", "매뉴얼"
        ]
        
        for alt in general_alternatives:
            if alt not in alternative_keywords:
                alternative_keywords.append(alt)
        
        return alternative_keywords[:5]  # 최대 5개
    
    def get_model_name(self) -> str:
        """현재 사용 중인 모델명 반환"""
        model_id = self.config.action_model
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
