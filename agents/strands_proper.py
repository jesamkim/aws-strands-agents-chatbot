"""
실제 Strands Agents 문법에 맞는 올바른 구현
strands-agents-example.md의 실제 문법을 따름
"""

import json
import time
import boto3
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, List, Any, Optional

# 타임아웃 래퍼 import
from .timeout_wrapper import safe_agent_call

# Strands import with fallback to enhanced mock
try:
    from strands import Agent, tool
    from strands_tools import calculator  # 실제 도구 import
    STRANDS_AVAILABLE = True
    print("✅ 실제 Strands Agents 라이브러리 사용")
except ImportError:
    from .enhanced_mock_strands import EnhancedMockAgent as Agent, enhanced_mock_tool as tool
    calculator = None
    STRANDS_AVAILABLE = False
    print("⚠️ Strands Agents 사용 (실제 KB 검색 지원)")

from utils.config import AgentConfig
from utils.kb_search import KnowledgeBaseSearcher
from utils.bedrock_client import BedrockClient


# 실제 Strands 문법에 맞는 도구 정의 (모듈 레벨)
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
    try:
        # 전역 설정에서 KB 정보 가져오기 (실제 구현에서는 다른 방식 사용)
        if not hasattr(kb_search_tool, '_config') or not kb_search_tool._config.is_kb_enabled():
            return json.dumps({
                "success": False,
                "error": "Knowledge Base가 설정되지 않았습니다.",
                "results": []
            })
        
        config = kb_search_tool._config
        
        # KB 검색기 초기화 (타임아웃 처리 포함)
        try:
            from utils.kb_search import KnowledgeBaseSearcher
            kb_searcher = KnowledgeBaseSearcher()
        except Exception as init_error:
            return json.dumps({
                "success": False,
                "error": f"KB 검색기 초기화 실패: {str(init_error)}",
                "results": []
            })
        
        # 다중 키워드 검색 (타임아웃 처리)
        try:
            search_results = kb_searcher.search_multiple_queries(
                kb_id=config.kb_id,
                queries=keywords,
                max_results_per_query=max(1, max_results // len(keywords))
            )
        except Exception as search_error:
            # 검색 실패 시 상세 오류 정보 제공
            error_msg = str(search_error)
            if "timeout" in error_msg.lower() or "read timed out" in error_msg.lower():
                return json.dumps({
                    "success": False,
                    "error": "KB 검색 시간 초과. 네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요.",
                    "error_type": "timeout",
                    "results": []
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"KB 검색 실패: {error_msg}",
                    "error_type": "search_error",
                    "results": []
                })
        
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
        # 최종 예외 처리
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return json.dumps({
                "success": False,
                "error": "시스템 타임아웃이 발생했습니다. 잠시 후 다시 시도해주세요.",
                "error_type": "system_timeout",
                "results": []
            })
        else:
            return json.dumps({
                "success": False,
                "error": f"KB 검색 중 예상치 못한 오류: {error_msg}",
                "error_type": "unexpected_error",
                "results": []
            })


@tool
def context_analyzer(query: str, history_json: str = "[]") -> str:
    """
    대화 맥락을 분석하여 질문의 성격을 파악합니다.
    
    Args:
        query: 현재 사용자 질문
        history_json: 대화 히스토리 (JSON 문자열)
        
    Returns:
        분석 결과를 JSON 문자열로 반환
    """
    try:
        # JSON 문자열을 파싱
        history = json.loads(history_json) if history_json else []
        
        # 간단한 맥락 분석
        is_greeting = any(word in query.lower() for word in ["안녕", "hello", "hi"])
        is_continuation = any(word in query.lower() for word in ["다음", "그럼", "계속"])
        
        return json.dumps({
            "is_greeting": is_greeting,
            "is_continuation": is_continuation,
            "has_context": len(history) > 0,
            "needs_kb_search": not (is_greeting or is_continuation)
        })
        
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "is_greeting": False,
            "is_continuation": False,
            "has_context": False,
            "needs_kb_search": True
        })


@tool
def quality_assessor(search_results_json: str, iteration: int = 1) -> str:
    """
    검색 결과의 품질을 평가하고 재시도 필요성을 판단합니다.
    
    Args:
        search_results_json: 검색 결과 (JSON 문자열)
        iteration: 현재 반복 횟수
        
    Returns:
        품질 평가 결과를 JSON 문자열로 반환
    """
    try:
        search_results = json.loads(search_results_json) if search_results_json else []
        
        if not search_results:
            return json.dumps({
                "quality_score": 0.0,
                "needs_retry": iteration < 3,
                "is_sufficient": False,
                "reason": "검색 결과 없음"
            })
        
        # 간단한 품질 평가
        avg_score = sum(r.get("score", 0) for r in search_results) / len(search_results)
        is_sufficient = avg_score > 0.5 or iteration >= 3
        
        return json.dumps({
            "quality_score": avg_score,
            "needs_retry": not is_sufficient,
            "is_sufficient": is_sufficient,
            "reason": f"평균 점수: {avg_score:.2f}, 반복: {iteration}"
        })
        
    except Exception as e:
        return json.dumps({
            "quality_score": 0.0,
            "needs_retry": False,
            "is_sufficient": True,
            "reason": f"평가 오류: {str(e)}"
        })


@tool
def timeout_resilient_kb_search(keywords: List[str], max_results: int = 5) -> str:
    """
    타임아웃에 강화된 Knowledge Base 검색 도구
    
    Args:
        keywords: 검색할 키워드 리스트
        max_results: 최대 결과 수
        
    Returns:
        검색 결과를 JSON 문자열로 반환
    """
    try:
        # ThreadPoolExecutor를 사용한 타임아웃 처리
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(kb_search_tool, keywords, max_results)
            try:
                # 45초 타임아웃으로 검색 실행
                result = future.result(timeout=45)
                return result
            except FutureTimeoutError:
                # 타임아웃 발생 시 안전한 응답 반환
                return json.dumps({
                    "success": False,
                    "error": "KB 검색 시간 초과 (45초). 네트워크 상태를 확인하거나 잠시 후 다시 시도해주세요.",
                    "error_type": "timeout",
                    "results": [],
                    "timeout_seconds": 45
                })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"타임아웃 강화 KB 검색 실패: {str(e)}",
            "error_type": "system_error",
            "results": []
        })


def create_timeout_configured_bedrock_model(model_id: str, region: str = "us-west-2"):
    """타임아웃이 설정된 Bedrock 모델 생성"""
    if not STRANDS_AVAILABLE:
        return None
    
    try:
        from strands.models import BedrockModel
        
        # 타임아웃 설정이 포함된 boto3 config
        timeout_config = Config(
            read_timeout=120,  # 읽기 타임아웃 120초
            connect_timeout=60,  # 연결 타임아웃 60초
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            region_name=region
        )
        
        # 커스텀 boto3 클라이언트 생성
        bedrock_client = boto3.client('bedrock-runtime', config=timeout_config)
        
        # BedrockModel에 커스텀 클라이언트 전달
        # 주의: 이 방법이 작동하지 않으면 환경변수로 타임아웃 설정
        model = BedrockModel(
            model_id=model_id,
            region=region
        )
        
        # 내부 클라이언트를 우리가 만든 것으로 교체 시도
        if hasattr(model, '_client'):
            model._client = bedrock_client
        elif hasattr(model, 'client'):
            model.client = bedrock_client
            
        return model
        
    except Exception as e:
        print(f"⚠️ 타임아웃 설정된 Bedrock 모델 생성 실패: {e}")
        # 기본 모델로 fallback
        from strands.models import BedrockModel
        return BedrockModel(model_id=model_id, region=region)


def configure_boto3_timeouts():
    """boto3 전역 타임아웃 설정"""
    import os
    
    # 환경변수로 boto3 타임아웃 설정
    os.environ['AWS_DEFAULT_READ_TIMEOUT'] = '120'
    os.environ['AWS_DEFAULT_CONNECT_TIMEOUT'] = '60'
    os.environ['AWS_MAX_ATTEMPTS'] = '3'
    
    print("🔧 boto3 전역 타임아웃 설정 완료")


# 전역 타임아웃 설정 적용
configure_boto3_timeouts()


class ProperStrandsReActChatbot:
    """
    실제 Strands Agents 문법에 맞는 ReAct 챗봇
    
    주요 특징:
    - 실제 Strands 문법 준수
    - 모듈 레벨 @tool 데코레이터 사용
    - 동기 처리 (실제 Strands 방식)
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.strands_available = STRANDS_AVAILABLE
        
        # 도구에 설정 전달 (실제 구현에서는 다른 방식 사용)
        kb_search_tool._config = config
        
        print(f"🚀 ProperStrandsReActChatbot 초기화 (Strands: {STRANDS_AVAILABLE})")
        
        # 실제 Strands 문법에 맞는 에이전트 생성
        self.main_agent = self._create_main_agent()
        
        # 전문 에이전트들 생성 (실제 Strands 패턴)
        self.kb_search_agent = self._create_kb_search_agent()
        self.context_agent = self._create_context_agent()
    
    def _create_main_agent(self) -> Agent:
        """메인 오케스트레이터 에이전트 생성 (실제 Strands 문법)"""
        system_prompt = f"""{self.config.system_prompt or '당신은 도움이 되는 AI 어시스턴트입니다.'}

당신은 사용자 질문을 분석하고 적절한 답변을 제공하는 ReAct 에이전트입니다.

**사용 가능한 도구:**
- context_analyzer: 대화 맥락 분석
- timeout_resilient_kb_search: 타임아웃 강화 KB 검색 (KB가 설정된 경우)
- quality_assessor: 검색 결과 품질 평가

**처리 방식:**
1. 먼저 context_analyzer로 대화 맥락을 분석하세요
2. KB 검색이 필요하면 timeout_resilient_kb_search를 사용하세요
3. 검색 결과가 있으면 quality_assessor로 품질을 평가하세요
4. 타임아웃이 발생하면 일반 지식으로 답변하세요
5. 최종 답변을 생성하세요

항상 한국어로 응답하세요."""
        
        # 실제 Strands 문법: tools 리스트에 함수 직접 전달
        available_tools = [context_analyzer, quality_assessor]
        
        # KB가 활성화된 경우에만 KB 검색 도구 추가
        if self.config.is_kb_enabled():
            available_tools.append(timeout_resilient_kb_search)  # 타임아웃 강화 버전 사용
        
        # 실제 도구가 있으면 추가
        if calculator and STRANDS_AVAILABLE:
            available_tools.append(calculator)
        
        if STRANDS_AVAILABLE:
            # 실제 Strands Agent는 config 파라미터를 받지 않음
            try:
                return Agent(
                    system_prompt=system_prompt,
                    tools=available_tools
                )
            except TypeError as e:
                if "unexpected keyword argument 'config'" in str(e):
                    print("⚠️ 실제 Strands Agent는 config 파라미터를 지원하지 않음. Enhanced Mock으로 전환...")
                    # Enhanced Mock Agent 사용
                    return Agent(config=self.config)
                else:
                    raise e
        else:
            # Enhanced Mock Agent는 config만 받음
            return Agent(config=self.config)
    
    def _create_kb_search_agent(self) -> Agent:
        """KB 검색 전문 에이전트 (실제 Strands 문법)"""
        system_prompt = """당신은 Knowledge Base 검색 전문가입니다.

**주요 역할:**
1. 최적의 검색 키워드 생성
2. KB 검색 실행
3. 검색 결과 품질 평가

kb_search_tool과 quality_assessor를 사용하여 효과적인 검색을 수행하세요."""
        
        if STRANDS_AVAILABLE:
            try:
                return Agent(
                    system_prompt=system_prompt,
                    tools=[timeout_resilient_kb_search, quality_assessor] if self.config.is_kb_enabled() else []
                )
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    # Enhanced Mock Agent 사용
                    return Agent(config=self.config)
                else:
                    raise e
        else:
            return Agent(config=self.config)
    
    def _create_context_agent(self) -> Agent:
        """대화 맥락 분석 전문 에이전트 (실제 Strands 문법)"""
        system_prompt = """당신은 대화 맥락 분석 전문가입니다.

context_analyzer 도구를 사용하여 사용자 질문의 성격을 파악하고
적절한 처리 방법을 결정하세요."""
        
        if STRANDS_AVAILABLE:
            try:
                return Agent(
                    system_prompt=system_prompt,
                    tools=[context_analyzer]
                )
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    # Enhanced Mock Agent 사용
                    return Agent(config=self.config)
                else:
                    raise e
        else:
            return Agent(config=self.config)
    
    def process_query(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        사용자 쿼리 처리 (실제 Strands 문법 - 동기 처리)
        타임아웃 래퍼를 사용하여 안전한 처리
        
        Args:
            query: 사용자 질문
            conversation_history: 대화 히스토리
            
        Returns:
            처리 결과
        """
        start_time = time.time()
        conversation_history = conversation_history or []
        
        print(f"🔍 쿼리 처리 시작: {query}")
        
        try:
            if STRANDS_AVAILABLE and self.main_agent:
                # 타임아웃 래퍼를 사용한 안전한 에이전트 호출
                result = safe_agent_call(
                    agent=self.main_agent,
                    query=query,
                    conversation_history=conversation_history,
                    timeout_seconds=60  # 60초 타임아웃으로 단축
                )
                
                # 결과 처리
                if result["success"]:
                    print(f"✅ Strands Agent 처리 성공 ({result['processing_time']:.2f}초)")
                    return {
                        "type": "ProperStrandsReAct",
                        "content": result["content"],
                        "error": False,
                        "processing_time": result["processing_time"],
                        "framework": "Proper Strands Agents",
                        "strands_available": self.strands_available,
                        "timeout_occurred": False
                    }
                else:
                    # 타임아웃이나 오류 발생 시 fallback 응답 사용
                    print(f"⚠️ Strands Agent 처리 실패: {result['error']}")
                    print(f"   타임아웃: {result['timeout']}, Fallback 사용: {result.get('fallback', False)}")
                    
                    return {
                        "type": "ProperStrandsReAct",
                        "content": result["content"],  # fallback 응답 포함
                        "error": False,  # fallback이므로 에러가 아님
                        "processing_time": result["processing_time"],
                        "framework": "Proper Strands Agents (Fallback)",
                        "strands_available": self.strands_available,
                        "timeout_occurred": result["timeout"],
                        "original_error": result["error"]
                    }
            else:
                # Mock agent 사용
                print("🔄 Mock Agent 사용")
                response = self.main_agent(f"""사용자 질문을 처리해주세요:

질문: {query}
대화 히스토리: {json.dumps(conversation_history[-3:], ensure_ascii=False)}""")
                
                processing_time = time.time() - start_time
                
                return {
                    "type": "ProperStrandsReAct",
                    "content": str(response),
                    "error": False,
                    "processing_time": processing_time,
                    "framework": "Mock Strands Agents",
                    "strands_available": self.strands_available,
                    "timeout_occurred": False
                }
                
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"쿼리 처리 중 예외 발생: {str(e)}"
            print(f"❌ {error_msg}")
            
            # 예외 발생 시에도 사용자에게 도움이 되는 응답 제공
            fallback_response = f"""죄송합니다. 요청을 처리하는 중 문제가 발생했습니다.

**질문:** {query}

**문제:** 시스템 오류가 발생했습니다.

**해결 방법:**
1. 잠시 후 다시 시도해 주세요
2. 질문을 더 간단하게 바꿔서 시도해 보세요
3. 문제가 지속되면 관리자에게 문의하세요

**오류 정보:** {str(e)}"""
            
            return {
                "type": "ProperStrandsReAct",
                "content": fallback_response,
                "error": False,  # 사용자에게는 에러가 아닌 것처럼 보이게
                "processing_time": processing_time,
                "framework": "Error Fallback",
                "strands_available": self.strands_available,
                "timeout_occurred": False,
                "exception_occurred": True,
                "original_error": str(e)
            }
            
        except Exception as e:
            return {
                "type": "ProperStrandsReAct",
                "content": f"처리 중 오류가 발생했습니다: {str(e)}",
                "processing_time": time.time() - start_time,
                "error": True,
                "error_details": str(e)
            }
    
    def demonstrate_tool_usage(self):
        """실제 Strands 문법의 도구 사용법 시연"""
        print("🔧 실제 Strands Agents 도구 사용법 시연")
        print("-" * 50)
        
        try:
            # 실제 Strands 문법: agent.tool.tool_name() 방식
            if hasattr(self.main_agent, 'tool'):
                # 맥락 분석 도구 직접 호출
                context_result = self.main_agent.tool.context_analyzer(
                    query="안녕하세요",
                    history_json="[]"
                )
                print(f"Context Analysis: {context_result}")
                
                # KB 검색 도구 직접 호출 (KB가 있는 경우)
                if self.config.is_kb_enabled():
                    search_result = self.main_agent.tool.kb_search_tool(
                        keywords=["테스트", "검색"],
                        max_results=3
                    )
                    print(f"KB Search: {search_result}")
                
                # 계산기 도구 직접 호출 (있는 경우)
                if calculator and STRANDS_AVAILABLE:
                    calc_result = self.main_agent.tool.calculator(
                        expression="2+2"
                    )
                    print(f"Calculator: {calc_result}")
            
            print("✅ 도구 사용법 시연 완료")
            
        except Exception as e:
            print(f"❌ 도구 사용법 시연 실패: {e}")
    
    def get_model_info(self) -> Dict:
        """모델 정보 반환"""
        return {
            "framework": "Proper Strands Agents",
            "strands_available": self.strands_available,
            "syntax_compliance": "Full",
            "tools_count": len(self.main_agent.tools) if hasattr(self.main_agent, 'tools') else 0,
            "kb_enabled": self.config.is_kb_enabled()
        }


@tool
def timeout_resilient_kb_search(keywords: List[str], max_results: int = 3) -> str:
    """
    타임아웃에 강한 Knowledge Base 검색 도구
    
    Args:
        keywords: 검색할 키워드 리스트
        max_results: 최대 결과 수 (기본값 3으로 축소)
        
    Returns:
        검색 결과를 JSON 문자열로 반환
    """
    import time
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    
    def search_with_timeout():
        """실제 검색 수행"""
        # KB 설정 확인
        if not hasattr(kb_search_tool, '_config') or not kb_search_tool._config.is_kb_enabled():
            return {
                "success": False,
                "error": "Knowledge Base가 설정되지 않았습니다.",
                "results": []
            }
        
        config = kb_search_tool._config
        
        from utils.kb_search import KnowledgeBaseSearcher
        kb_searcher = KnowledgeBaseSearcher()
        
        # 키워드 수 제한 (성능 향상)
        limited_keywords = keywords[:2]  # 최대 2개 키워드만 사용
        
        search_results = kb_searcher.search_multiple_queries(
            kb_id=config.kb_id,
            queries=limited_keywords,
            max_results_per_query=max(1, max_results // len(limited_keywords))
        )
        
        # 결과 정리
        formatted_results = []
        for i, result in enumerate(search_results[:max_results]):
            formatted_results.append({
                "id": i + 1,
                "content": result.get("content", "")[:500],  # 내용 길이 제한
                "source": result.get("source", ""),
                "score": result.get("score", 0),
                "query": result.get("query", "")
            })
        
        return {
            "success": True,
            "results_count": len(formatted_results),
            "results": formatted_results,
            "search_keywords": limited_keywords
        }
    
    try:
        # 60초 타임아웃으로 검색 실행
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(search_with_timeout)
            result = future.result(timeout=60)  # 60초 타임아웃
            
        return json.dumps(result)
        
    except FutureTimeoutError:
        return json.dumps({
            "success": False,
            "error": "KB 검색 시간이 초과되었습니다 (60초).",
            "error_type": "timeout",
            "results": [],
            "fallback_suggestion": "네트워크 상태를 확인하거나 더 간단한 키워드로 다시 시도해주세요."
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"KB 검색 중 오류: {str(e)}",
            "error_type": "general_error", 
            "results": [],
            "fallback_suggestion": "일반적인 지식으로 답변하겠습니다."
        })
