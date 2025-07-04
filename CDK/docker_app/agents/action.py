"""
수정된 Action Agent 구현
올바른 메서드 시그니처와 강화된 KB 검색
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
    
    def act(self, context: Dict, previous_steps: List) -> Dict:
        """
        계획에 따라 액션 수행
        
        Args:
            context: 실행 컨텍스트
            previous_steps: 이전 단계들의 결과
            
        Returns:
            Action 결과
        """
        try:
            # 가장 최근 Orchestration 결과 찾기
            orchestration_result = None
            for step in reversed(previous_steps):
                if step.get("type") == "Orchestration":
                    orchestration_result = step
                    break
            
            if not orchestration_result:
                return self._create_error_response("Orchestration 결과를 찾을 수 없습니다.", [])
            
            parsed_orchestration = orchestration_result.get("parsed_result", {})
            needs_kb_search = parsed_orchestration.get("needs_kb_search", False)
            search_keywords = parsed_orchestration.get("search_keywords", [])
            
            print(f"   KB 검색 필요: {needs_kb_search}")
            print(f"   KB 활성화: {self.config.is_kb_enabled()}")
            print(f"   검색 키워드: {search_keywords}")
            
            # KB 검색이 필요하고 가능한 경우
            if needs_kb_search and self.config.is_kb_enabled() and search_keywords:
                print("   → KB 검색 실행")
                return self._perform_kb_search(search_keywords, context)
            
            # KB 검색이 필요하지 않은 경우
            elif not needs_kb_search:
                print("   → KB 검색 불필요")
                return self._perform_direct_response(orchestration_result, context)
            
            # KB가 비활성화되었거나 키워드가 없는 경우
            else:
                print("   → KB 검색 불가능")
                return self._handle_no_search_case(orchestration_result, context, search_keywords)
                
        except Exception as e:
            return self._create_error_response(f"Action 수행 중 오류 발생: {str(e)}", [])
    
    def _perform_kb_search(self, search_keywords: List[str], context: Dict) -> Dict:
        """Knowledge Base 검색 수행"""
        try:
            print(f"   KB ID: {self.config.kb_id}")
            print(f"   검색 키워드: {search_keywords}")
            
            if not self.kb_searcher:
                return self._create_error_response("KB 검색기가 초기화되지 않았습니다.", search_keywords)
            
            # 다중 키워드 검색 실행
            search_results = self.kb_searcher.search_multiple_queries(
                kb_id=self.config.kb_id,
                queries=search_keywords,
                max_results_per_query=2  # 키워드당 최대 2개 결과
            )
            
            print(f"   검색 결과: {len(search_results)}개")
            
            # 검색 결과를 컨텍스트에 저장
            context["kb_results"] = search_results
            
            # 검색 결과 요약 생성
            if search_results:
                content = f"✅ Knowledge Base 검색 완료: {len(search_results)}개 관련 문서 발견"
                
                # 검색 키워드별 결과 수 요약
                keyword_summary = {}
                for result in search_results:
                    keyword = result.get("query", "unknown")
                    keyword_summary[keyword] = keyword_summary.get(keyword, 0) + 1
                
                content += f"\n📊 검색 키워드별 결과: {dict(keyword_summary)}"
                
                # 상위 결과의 점수 정보
                top_scores = [r.get("score", 0) for r in search_results[:3]]
                content += f"\n🎯 상위 3개 결과 점수: {[f'{s:.3f}' for s in top_scores]}"
                
                # Citation 정보 추가
                citations = [f"[{result.get('citation_id', i+1)}]" for i, result in enumerate(search_results)]
                content += f"\n📚 Citations: {', '.join(citations)}"
                
                # 검색 결과 미리보기
                content += f"\n\n📄 검색 결과 미리보기:"
                for i, result in enumerate(search_results[:2]):  # 상위 2개만
                    preview = result.get('content', '')[:100]
                    content += f"\n[{i+1}] {preview}..."
                
            else:
                content = f"❌ Knowledge Base 검색 완료: 관련 문서를 찾지 못했습니다"
                content += f"\n🔍 검색한 키워드: {search_keywords}"
                content += f"\n💡 다른 키워드로 재시도를 권장합니다."
            
            return {
                "type": "Action",
                "model": self.config.action_model,
                "content": content,
                "parsed_result": {
                    "search_type": "knowledge_base",
                    "search_keywords": search_keywords,
                    "results_count": len(search_results),
                    "error": False
                },
                "search_results": search_results,
                "search_keywords": search_keywords,
                "error": False
            }
            
        except Exception as e:
            error_msg = f"KB 검색 중 오류 발생: {str(e)}"
            print(f"   ❌ {error_msg}")
            return self._create_error_response(error_msg, search_keywords)
    
    def _perform_direct_response(self, orchestration_result: Dict, context: Dict) -> Dict:
        """KB 검색이 필요하지 않은 경우의 처리"""
        parsed = orchestration_result.get("parsed_result", {})
        intent = parsed.get("intent", "알 수 없는 의도")
        
        # 의도에 따른 직접 응답 준비
        if "인사" in intent or "대화" in intent:
            content = "💬 일반적인 인사말로 판단되어 Knowledge Base 검색을 수행하지 않습니다."
        elif "계산" in intent or "수학" in intent:
            content = "🔢 수학 계산 문제로 판단되어 Knowledge Base 검색을 수행하지 않습니다."
        elif "무지개" in intent or "색상" in intent:
            content = "🌈 일반 상식 질문으로 판단되어 Knowledge Base 검색을 수행하지 않습니다."
        else:
            content = f"ℹ️ '{intent}' 의도로 판단되어 Knowledge Base 검색이 필요하지 않습니다."
        
        return {
            "type": "Action",
            "model": self.config.action_model,
            "content": content,
            "parsed_result": {
                "search_type": "direct_response",
                "intent": intent,
                "error": False
            },
            "search_results": [],
            "search_keywords": [],
            "error": False
        }
    
    def _handle_no_search_case(self, orchestration_result: Dict, context: Dict, search_keywords: List[str]) -> Dict:
        """검색을 수행할 수 없는 경우의 처리"""
        if not self.config.is_kb_enabled():
            content = "⚠️ Knowledge Base가 설정되지 않아 검색을 수행할 수 없습니다."
            content += f"\n💡 KB ID를 설정하면 더 정확한 답변을 제공할 수 있습니다."
        elif not search_keywords:
            content = "⚠️ 검색 키워드가 생성되지 않아 Knowledge Base 검색을 수행할 수 없습니다."
            content += f"\n💡 더 구체적인 질문을 해주시면 도움이 됩니다."
        else:
            content = "⚠️ 알 수 없는 이유로 Knowledge Base 검색을 수행할 수 없습니다."
            content += f"\n🔍 시도한 키워드: {search_keywords}"
        
        return {
            "type": "Action",
            "model": self.config.action_model,
            "content": content,
            "parsed_result": {
                "search_type": "no_search",
                "search_keywords": search_keywords,
                "error": True,
                "error_reason": "KB 검색 불가능"
            },
            "search_results": [],
            "search_keywords": search_keywords,
            "error": True
        }
    
    def _create_error_response(self, error_msg: str, search_keywords: List[str]) -> Dict:
        """에러 응답 생성"""
        return {
            "type": "Action",
            "model": self.config.action_model,
            "content": f"❌ {error_msg}",
            "parsed_result": {
                "search_type": "error",
                "search_keywords": search_keywords,
                "error": True,
                "error_message": error_msg
            },
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
                return self._create_error_response("재검색할 대체 키워드를 생성할 수 없습니다.", original_keywords)
            
            print(f"   🔄 재검색 키워드: {new_keywords}")
            
            # 새로운 키워드로 검색 수행
            return self._perform_kb_search(new_keywords, context)
            
        except Exception as e:
            return self._create_error_response(f"재검색 중 오류: {str(e)}", original_keywords)
    
    def _generate_alternative_keywords(self, original_keywords: List[str]) -> List[str]:
        """원래 키워드에서 대체 키워드 생성"""
        alternatives = []
        
        for keyword in original_keywords:
            # 간단한 동의어 매핑
            synonyms = {
                "회사": ["기업", "조직", "법인"],
                "절차": ["과정", "프로세스", "단계"],
                "방법": ["방식", "수단", "절차"],
                "정책": ["규정", "지침", "원칙"],
                "투자": ["자금", "출자", "투입"],
                "승인": ["허가", "인가", "결재"]
            }
            
            if keyword in synonyms:
                alternatives.extend(synonyms[keyword])
            else:
                # 원래 키워드도 포함
                alternatives.append(keyword)
        
        return alternatives[:3]  # 최대 3개
    
    def test_kb_connection(self) -> Dict:
        """KB 연결 테스트"""
        try:
            if not self.config.is_kb_enabled():
                return {
                    "success": False,
                    "message": "Knowledge Base ID가 설정되지 않았습니다."
                }
            
            if not self.kb_searcher:
                return {
                    "success": False,
                    "message": "KB 검색기가 초기화되지 않았습니다."
                }
            
            # 간단한 테스트 검색
            test_results = self.kb_searcher.search(
                kb_id=self.config.kb_id,
                query="테스트",
                max_results=1
            )
            
            return {
                "success": True,
                "message": f"KB 연결 성공. 테스트 검색 결과: {len(test_results)}개",
                "kb_id": self.config.kb_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"KB 연결 테스트 실패: {str(e)}"
            }
    
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
